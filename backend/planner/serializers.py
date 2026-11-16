from rest_framework import serializers

from programs.models import GraduateProgram
from programs.serializers import ProgramSummarySerializer

from .models import SavedProgram


class SavedProgramSerializer(serializers.ModelSerializer):
    program = ProgramSummarySerializer(read_only=True)
    program_id = serializers.PrimaryKeyRelatedField(
        queryset=GraduateProgram.objects.filter(is_active=True), source="program", write_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = SavedProgram
        fields = (
            "id",
            "program",
            "program_id",
            "status",
            "status_display",
            "notes",
            "personal_deadline",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_program_id(self, program):
        request = self.context["request"]
        if self.instance is None and SavedProgram.objects.filter(user=request.user, program=program).exists():
            raise serializers.ValidationError("You have already saved this program.")
        return program

    def update(self, instance, validated_data):
        validated_data.pop("program", None)  # the saved program itself cannot be swapped
        return super().update(instance, validated_data)
