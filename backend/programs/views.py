from datetime import date
from decimal import Decimal, InvalidOperation

from django.db.models import BooleanField, Count, Exists, OuterRef, Q, Value
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from gradapp.text import matched_phrases, tokenize
from planner.models import SavedProgram

from .models import Faculty, FundingOpportunity, GraduateProgram, University
from .permissions import IsAdminOrReadOnly
from .retrieval import retrieve_program_information
from .serializers import (
    FacultySerializer,
    FundingOpportunitySerializer,
    GraduateProgramSerializer,
    ProgramSummarySerializer,
    SourceSnapshotSerializer,
    UniversitySerializer,
)


TRUE_VALUES = {"true", "1", "yes"}
FALSE_VALUES = {"false", "0", "no"}


def parse_decimal(value, name):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValidationError({name: "Enter a valid number."})
    if not number.is_finite() or number < 0:
        raise ValidationError({name: "Enter a positive number."})
    return number


def parse_id_list(value, name="ids"):
    try:
        ids = [int(part) for part in str(value).split(",") if part.strip()]
    except ValueError:
        raise ValidationError({name: "Provide a comma-separated list of numeric IDs."})
    return list(dict.fromkeys(ids))  # de-duplicate, keep order


class UniversityViewSet(viewsets.ModelViewSet):
    serializer_class = UniversitySerializer
    permission_classes = [IsAdminOrReadOnly]
    queryset = University.objects.all()


