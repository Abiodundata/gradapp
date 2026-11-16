"""Get Personalized Recommendations use case.

Ranks active programs by how well they *fit* a student's profile. The score
is not a prediction of admission chances. Every point awarded comes with a
plain-language reason so students can see why a program was recommended.

Score components (maximum 100 points):

=====================  ======  ==============================================
Component              Points  Based on
=====================  ======  ==============================================
Academic fit             35    interests vs. program field/description and
                               faculty research areas
Budget                   15    tuition vs. annual tuition budget
Funding                  15    funding needs vs. funding available
Location                 15    preferred locations vs. city/state/country
GPA                      10    GPA vs. published minimum GPA
Timing                   10    application deadline still open
=====================  ======  ==============================================
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db.models import Prefetch

from gradapp.text import matched_phrases, original_words, tokenize
from programs.models import Faculty, GraduateProgram


WEIGHTS = {
    "academic": 35,
    "budget": 15,
    "funding": 15,
    "location": 15,
    "gpa": 10,
    "timing": 10,
}


@dataclass
class Recommendation:
    program: GraduateProgram
    score: int
    breakdown: dict
    reasons: list = field(default_factory=list)
    cautions: list = field(default_factory=list)
    matched_faculty: list = field(default_factory=list)


def _interest_text(profile):
    return " ".join(
        filter(
            None,
            [
                profile.academic_interests,
                profile.research_interests,
                profile.preferred_programs,
                profile.previous_field_of_study,
                profile.career_goals,
            ],
        )
    )


def profile_is_empty(profile):
    return not any(
        [
            profile.academic_interests,
            profile.research_interests,
            profile.preferred_programs,
            profile.previous_field_of_study,
            profile.preferred_locations,
            profile.tuition_budget,
            profile.gpa,
        ]
    )


def _academic(profile, program, interest_tokens):
    if not interest_tokens:
        return WEIGHTS["academic"] * 0.5, [], [], ["Add academic or research interests to your profile for better matching."]

    program_text = " ".join([program.name, program.field_of_study, program.department, program.description])
    program_tokens = tokenize(program_text)
    program_hits = interest_tokens & program_tokens
    name_hits = interest_tokens & tokenize(f"{program.name} {program.field_of_study}")

    faculty_matches = []
    for member in program.faculty.all():
        phrases = matched_phrases(_interest_text(profile), member.research_areas)
        if phrases:
            faculty_matches.append({"id": member.id, "name": member.name, "matched_areas": phrases})

    # Program text match is worth up to 25 points, faculty match up to 10.
    program_ratio = min(1.0, len(program_hits) / max(2, min(len(interest_tokens), 5)))
    if name_hits:
        program_ratio = max(program_ratio, 0.8)
    faculty_ratio = min(1.0, len(faculty_matches) / 2)
    points = 25 * program_ratio + 10 * faculty_ratio

    reasons, cautions = [], []
    if name_hits:
        words = original_words(name_hits, f"{program.name} {program.field_of_study}")
        reasons.append(f"Program focus ({', '.join(words)}) matches your interests.")
    elif program_hits:
        words = original_words(program_hits, program_text)[:4]
        reasons.append(f"Program description mentions {', '.join(words)}.")
    if faculty_matches:
        names = ", ".join(match["name"] for match in faculty_matches[:3])
        reasons.append(f"{len(faculty_matches)} faculty member(s) research topics you listed ({names}).")
    if not program_hits and not faculty_matches:
        cautions.append("Little overlap with the interests in your profile.")
    return points, reasons, faculty_matches, cautions


def _decimal(value):
    return None if value in (None, "") else Decimal(str(value))


def _budget(profile, program):
    budget, tuition = _decimal(profile.tuition_budget), _decimal(program.tuition_per_year)
    if budget is None:
        return WEIGHTS["budget"], [], []
    if tuition is None:
        return WEIGHTS["budget"] * 0.5, [], ["Tuition is not listed; check the official site."]
    if tuition <= budget:
        return WEIGHTS["budget"], [f"Tuition (${tuition:,.0f}/yr) is within your ${budget:,.0f} budget."], []
    if tuition <= budget * Decimal("1.2"):
        return WEIGHTS["budget"] * 0.5, [], [f"Tuition (${tuition:,.0f}/yr) is slightly above your budget."]
    return 0, [], [f"Tuition (${tuition:,.0f}/yr) is well above your ${budget:,.0f} budget."]


def _funding(profile, program):
    need = profile.funding_requirement
    has_funding = program.funding_available or bool(getattr(program, "funding_count", 0))
    if need == "not_required":
        return WEIGHTS["funding"], [], []
    if has_funding:
        return WEIGHTS["funding"], ["Funding opportunities are available."], []
    if need == "required":
        return 0, [], ["You need funding, but none is listed for this program."]
    return WEIGHTS["funding"] * 0.4, [], ["No funding listed for this program."]


def _location(profile, program):
    preferred = [loc.strip() for loc in (profile.preferred_locations or "").replace(";", ",").split(",") if loc.strip()]
    if not preferred:
        return WEIGHTS["location"], [], []
    university = program.university
    place_tokens = tokenize(f"{university.city} {university.state_or_region} {university.country}")
    for location in preferred:
        if tokenize(location) and tokenize(location) <= place_tokens:
            return WEIGHTS["location"], [f"Located in {university.city}, {university.state_or_region}, one of your preferred locations."], []
    return 0, [], [f"Not in your preferred locations ({', '.join(preferred)})."]


def _gpa(profile, program):
    gpa, minimum = _decimal(profile.gpa), _decimal(program.minimum_gpa)
    if gpa is None or minimum is None:
        return WEIGHTS["gpa"] * 0.6, [], []
    if gpa >= minimum:
        return WEIGHTS["gpa"], [f"Your GPA meets the published minimum of {program.minimum_gpa}."], []
    return 0, [], [f"Your GPA is below the published minimum of {program.minimum_gpa}."]


def _timing(program, today):
    deadline = program.application_deadline
    if deadline is None:
        return WEIGHTS["timing"] * 0.5, [], ["Application deadline is not listed."]
    days = (deadline - today).days
    if days < 0:
        return 0, [], [f"The listed deadline ({deadline:%b %d, %Y}) has passed."]
    if days <= 21:
        return WEIGHTS["timing"], [], [f"Deadline is soon: {deadline:%b %d, %Y} ({days} days)."]
    return WEIGHTS["timing"], [f"Application deadline {deadline:%b %d, %Y} is still open."], []


def recommend(profile, limit=10, today=None):
    """Return a ranked list of ``Recommendation`` objects for ``profile``."""
    from django.db.models import Count

    today = today or date.today()
    interest_tokens = tokenize(_interest_text(profile))

    programs = (
        GraduateProgram.objects.filter(is_active=True)
        .select_related("university")
        .annotate(funding_count=Count("funding_opportunities", distinct=True))
        .prefetch_related(Prefetch("faculty", queryset=Faculty.objects.filter(is_active=True)))
    )
    if profile.intended_degree_level:
        programs = programs.filter(degree_level=profile.intended_degree_level)

    results = []
    for program in programs:
        academic, a_reasons, faculty_matches, a_cautions = _academic(profile, program, interest_tokens)
        budget, b_reasons, b_cautions = _budget(profile, program)
        funding, f_reasons, f_cautions = _funding(profile, program)
        location, l_reasons, l_cautions = _location(profile, program)
        gpa, g_reasons, g_cautions = _gpa(profile, program)
        timing, t_reasons, t_cautions = _timing(program, today)

        breakdown = {
            "academic": round(academic),
            "budget": round(budget),
            "funding": round(funding),
            "location": round(location),
            "gpa": round(gpa),
            "timing": round(timing),
        }
        results.append(
            Recommendation(
                program=program,
                score=round(academic + budget + funding + location + gpa + timing),
                breakdown=breakdown,
                reasons=a_reasons + l_reasons + b_reasons + f_reasons + g_reasons + t_reasons,
                cautions=a_cautions + l_cautions + b_cautions + f_cautions + g_cautions + t_cautions,
                matched_faculty=faculty_matches,
            )
        )

    results.sort(key=lambda rec: (-rec.score, rec.program.university.name, rec.program.name))
    return results[:limit]


def similar_programs(program, limit=4):
    """Programs most similar to ``program`` (same degree level, overlapping topics)."""
    base_tokens = tokenize(f"{program.name} {program.field_of_study} {program.description}")
    candidates = (
        GraduateProgram.objects.filter(is_active=True, degree_level=program.degree_level)
        .exclude(pk=program.pk)
        .select_related("university")
    )
    scored = []
    for candidate in candidates:
        shared = base_tokens & tokenize(f"{candidate.name} {candidate.field_of_study} {candidate.description}")
        if shared:
            scored.append((len(shared), candidate))
    scored.sort(key=lambda item: (-item[0], item[1].name))
    return [candidate for _, candidate in scored[:limit]]
