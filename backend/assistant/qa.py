"""Ask AI Questions use case.

Answers a student's question using GradApp's own verified records
(retrieval-augmented generation):

1. Find the programs, faculty and funding records most relevant to the
   question (and, optionally, the student's profile).
2. Give only those records to the AI model and ask it to answer *from them*,
   citing record IDs such as [P3] or [F7].
3. Return the answer together with the source records so the student can
   open and verify each one.

If AI is not configured or fails, the most relevant records are returned
with a short rule-based summary instead.
"""

import re
from datetime import date

from django.conf import settings
from django.db.models import Q

from gradapp.text import tokenize
from programs.models import Faculty, FundingOpportunity, GraduateProgram, University

from . import llm


MAX_PER_TYPE = 4

# Words that tell us what kind of record the student is asking about.
FUNDING_WORDS = {"scholarship", "funding", "fund", "fellowship", "assistantship", "grant", "stipend",
                 "financial", "aid", "waiver", "money", "pay", "afford", "cost"}
FACULTY_WORDS = {"professor", "faculty", "advisor", "adviser", "supervisor", "mentor", "lab", "researcher"}
INTERNATIONAL_WORDS = {"internation", "foreign", "visa"}

SYSTEM_PROMPT = """You are GradApp's graduate-admissions assistant.
Answer the student's question using ONLY the records provided in <records>.
Rules:
- Cite every fact with the record ID in square brackets, e.g. [P2] or [F5] or [G1].
- {missing_rule} Do not invent programs, people, numbers or dates.
- You describe how well options fit; you never predict admission chances.
- Remind the student to verify deadlines and costs on the official site when you mention them.
- Be concise: at most about 180 words, using short paragraphs or bullet points.
Today's date is {today}."""

MISSING_RULE_WITH_WEB = (
    "If the records do not contain the information needed to answer the question (for example, the "
    "student asks about a university, program, person or scholarship that is not in the records), reply "
    "with exactly NO_ANSWER and nothing else. GradApp will then search the web."
)
MISSING_RULE_NO_WEB = (
    "If the records do not contain the answer, say so plainly and suggest what the student could search "
    "for or check on the official university website."
)
NO_ANSWER = "NO_ANSWER"


def _score(tokens, text):
    return len(tokens & tokenize(text))


# What a record *is* (its name, field or research areas) counts more than
# words that merely appear somewhere in its description.
def _key_text(obj):
    if isinstance(obj, GraduateProgram):
        return f"{obj.name} {obj.field_of_study}"
    if isinstance(obj, Faculty):
        return obj.research_areas
    return f"{obj.name} {obj.get_funding_type_display()}"


KEY_WEIGHT = 3


def _rank(queryset, tokens, text_fn, keep_unmatched=False):
    """Order records by how well they match the query words (stable for ties)."""
    scored = []
    for position, obj in enumerate(queryset):
        score = _score(tokens, text_fn(obj)) + KEY_WEIGHT * _score(tokens, _key_text(obj))
        if score or keep_unmatched:
            scored.append((score, position, obj))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [obj for _, _, obj in scored[:MAX_PER_TYPE]]


def _program_text(program):
    return " ".join([
        program.name, program.field_of_study, program.department, program.description,
        program.admission_requirements, program.funding_details, program.university.name,
        program.university.city, program.university.state_or_region, program.university.country,
        program.get_degree_level_display(),
    ])


def _faculty_text(member):
    return " ".join([member.name, member.title, member.department, member.research_areas, member.bio, member.university.name])


def _funding_text(item):
    return " ".join([
        item.name, item.get_funding_type_display(), item.provider, item.description, item.eligibility,
        "international students eligible" if item.international_eligible else "domestic students only",
        "covers tuition" if item.covers_tuition else "",
        item.university.name if item.university else "", item.program.name if item.program else "",
    ])


MAX_SECONDARY = 2  # records shown for types the question is not mainly about

_MASTERS_RE = re.compile(r"\b(master'?s?|ms|m\.s\.|msc|mba|mph)\b", re.IGNORECASE)
_DOCTORAL_RE = re.compile(r"\b(ph\.?d|doctoral|doctorate)\b", re.IGNORECASE)


def detect_degree_level(question):
    """'masters' or 'doctoral' when the question names exactly one level, else None."""
    masters, doctoral = bool(_MASTERS_RE.search(question)), bool(_DOCTORAL_RE.search(question))
    if masters != doctoral:
        return "masters" if masters else "doctoral"
    return None