class GraduateProgramViewSet(viewsets.ModelViewSet):
    """Search Graduate Programs, Advanced Search/Filter, View Program Details,
    Compare Programs and Retrieve Program Information."""

    serializer_class = GraduateProgramSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = (
            GraduateProgram.objects.select_related("university")
            .filter(is_active=True)
            .annotate(
                faculty_count=Count("faculty", filter=Q(faculty__is_active=True), distinct=True),
                funding_count=Count(
                    "funding_opportunities", filter=Q(funding_opportunities__is_active=True), distinct=True
                ),
            )
        )
        user = self.request.user
        if user and user.is_authenticated:
            queryset = queryset.annotate(
                is_saved=Exists(SavedProgram.objects.filter(user=user, program=OuterRef("pk")))
            )
        else:
            queryset = queryset.annotate(is_saved=Value(False, output_field=BooleanField()))

        if self.action != "list":
            return queryset
        return self.filter_programs(queryset, self.request.query_params)

    @staticmethod
    def filter_programs(queryset, params):
        search = params.get("search", "").strip()
        if search:
            for term in search.split()[:8]:
                queryset = queryset.filter(
                    Q(name__icontains=term)
                    | Q(field_of_study__icontains=term)
                    | Q(department__icontains=term)
                    | Q(description__icontains=term)
                    | Q(university__name__icontains=term)
                    | Q(university__city__icontains=term)
                    | Q(university__state_or_region__icontains=term)
                )

        if params.get("degree_level"):
            queryset = queryset.filter(degree_level=params["degree_level"])
        if params.get("field"):
            queryset = queryset.filter(field_of_study__icontains=params["field"])
        if params.get("country"):
            queryset = queryset.filter(university__country__iexact=params["country"])
        if params.get("state_or_region"):
            queryset = queryset.filter(university__state_or_region__iexact=params["state_or_region"])
        if params.get("university"):
            queryset = queryset.filter(university_id=params["university"]) if params["university"].isdigit() else queryset.none()
        funding = params.get("funding_available", "").lower()
        if funding in TRUE_VALUES:
            queryset = queryset.filter(Q(funding_available=True) | Q(funding_count__gt=0))
        elif funding in FALSE_VALUES:
            queryset = queryset.filter(funding_available=False, funding_count=0)
        if params.get("max_tuition"):
            queryset = queryset.filter(tuition_per_year__lte=parse_decimal(params["max_tuition"], "max_tuition"))
        if params.get("max_gpa_required"):
            gpa = parse_decimal(params["max_gpa_required"], "max_gpa_required")
            queryset = queryset.filter(Q(minimum_gpa__lte=gpa) | Q(minimum_gpa__isnull=True))
        if params.get("deadline_open", "").lower() in TRUE_VALUES:
            queryset = queryset.filter(Q(application_deadline__gte=date.today()) | Q(application_deadline__isnull=True))

        ordering = params.get("ordering")
        allowed_ordering = {
            "name": "name",
            "-name": "-name",
            "tuition": "tuition_per_year",
            "-tuition": "-tuition_per_year",
            "deadline": "application_deadline",
            "university": "university__name",
        }
        return queryset.order_by(allowed_ordering.get(ordering, "university__name"), "name", "id")

    @action(detail=False, methods=["get"])
    def compare(self, request):
        """Compare Programs: GET /api/programs/compare/?ids=1,2,3 (2 to 4 programs)."""
        ids = parse_id_list(request.query_params.get("ids", ""))
        if not 2 <= len(ids) <= 4:
            raise ValidationError({"ids": "Select between 2 and 4 programs to compare."})
        programs = {program.id: program for program in self.get_queryset().filter(id__in=ids)}
        missing = [pk for pk in ids if pk not in programs]
        if missing:
            raise ValidationError({"ids": f"Programs not found: {', '.join(map(str, missing))}."})

        results = []
        for pk in ids:
            program = programs[pk]
            data = self.get_serializer(program).data
            faculty = Faculty.objects.filter(programs=program, is_active=True)
            areas = {}
            for member in faculty:
                for area in member.research_area_list:
                    areas[area.lower()] = areas.get(area.lower(), 0) + 1
            funding = FundingOpportunity.objects.filter(
                Q(program=program) | Q(university=program.university, program__isnull=True), is_active=True
            )
            data["top_research_areas"] = [area for area, _ in sorted(areas.items(), key=lambda x: -x[1])[:5]]
            data["funding_opportunities"] = [
                {"id": item.id, "name": item.name, "funding_type": item.funding_type, "amount": item.amount, "amount_note": item.amount_note}
                for item in funding[:5]
            ]
            data["days_until_deadline"] = (
                (program.application_deadline - date.today()).days if program.application_deadline else None
            )
            results.append(data)
        return Response({"results": results})

    @action(detail=True, methods=["get"])
    def similar(self, request, pk=None):
        """Comparable programs with overlapping topics at the same degree level."""
        from assistant.recommendations import similar_programs

        program = self.get_object()
        return Response(ProgramSummarySerializer(similar_programs(program), many=True).data)

    @action(detail=True, methods=["get"])
    def sources(self, request, pk=None):
        """History of information retrieval attempts for this program."""
        program = self.get_object()
        return Response(SourceSnapshotSerializer(program.snapshots.all()[:10], many=True).data)

    @action(detail=True, methods=["post"], url_path="retrieve", permission_classes=[permissions.IsAdminUser])
    def retrieve_information(self, request, pk=None):
        """Retrieve Program Information from the official website (administrators)."""
        program = self.get_object()
        snapshot = retrieve_program_information(program, apply=request.data.get("apply", True) is not False)
        program.refresh_from_db()
        return Response(
            {
                "snapshot": SourceSnapshotSerializer(snapshot).data,
                "program": self.get_serializer(self.get_queryset().get(pk=program.pk)).data,
            },
            status=status.HTTP_200_OK,  # the snapshot status says whether retrieval succeeded
        )


