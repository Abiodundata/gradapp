"""Shared factories for GradApp tests."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model

from accounts.models import StudentProfile
from programs.models import Faculty, FundingOpportunity, GraduateProgram, University


User = get_user_model()
PASSWORD = "StrongPass!2026"


def make_user(username="student", staff=False, **profile):
    user = User.objects.create_user(username=username, email=f"{username}@example.com", password=PASSWORD, is_staff=staff)
    StudentProfile.objects.create(user=user, **profile)
    return user


def make_university(name="Example University", city="Corpus Christi", state="Texas", country="United States"):
    return University.objects.create(
        name=name, city=city, state_or_region=state, country=country, website_url="https://example.edu/"
    )


def make_program(university, name="Data Science", degree="masters", days=60, **extra):
    defaults = {
        "field_of_study": name,
        "tuition_per_year": 20000,
        "funding_available": False,
        "program_url": f"https://example.edu/{name.lower().replace(' ', '-')}",
        "application_deadline": date.today() + timedelta(days=days) if days is not None else None,
    }
    defaults.update(extra)
    return GraduateProgram.objects.create(university=university, name=name, degree_level=degree, **defaults)


def make_faculty(university, name="Dr. Ada Example", areas="machine learning, robotics", programs=(), **extra):
    member = Faculty.objects.create(university=university, name=name, research_areas=areas, **extra)
    member.programs.set(programs)
    return member


def make_funding(name="Research Assistantship", university=None, program=None, days=30, **extra):
    defaults = {"funding_type": "assistantship", "amount": 20000, "deadline": date.today() + timedelta(days=days) if days is not None else None}
    defaults.update(extra)
    return FundingOpportunity.objects.create(name=name, university=university, program=program, **defaults)
