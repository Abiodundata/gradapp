from django.contrib import admin, messages

from .models import Faculty, FundingOpportunity, GraduateProgram, SourceSnapshot, University
from .retrieval import retrieve_program_information


@admin.action(description="Mark selected records as reviewed")
def mark_reviewed(modeladmin, request, queryset):
    updated = queryset.update(needs_review=False)
    modeladmin.message_user(request, f"{updated} record(s) marked as reviewed.")


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "state_or_region", "country")
    search_fields = ("name", "city", "state_or_region", "country")


class SourceSnapshotInline(admin.TabularInline):
    model = SourceSnapshot
    extra = 0
    can_delete = False
    fields = ("fetched_at", "status", "http_status", "extraction_method", "applied_fields", "error")
    readonly_fields = fields
    show_change_link = True


@admin.register(GraduateProgram)
class GraduateProgramAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "university",
        "degree_level",
        "field_of_study",
        "funding_available",
        "application_deadline",
        "source_retrieved_at",
        "origin",
        "needs_review",
        "is_active",
    )
    list_filter = ("needs_review", "origin", "degree_level", "funding_available", "is_active", "university")
    search_fields = ("name", "university__name", "field_of_study")
    inlines = (SourceSnapshotInline,)
    actions = ("retrieve_information", mark_reviewed)

    @admin.action(description="Retrieve program information from official website")
    def retrieve_information(self, request, queryset):
        succeeded = failed = 0
        for program in queryset.select_related("university"):
            snapshot = retrieve_program_information(program)
            if snapshot.status == SourceSnapshot.Status.SUCCESS:
                succeeded += 1
            else:
                failed += 1
                self.message_user(request, f"{program}: {snapshot.error}", messages.WARNING)
        self.message_user(request, f"Retrieved {succeeded} program(s); {failed} failed.")


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ("name", "title", "university", "department", "accepting_students", "origin", "needs_review", "is_active")
    list_filter = ("needs_review", "origin", "university", "accepting_students", "is_active")
    actions = (mark_reviewed,)
    search_fields = ("name", "research_areas", "department")
    filter_horizontal = ("programs",)


@admin.register(FundingOpportunity)
class FundingOpportunityAdmin(admin.ModelAdmin):
    list_display = ("name", "funding_type", "university", "program", "amount", "deadline", "origin", "needs_review", "is_active")
    list_filter = ("needs_review", "origin", "funding_type", "covers_tuition", "international_eligible", "is_active")
    actions = (mark_reviewed,)
    search_fields = ("name", "provider", "description")


@admin.register(SourceSnapshot)
class SourceSnapshotAdmin(admin.ModelAdmin):
    list_display = ("program", "status", "http_status", "extraction_method", "fetched_at")
    list_filter = ("status", "extraction_method")
    readonly_fields = [field.name for field in SourceSnapshot._meta.fields]