class FacultyViewSet(viewsets.ModelViewSet):
    """View Faculty Profiles and find potential advisors.

    ``?match_profile=true`` ranks faculty by overlap with the student's
    research and academic interests and explains which areas matched.
    """

    serializer_class = FacultySerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = (
            Faculty.objects.filter(is_active=True)
            .select_related("university")
            .prefetch_related("programs")
        )
        if self.action != "list":
            return queryset
        params = self.request.query_params
        search = params.get("search", "").strip()
        if search:
            for term in search.split()[:8]:
                queryset = queryset.filter(
                    Q(name__icontains=term)
                    | Q(research_areas__icontains=term)
                    | Q(department__icontains=term)
                    | Q(title__icontains=term)
                    | Q(university__name__icontains=term)
                )
        if params.get("research_area"):
            queryset = queryset.filter(research_areas__icontains=params["research_area"])
        if params.get("university", "").isdigit():
            queryset = queryset.filter(university_id=params["university"])
        if params.get("program", "").isdigit():
            queryset = queryset.filter(programs__id=params["program"])
        if params.get("accepting_students", "").lower() in TRUE_VALUES:
            queryset = queryset.filter(accepting_students=True)
        return queryset.distinct().order_by("name")

    def list(self, request, *args, **kwargs):
        if request.query_params.get("match_profile", "").lower() not in TRUE_VALUES:
            return super().list(request, *args, **kwargs)

        profile = getattr(request.user, "student_profile", None)
        interests = " ".join(filter(None, [
            getattr(profile, "research_interests", ""), getattr(profile, "academic_interests", "")
        ]))
        interest_tokens = tokenize(interests)
        if not interest_tokens:
            raise ValidationError({"match_profile": "Add research or academic interests to your profile to find matching advisors."})

        ranked = []
        for member in self.get_queryset():
            area_tokens = tokenize(f"{member.research_areas} {member.bio}")
            shared = interest_tokens & area_tokens
            if not shared:
                continue
            member.match_score = round(100 * len(shared) / len(interest_tokens))
            member.matched_areas = matched_phrases(interests, member.research_areas) or sorted(shared)
            ranked.append(member)
        ranked.sort(key=lambda m: (-m.match_score, m.name))
        page = self.paginate_queryset(ranked)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


class FundingOpportunityViewSet(viewsets.ModelViewSet):
    """Search Funding use case."""

    serializer_class = FundingOpportunitySerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = FundingOpportunity.objects.filter(is_active=True).select_related("university", "program")
        if self.action != "list":
            return queryset
        params = self.request.query_params
        search = params.get("search", "").strip()
        if search:
            for term in search.split()[:8]:
                queryset = queryset.filter(
                    Q(name__icontains=term)
                    | Q(description__icontains=term)
                    | Q(eligibility__icontains=term)
                    | Q(provider__icontains=term)
                    | Q(university__name__icontains=term)
                    | Q(program__name__icontains=term)
                )
        if params.get("funding_type"):
            queryset = queryset.filter(funding_type=params["funding_type"])
        if params.get("university", "").isdigit():
            queryset = queryset.filter(university_id=params["university"])
        if params.get("program", "").isdigit():
            program = GraduateProgram.objects.filter(pk=params["program"]).first()
            if program is None:
                return queryset.none()
            queryset = queryset.filter(
                Q(program=program) | Q(university=program.university, program__isnull=True)
            )
        if params.get("degree_level"):
            queryset = queryset.filter(
                Q(degree_levels="") | Q(degree_levels__icontains=params["degree_level"])
            )
        if params.get("international_eligible", "").lower() in TRUE_VALUES:
            queryset = queryset.filter(international_eligible=True)
        if params.get("covers_tuition", "").lower() in TRUE_VALUES:
            queryset = queryset.filter(covers_tuition=True)
        if params.get("min_amount"):
            queryset = queryset.filter(amount__gte=parse_decimal(params["min_amount"], "min_amount"))
        if params.get("open_only", "true").lower() in TRUE_VALUES:
            queryset = queryset.filter(Q(deadline__gte=date.today()) | Q(deadline__isnull=True))
        ordering = {"amount": "-amount", "deadline": "deadline", "name": "name"}.get(params.get("ordering"), "deadline")
        return queryset.order_by(ordering, "name", "id")