def detect_intent(question):
    """Return which record types the question is mainly about, most relevant first."""
    tokens = tokenize(question)
    order = []
    if tokens & FUNDING_WORDS:
        order.append("funding")
    if tokens & FACULTY_WORDS:
        order.append("faculty")
    order.append("programs")
    for kind in ("faculty", "funding"):
        if kind not in order:
            order.append(kind)
    return order


GENERIC_WORDS = FUNDING_WORDS | FACULTY_WORDS | INTERNATIONAL_WORDS | {
    "open", "available", "offer", "accept", "currently", "now", "list", "which", "any", "all", "information", "tell",
}
_PROGRAMS_RE = re.compile(r"\bprograms?\b", re.IGNORECASE)


def detect_locations(question):
    """Return the university cities/states/countries named in the question."""
    text = question.lower()
    names = set()
    for row in University.objects.values_list("city", "state_or_region", "country").distinct():
        for value in row:
            if value and re.search(rf"\b{re.escape(value.lower())}\b", text):
                names.add(value)
    return names


def _matching(queryset, tokens, fields):
    """Database pre-filter: records containing any of ``tokens`` in any of ``fields``."""
    condition = Q()
    for token in list(tokens)[:12]:
        for field in fields:
            condition |= Q(**{f"{field}__icontains": token})
    return queryset.filter(condition)


PROGRAM_FIELDS = ("name", "field_of_study", "department", "description", "funding_details", "university__name")
FACULTY_FIELDS = ("name", "research_areas", "department", "bio", "university__name")
FUNDING_FIELDS = ("name", "description", "eligibility", "provider", "funding_type", "university__name", "program__name")


def retrieve_context(question, profile=None):
    question_tokens = tokenize(question)
    tokens = set(question_tokens)
    if profile is not None:
        tokens |= tokenize(" ".join(filter(None, [profile.research_interests, profile.academic_interests])))

    intent = detect_intent(question)
    if _PROGRAMS_RE.search(question) and intent[0] != "programs":
        intent = ["programs"] + [kind for kind in intent if kind != "programs"]

    programs = GraduateProgram.objects.filter(is_active=True).select_related("university")
    faculty = Faculty.objects.filter(is_active=True).select_related("university")
    funding = (
        FundingOpportunity.objects.filter(is_active=True)
        .filter(Q(deadline__isnull=True) | Q(deadline__gte=date.today()))  # only funding you can still apply for
        .select_related("university", "program")
    )

    # Hard filters taken from the question.
    if question_tokens & INTERNATIONAL_WORDS:
        funding = funding.filter(international_eligible=True)
    degree_level = detect_degree_level(question)
    if degree_level:
        programs = programs.filter(degree_level=degree_level)
        faculty = faculty.filter(Q(programs__degree_level=degree_level) | Q(programs__isnull=True)).distinct()
        funding = funding.filter(Q(degree_levels="") | Q(degree_levels__icontains=degree_level))
    locations = detect_locations(question)
    if locations:
        place = Q()
        for name in locations:
            place |= Q(city__iexact=name) | Q(state_or_region__iexact=name) | Q(country__iexact=name)
        universities = University.objects.filter(place)
        programs = programs.filter(university__in=universities)
        faculty = faculty.filter(university__in=universities)
        funding = funding.filter(Q(university__in=universities) | Q(university__isnull=True))

    # Words that describe the topic (e.g. "robotics"), not the kind of record or the place.
    topic_tokens = question_tokens - GENERIC_WORDS - tokenize(" ".join(locations))

    if topic_tokens:
        context = {
            "programs": _rank(_matching(programs, topic_tokens, PROGRAM_FIELDS)[:200], tokens, _program_text),
            "faculty": _rank(_matching(faculty, topic_tokens, FACULTY_FIELDS)[:200], tokens, _faculty_text),
            "funding": _rank(_matching(funding, topic_tokens, FUNDING_FIELDS)[:200], tokens, _funding_text),
        }
    else:
        # Generic questions such as "Which PhD programs have funding?" or
        # "What scholarships are open to international students?": list the
        # records of the requested kind, ranked by the profile when available.
        context = {"programs": [], "faculty": [], "funding": []}
        wanted = {intent[0]} | ({"programs"} if _PROGRAMS_RE.search(question) else set())
        if question_tokens & FUNDING_WORDS:
            wanted.add("funding")
        if "programs" in wanted:
            programs = programs.filter(Q(application_deadline__isnull=True) | Q(application_deadline__gte=date.today()))
            if question_tokens & FUNDING_WORDS:
                programs = programs.filter(Q(funding_available=True) | Q(funding_opportunities__is_active=True)).distinct()
            context["programs"] = _rank(programs.order_by("application_deadline")[:200], tokens, _program_text, keep_unmatched=True)
        if "faculty" in wanted:
            context["faculty"] = _rank(faculty.order_by("-accepting_students", "name")[:200], tokens, _faculty_text, keep_unmatched=True)
        if "funding" in wanted:
            # "scholarships" alone means scholarships, not assistantships or fellowships.
            asked_types = {"scholarship", "fellowship", "assistantship", "grant"} & question_tokens
            if asked_types:
                funding = funding.filter(funding_type__in=asked_types)
            context["funding"] = _rank(funding.order_by("deadline")[:200], tokens, _funding_text, keep_unmatched=True)

    for kind in intent[1:]:
        context[kind] = context[kind][:MAX_SECONDARY]
    context["order"] = intent
    return context


