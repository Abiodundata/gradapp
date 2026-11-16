from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Origin(models.TextChoices):
    ADMIN = "admin", "Added by administrator"
    SAMPLE = "sample", "Sample data"
    WEB = "web", "Found by web search"


class ReviewableMixin(models.Model):
    """Records found by the AI web search are saved for review before being trusted."""

    origin = models.CharField(max_length=10, choices=Origin.choices, default=Origin.ADMIN)
    needs_review = models.BooleanField(
        default=False, help_text="Found automatically on the web and not yet checked by an administrator."
    )

    class Meta:
        abstract = True


class University(models.Model):
    name = models.CharField(max_length=255, unique=True)
    city = models.CharField(max_length=120)
    state_or_region = models.CharField(max_length=120)
    country = models.CharField(max_length=120, default="United States")
    website_url = models.URLField()

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "universities"

    def __str__(self):
        return self.name


class GraduateProgram(ReviewableMixin):
    class DegreeLevel(models.TextChoices):
        MASTERS = "masters", "Master's"
        DOCTORAL = "doctoral", "Doctoral"
        OTHER = "other", "Other graduate degree"

    university = models.ForeignKey(
        University, on_delete=models.CASCADE, related_name="programs"
    )
    name = models.CharField(max_length=255)
    degree_level = models.CharField(max_length=20, choices=DegreeLevel.choices)
    field_of_study = models.CharField(max_length=180)
    department = models.CharField(max_length=180, blank=True)
    description = models.TextField(blank=True)
    admission_requirements = models.TextField(blank=True)
    minimum_gpa = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(4)],
    )
    tuition_per_year = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    funding_available = models.BooleanField(default=False)
    funding_details = models.TextField(blank=True)
    application_deadline = models.DateField(null=True, blank=True)
    program_url = models.URLField()
    source_retrieved_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("university__name", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("university", "name", "degree_level"),
                name="unique_program_per_university_and_degree",
            )
        ]

    def __str__(self):
        return f"{self.name} at {self.university.name}"

    @property
    def is_stale(self):
        """True when program information has never been verified or is old."""
        if not self.source_retrieved_at:
            return True
        age = timezone.now() - self.source_retrieved_at
        return age > timedelta(days=settings.RETRIEVAL_STALE_AFTER_DAYS)


class Faculty(ReviewableMixin):
    """A professor or researcher a student could contact as a potential advisor."""

    university = models.ForeignKey(
        University, on_delete=models.CASCADE, related_name="faculty"
    )
    programs = models.ManyToManyField(
        GraduateProgram, related_name="faculty", blank=True
    )
    name = models.CharField(max_length=180)
    title = models.CharField(max_length=180, blank=True)
    department = models.CharField(max_length=180, blank=True)
    email = models.EmailField(blank=True)
    research_areas = models.TextField(
        blank=True, help_text="Comma-separated research areas, e.g. 'machine learning, robotics'."
    )
    bio = models.TextField(blank=True)
    profile_url = models.URLField(blank=True)
    accepting_students = models.BooleanField(
        null=True, blank=True, help_text="Leave empty when unknown."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "faculty"

    def __str__(self):
        return f"{self.name} ({self.university.name})"

    @property
    def research_area_list(self):
        return [area.strip() for area in self.research_areas.split(",") if area.strip()]


class FundingOpportunity(ReviewableMixin):
    class FundingType(models.TextChoices):
        ASSISTANTSHIP = "assistantship", "Assistantship"
        FELLOWSHIP = "fellowship", "Fellowship"
        SCHOLARSHIP = "scholarship", "Scholarship"
        GRANT = "grant", "Grant"
        OTHER = "other", "Other"

    name = models.CharField(max_length=255)
    funding_type = models.CharField(max_length=20, choices=FundingType.choices)
    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name="funding_opportunities",
        null=True,
        blank=True,
        help_text="Leave empty for external scholarships not tied to one university.",
    )
    program = models.ForeignKey(
        GraduateProgram,
        on_delete=models.CASCADE,
        related_name="funding_opportunities",
        null=True,
        blank=True,
    )
    provider = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    eligibility = models.TextField(blank=True)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    amount_note = models.CharField(
        max_length=255, blank=True, help_text="e.g. 'per year' or 'plus full tuition waiver'."
    )
    covers_tuition = models.BooleanField(default=False)
    international_eligible = models.BooleanField(default=True)
    degree_levels = models.CharField(
        max_length=60,
        blank=True,
        help_text="Comma-separated degree levels (masters, doctoral, other). Empty means all.",
    )
    deadline = models.DateField(null=True, blank=True)
    url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("deadline", "name")
        verbose_name_plural = "funding opportunities"

    def __str__(self):
        return self.name


class SourceSnapshot(models.Model):
    """Record of one attempt to retrieve program information from its official website."""

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        BLOCKED = "blocked", "Blocked (robots.txt or unsafe URL)"

    program = models.ForeignKey(
        GraduateProgram, on_delete=models.CASCADE, related_name="snapshots"
    )
    url = models.URLField()
    status = models.CharField(max_length=20, choices=Status.choices)
    http_status = models.PositiveIntegerField(null=True, blank=True)
    page_title = models.CharField(max_length=500, blank=True)
    content_excerpt = models.TextField(blank=True)
    extracted = models.JSONField(default=dict, blank=True)
    applied_fields = models.JSONField(default=list, blank=True)
    extraction_method = models.CharField(max_length=40, blank=True)
    error = models.TextField(blank=True)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-fetched_at",)

    def __str__(self):
        return f"{self.program} - {self.status} at {self.fetched_at:%Y-%m-%d %H:%M}"
