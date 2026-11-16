from django.conf import settings
from django.db import models

from programs.models import GraduateProgram


class SavedProgram(models.Model):
    """A program a student saved to their shortlist (Save Programs use case)."""

    class Status(models.TextChoices):
        INTERESTED = "interested", "Interested"
        PREPARING = "preparing", "Preparing application"
        SUBMITTED = "submitted", "Submitted"
        ADMITTED = "admitted", "Admitted"
        REJECTED = "rejected", "Not admitted"
        WITHDRAWN = "withdrawn", "Withdrawn"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_programs"
    )
    program = models.ForeignKey(
        GraduateProgram, on_delete=models.CASCADE, related_name="saved_by"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INTERESTED)
    notes = models.TextField(blank=True)
    personal_deadline = models.DateField(
        null=True,
        blank=True,
        help_text="Optional personal target date, e.g. to finish an application early.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=("user", "program"), name="unique_saved_program_per_user")
        ]

    def __str__(self):
        return f"{self.user} saved {self.program}"
