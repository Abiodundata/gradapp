from datetime import date

from rest_framework import serializers

from .models import Faculty, FundingOpportunity, GraduateProgram, SourceSnapshot, University


class UniversitySerializer(serializers.ModelSerializer):
    class Meta:
        model = University
        fields = ("id", "name", "city", "state_or_region", "country", "website_url")


class ProgramSummarySerializer(serializers.ModelSerializer):
    """Compact program representation used inside other resources."""

    university = UniversitySerializer(read_only=True)

    class Meta:
        model = GraduateProgram
        fields = (
            "id",
            "name",
            "degree_level",
            "field_of_study",
            "university",
            "tuition_per_year",
            "funding_available",
            "application_deadline",
            "program_url",
            "needs_review",
        )


class GraduateProgramSerializer(serializers.ModelSerializer):
    university = UniversitySerializer(read_only=True)
    university_id = serializers.PrimaryKeyRelatedField(
        queryset=University.objects.all(), source="university", write_only=True
    )
    is_saved = serializers.BooleanField(read_only=True, default=False)
    is_stale = serializers.BooleanField(read_only=True)
    faculty_count = serializers.IntegerField(read_only=True, default=0)
    funding_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = GraduateProgram
        fields = (
            "id",
            "university",
            "university_id",
            "name",
            "degree_level",
            "field_of_study",
            "department",
            "description",
            "admission_requirements",
            "minimum_gpa",
            "tuition_per_year",
            "funding_available",
            "funding_details",
            "application_deadline",
            "program_url",
            "source_retrieved_at",
            "is_stale",
            "is_active",
            "origin",
            "needs_review",
            "is_saved",
            "faculty_count",
            "funding_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "source_retrieved_at", "created_at", "updated_at")


class FacultySerializer(serializers.ModelSerializer):
    university = UniversitySerializer(read_only=True)
    university_id = serializers.PrimaryKeyRelatedField(
        queryset=University.objects.all(), source="university", write_only=True
    )
    programs = serializers.SerializerMethodField()
    program_ids = serializers.PrimaryKeyRelatedField(
        queryset=GraduateProgram.objects.all(), source="programs", many=True, write_only=True, required=False
    )
    research_area_list = serializers.ListField(child=serializers.CharField(), read_only=True)
    match_score = serializers.IntegerField(read_only=True, required=False)
    matched_areas = serializers.ListField(child=serializers.CharField(), read_only=True, required=False)

    class Meta:
        model = Faculty
        fields = (
            "id",
            "university",
            "university_id",
            "programs",
            "program_ids",
            "name",
            "title",
            "department",
            "email",
            "research_areas",
            "research_area_list",
            "bio",
            "profile_url",
            "accepting_students",
            "origin",
            "needs_review",
            "match_score",
            "matched_areas",
        )

    def get_programs(self, obj):
        return [
            {"id": program.id, "name": program.name, "degree_level": program.degree_level}
            for program in obj.programs.all()
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for key in ("match_score", "matched_areas"):
            if hasattr(instance, key):
                data[key] = getattr(instance, key)
            else:
                data.pop(key, None)
        return data


class FundingOpportunitySerializer(serializers.ModelSerializer):
    university = UniversitySerializer(read_only=True)
    university_id = serializers.PrimaryKeyRelatedField(
        queryset=University.objects.all(), source="university", write_only=True, required=False, allow_null=True
    )
    program = serializers.SerializerMethodField()
    program_id = serializers.PrimaryKeyRelatedField(
        queryset=GraduateProgram.objects.all(), source="program", write_only=True, required=False, allow_null=True
    )
    funding_type_display = serializers.CharField(source="get_funding_type_display", read_only=True)
    is_open = serializers.SerializerMethodField()
    days_left = serializers.SerializerMethodField()

    class Meta:
        model = FundingOpportunity
        fields = (
            "id",
            "name",
            "funding_type",
            "funding_type_display",
            "university",
            "university_id",
            "program",
            "program_id",
            "provider",
            "description",
            "eligibility",
            "amount",
            "amount_note",
            "covers_tuition",
            "international_eligible",
            "degree_levels",
            "deadline",
            "is_open",
            "days_left",
            "url",
            "origin",
            "needs_review",
        )

    def get_program(self, obj):
        if not obj.program:
            return None
        return {"id": obj.program.id, "name": obj.program.name, "degree_level": obj.program.degree_level}

    def get_days_left(self, obj):
        if not obj.deadline:
            return None
        return (obj.deadline - date.today()).days

    def get_is_open(self, obj):
        return obj.deadline is None or obj.deadline >= date.today()


class SourceSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceSnapshot
        fields = (
            "id",
            "url",
            "status",
            "http_status",
            "page_title",
            "extracted",
            "applied_fields",
            "extraction_method",
            "error",
            "fetched_at",
        )
