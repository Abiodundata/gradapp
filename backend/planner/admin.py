from django.contrib import admin

from .models import SavedProgram


@admin.register(SavedProgram)
class SavedProgramAdmin(admin.ModelAdmin):
    list_display = ("user", "program", "status", "personal_deadline", "updated_at")
    list_filter = ("status",)
    search_fields = ("user__username", "program__name", "program__university__name")
