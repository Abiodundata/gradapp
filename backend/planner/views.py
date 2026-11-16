from datetime import date

from django.db.models import Q
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from programs.models import FundingOpportunity

from .models import SavedProgram
from .serializers import SavedProgramSerializer


class SavedProgramViewSet(viewsets.ModelViewSet):
    """Save Programs use case: each student manages only their own shortlist."""

    serializer_class = SavedProgramSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = SavedProgram.objects.filter(user=self.request.user).select_related("program__university")
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class DeadlinesView(APIView):
    """Track Application Deadlines use case.

    Combines application deadlines (and personal target dates) of saved
    programs with deadlines of funding linked to those programs or their
    universities, sorted by date.
    """

    CLOSED_STATUSES = {"submitted", "admitted", "rejected", "withdrawn"}

    def get(self, request):
        today = date.today()
        include_past = request.query_params.get("include_past", "").lower() in {"true", "1"}
        saved = SavedProgram.objects.filter(user=request.user).select_related("program__university")

        items = []
        program_ids, university_ids = set(), set()
        for entry in saved:
            program = entry.program
            program_ids.add(program.id)
            university_ids.add(program.university_id)
            base = {
                "saved_program_id": entry.id,
                "program_id": program.id,
                "program_name": program.name,
                "university_name": program.university.name,
                "status": entry.status,
                "status_display": entry.get_status_display(),
                "url": program.program_url,
                "completed": entry.status in self.CLOSED_STATUSES,
            }
            if program.application_deadline:
                items.append({**base, "kind": "application", "title": f"Application deadline: {program.name}", "date": program.application_deadline})
            if entry.personal_deadline:
                items.append({**base, "kind": "personal", "title": f"Personal target: {program.name}", "date": entry.personal_deadline})

        funding = FundingOpportunity.objects.filter(
            Q(program_id__in=program_ids) | Q(university_id__in=university_ids, program__isnull=True),
            is_active=True,
            deadline__isnull=False,
        ).select_related("university", "program")
        for item in funding:
            items.append({
                "kind": "funding",
                "title": f"Funding deadline: {item.name}",
                "date": item.deadline,
                "funding_id": item.id,
                "program_id": item.program_id,
                "program_name": item.program.name if item.program else None,
                "university_name": item.university.name if item.university else item.provider,
                "url": item.url,
                "completed": False,
            })

        for item in items:
            item["days_left"] = (item["date"] - today).days
            item["is_past"] = item["days_left"] < 0
            item["urgency"] = (
                "past" if item["is_past"] else "urgent" if item["days_left"] <= 14 else "soon" if item["days_left"] <= 45 else "later"
            )
        if not include_past:
            items = [item for item in items if not item["is_past"]]
        items.sort(key=lambda item: (item["date"], item["title"]))

        undated = [
            {"program_id": entry.program.id, "program_name": entry.program.name, "university_name": entry.program.university.name}
            for entry in saved
            if not entry.program.application_deadline and not entry.personal_deadline
        ]
        return Response({"today": today, "results": items, "saved_without_deadline": undated})