def _money(value):
    return f"${value:,.0f}" if value is not None else "not listed"


def _ordered(context):
    return context.get("order", ["programs", "faculty", "funding"])


def format_records(context):
    sections = {"programs": [], "faculty": [], "funding": []}
    lines = sections["programs"]
    for program in context["programs"]:
        lines.append(
            f"[P{program.id}] {program.name} ({program.get_degree_level_display()}) at {program.university.name}, "
            f"{program.university.city}, {program.university.state_or_region}, {program.university.country}. "
            f"Field: {program.field_of_study}. Tuition/year: {_money(program.tuition_per_year)}. "
            f"Deadline: {program.application_deadline or 'not listed'}. Minimum GPA: {program.minimum_gpa or 'not listed'}. "
            f"Funding: {'yes' if program.funding_available else 'not listed'}. {program.funding_details} "
            f"Requirements: {program.admission_requirements} Description: {program.description} URL: {program.program_url}"
        )
    lines = sections["faculty"]
    for member in context["faculty"]:
        accepting = {True: "yes", False: "no", None: "unknown"}[member.accepting_students]
        lines.append(
            f"[F{member.id}] {member.name}, {member.title}, {member.department}, {member.university.name}. "
            f"Research areas: {member.research_areas}. Accepting students: {accepting}. {member.bio} URL: {member.profile_url}"
        )
    lines = sections["funding"]
    for item in context["funding"]:
        where = item.university.name if item.university else (item.provider or "external provider")
        lines.append(
            f"[G{item.id}] {item.name} ({item.get_funding_type_display()}) - {where}. Amount: {_money(item.amount)} {item.amount_note}. "
            f"Covers tuition: {'yes' if item.covers_tuition else 'no'}. International students eligible: {'yes' if item.international_eligible else 'no'}. "
            f"Deadline: {item.deadline or 'not listed'}. Eligibility: {item.eligibility} {item.description} URL: {item.url}"
        )
    return "\n".join(line for kind in _ordered(context) for line in sections[kind])


def sources_for(context):
    sections = {"programs": [], "faculty": [], "funding": []}
    sources = sections["programs"]
    for program in context["programs"]:
        sources.append({"type": "program", "ref": f"P{program.id}", "id": program.id,
                        "title": f"{program.name} - {program.university.name}", "url": program.program_url})
    sources = sections["faculty"]
    for member in context["faculty"]:
        sources.append({"type": "faculty", "ref": f"F{member.id}", "id": member.id,
                        "title": f"{member.name} - {member.university.name}", "url": member.profile_url})
    sources = sections["funding"]
    for item in context["funding"]:
        sources.append({"type": "funding", "ref": f"G{item.id}", "id": item.id, "title": item.name, "url": item.url})
    return [source for kind in _ordered(context) for source in sections[kind]]


