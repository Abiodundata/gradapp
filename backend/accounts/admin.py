from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import StudentProfile


User = get_user_model()


class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    can_delete = False
    extra = 0


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (StudentProfileInline,)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "intended_degree_level",
        "previous_field_of_study",
        "funding_requirement",
        "updated_at",
    )
    list_filter = ("intended_degree_level", "funding_requirement")
    search_fields = ("user__username", "user__email", "research_interests")