def _fallback_answer(context):
    if not any(context[kind] for kind in ("programs", "faculty", "funding")):
        return (
            "I couldn't find any GradApp records related to that question. Try different keywords, "
            "such as a field of study, a city, or a type of funding."
        )
    parts = ["AI answers are not enabled on this server, so here are the GradApp records that best match your question:"]
    for kind in _ordered(context):
        if kind == "programs":
            for program in context["programs"]:
                parts.append(
                    f"- [P{program.id}] {program.name} ({program.get_degree_level_display()}) at {program.university.name}: "
                    f"tuition {_money(program.tuition_per_year)}/yr, deadline {program.application_deadline or 'not listed'}."
                )
        elif kind == "faculty":
            for member in context["faculty"]:
                parts.append(f"- [F{member.id}] {member.name}, {member.university.name}: {member.research_areas}.")
        else:
            for item in context["funding"]:
                where = item.university.name if item.university else (item.provider or "external provider")
                intl = "open to international students" if item.international_eligible else "domestic students only"
                parts.append(
                    f"- [G{item.id}] {item.name} ({item.get_funding_type_display()}, {where}): "
                    f"{_money(item.amount)} {item.amount_note}; {intl}; deadline {item.deadline or 'not listed'}."
                )
    parts.append("Verify details on the official websites linked below.")
    return "\n".join(parts)


def _web_allowed():
    return settings.AI_WEB_SEARCH_ENABLED and llm.is_configured()


def _web_answer(question, history):
    """Answer from the web and save what was found (see ``assistant.web``)."""
    from .web import search_web_and_save

    previous = [turn.get("content", "") for turn in (history or []) if turn.get("role") == "user"]
    query = question
    if previous:
        # Give follow-up questions ("what about funding there?") their context.
        query = f"Earlier question in this conversation: {previous[-1][:500]}\nCurrent question: {question}"
    result = search_web_and_save(query)
    if not result:
        return None
    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "ai_powered": True,
        "web_searched": True,
        "saved": result["saved"],
    }


def answer_question(question, profile=None, history=None, search_web=False):
    """Answer from GradApp's records; fall back to a web search when they cannot answer.

    ``search_web=True`` skips the database and searches the web directly
    (the "Search the web" button).
    """
    web_allowed = _web_allowed()
    if search_web and web_allowed:
        web = _web_answer(question, history)
        if web:
            return web

    context = retrieve_context(question, profile)
    sources = sources_for(context)
    records = format_records(context)
    has_records = bool(sources)

    if not has_records and web_allowed and not search_web:
        web = _web_answer(question, history)
        if web:
            return web

    messages = []
    for turn in (history or [])[-6:]:
        role = turn.get("role")
        content = str(turn.get("content", ""))[:2000]
        if role in {"user", "assistant"} and content:
            if messages and messages[-1]["role"] == role:
                messages[-1] = {"role": role, "content": content}  # keep turns alternating
            else:
                messages.append({"role": role, "content": content})
    if messages and messages[-1]["role"] == "user":
        messages.pop()
    profile_note = ""
    if profile is not None:
        profile_note = (
            f"\n<student_profile>Degree: {profile.get_intended_degree_level_display() or 'not set'}; "
            f"interests: {profile.academic_interests} {profile.research_interests}; "
            f"preferred locations: {profile.preferred_locations}; tuition budget: {profile.tuition_budget or 'not set'}; "
            f"funding: {profile.get_funding_requirement_display()}</student_profile>"
        )
    messages.append({
        "role": "user",
        "content": f"<records>\n{records or 'No matching records.'}\n</records>{profile_note}\n\nQuestion: {question}",
    })
    # The API requires the conversation to start with a user turn.
    while messages and messages[0]["role"] != "user":
        messages.pop(0)

    system = SYSTEM_PROMPT.format(
        today=date.today().isoformat(),
        missing_rule=MISSING_RULE_WITH_WEB if web_allowed else MISSING_RULE_NO_WEB,
    )
    answer = llm.complete(system, messages, max_tokens=700)
    if answer and answer.strip().upper().startswith(NO_ANSWER):
        web = _web_answer(question, history) if web_allowed and not search_web else None
        if web:
            return web
        answer = (
            "GradApp's records don't cover this question, and a web search didn't return an answer. "
            "Try rephrasing, or check the official university website."
        )
        return {"answer": answer, "sources": [], "ai_powered": True, "web_searched": False, "saved": []}
    if answer:
        return {"answer": answer, "sources": sources, "ai_powered": True, "web_searched": False, "saved": []}
    return {"answer": _fallback_answer(context), "sources": sources, "ai_powered": False, "web_searched": False, "saved": []}
