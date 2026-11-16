"""Retrieve Program Information use case.

Fetches a program's official web page, extracts the facts GradApp cares
about (tuition, application deadline, minimum GPA, funding, admission
requirements) and stores a dated ``SourceSnapshot`` so users can see when the
information was last verified and where it came from.

Safety measures:
* Only http/https URLs that resolve to public IP addresses are fetched
  (prevents server-side request forgery against internal services).
* robots.txt is respected.
* Responses are size-limited and time-limited.
"""

import ipaddress
import json
import logging
import re
import socket
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.utils import timezone

from assistant import llm

from .models import GraduateProgram, SourceSnapshot


logger = logging.getLogger(__name__)

EXCERPT_LIMIT = 20000


class RetrievalBlocked(Exception):
    """The URL must not be fetched (unsafe address or disallowed by robots.txt)."""


# --------------------------------------------------------------------------
# URL safety
# --------------------------------------------------------------------------

def validate_public_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RetrievalBlocked("Only http and https URLs can be retrieved.")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise requests.ConnectionError(f"Could not resolve host {parsed.hostname}.") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            raise RetrievalBlocked("The URL points to a private or reserved network address.")


def robots_allows(url, session):
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    try:
        response = session.get(robots_url, timeout=settings.RETRIEVAL_TIMEOUT_SECONDS)
    except requests.RequestException:
        return True  # robots.txt unreachable: treat as allowed, like most crawlers
    if response.status_code in (401, 403):
        return False
    if response.status_code >= 400:
        return True
    parser.parse(response.text.splitlines())
    return parser.can_fetch(settings.RETRIEVAL_USER_AGENT, url)


def fetch_html(url, session=None):
    """Return (status_code, html_text) for a public URL, enforcing size limits."""
    session = session or requests.Session()
    session.headers.update({"User-Agent": settings.RETRIEVAL_USER_AGENT})
    validate_public_url(url)
    if not robots_allows(url, session):
        raise RetrievalBlocked("robots.txt does not allow GradApp to fetch this page.")

    current_url = url
    for _ in range(5):  # follow redirects manually so every hop is validated
        response = session.get(
            current_url,
            timeout=settings.RETRIEVAL_TIMEOUT_SECONDS,
            allow_redirects=False,
            stream=True,
        )
        if response.is_redirect and response.headers.get("location"):
            current_url = urljoin(current_url, response.headers["location"])
            validate_public_url(current_url)
            response.close()
            continue
        break
    else:
        raise requests.TooManyRedirects("Too many redirects.")

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type and "text" not in content_type:
        response.close()
        raise requests.RequestException(f"Unsupported content type: {content_type or 'unknown'}.")

    chunks, size = [], 0
    for chunk in response.iter_content(chunk_size=65536):
        size += len(chunk)
        if size > settings.RETRIEVAL_MAX_BYTES:
            break
        chunks.append(chunk)
    response.close()
    encoding = response.encoding or "utf-8"
    return response.status_code, b"".join(chunks).decode(encoding, errors="replace")


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def html_to_text(html):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)
    text = re.sub(r"\n{2,}", "\n", text)
    return title[:500], text


_MONEY_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d{3,6})(?:\.\d{2})?")
_GPA_RE = re.compile(
    r"(?:minimum|min\.?|at least|cumulative)\s+(?:undergraduate\s+)?(?:gpa|grade point average)"
    r"[^0-9]{0,40}([0-4]\.\d{1,2})"
    r"|([0-4]\.\d{1,2})\s*(?:/\s*4\.0\s*)?(?:minimum\s+)?(?:gpa|grade point average)",
    re.IGNORECASE,
)
_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december|"
    "jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)
_DATE_RE = re.compile(
    rf"\b(?:(?:{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}|\d{{1,2}}/\d{{1,2}}/\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})\b",
    re.IGNORECASE,
)
_FUNDING_RE = re.compile(r"assistantship|fellowship|scholarship|stipend|tuition waiver", re.IGNORECASE)


def _parse_date(raw):
    cleaned = re.sub(r"(\d)(st|nd|rd|th)", r"\1", raw.replace(".", "").replace(",", "")).strip()
    cleaned = cleaned.replace("Sept ", "Sep ").replace("sept ", "sep ")
    for fmt in ("%B %d %Y", "%b %d %Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _near(text, keyword_pattern, value_pattern, window=160):
    """Find the first ``value_pattern`` match within ``window`` chars after a keyword."""
    for keyword in re.finditer(keyword_pattern, text, re.IGNORECASE):
        segment = text[keyword.start(): keyword.end() + window]
        match = value_pattern.search(segment)
        if match:
            return match
    return None


def extract_with_rules(text):
    """Heuristic extraction that works without any AI service."""
    facts = {}

    money = _near(text, r"tuition", _MONEY_RE)
    if money:
        try:
            facts["tuition_per_year"] = str(Decimal(money.group(1).replace(",", "")))
        except InvalidOperation:
            pass

    deadline = _near(text, r"deadline|apply by|applications? due|priority date", _DATE_RE, window=120)
    if deadline:
        parsed = _parse_date(deadline.group(0))
        if parsed:
            facts["application_deadline"] = parsed.isoformat()

    gpa = _GPA_RE.search(text)
    if gpa:
        value = gpa.group(1) or gpa.group(2)
        try:
            number = Decimal(value)
            if 0 < number <= 4:
                facts["minimum_gpa"] = str(number)
        except InvalidOperation:
            pass

    if _FUNDING_RE.search(text):
        facts["funding_available"] = True
        funding_sentence = re.search(r"[^.\n]*(?:assistantship|fellowship|scholarship|stipend)[^.\n]*\.", text, re.IGNORECASE)
        if funding_sentence:
            facts["funding_details"] = funding_sentence.group(0).strip()[:600]

    requirements = re.search(
        r"(?:admission requirements?|requirements for admission)[:\s]*\n?((?:.+\n?){1,8})",
        text,
        re.IGNORECASE,
    )
    if requirements:
        facts["admission_requirements"] = requirements.group(1).strip()[:1500]

    return facts


EXTRACTION_PROMPT = """You extract facts about one graduate program from the text of its official web page.
Return ONLY a JSON object with these keys (use null when the page does not clearly state a value; never guess):
{
  "tuition_per_year": number or null,       // annual tuition in the page's currency, digits only
  "application_deadline": "YYYY-MM-DD" or null, // the main/fall application deadline
  "minimum_gpa": number or null,            // on a 4.0 scale
  "funding_available": true/false/null,
  "funding_details": string or null,        // one or two sentences
  "admission_requirements": string or null, // short bullet-style summary, max 600 characters
  "description": string or null             // one or two sentence program summary
}"""


def extract_with_ai(program, text):
    reply = llm.complete(
        system=EXTRACTION_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Program: {program.name} ({program.get_degree_level_display()}) at {program.university.name}\n\nPage text:\n{text[:15000]}",
        }],
        max_tokens=800,
    )
    if not reply:
        return None
    match = re.search(r"\{.*\}", reply, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return {key: value for key, value in data.items() if value not in (None, "")}


# --------------------------------------------------------------------------
# Applying results
# --------------------------------------------------------------------------

APPLICABLE_FIELDS = (
    "tuition_per_year",
    "application_deadline",
    "minimum_gpa",
    "funding_available",
    "funding_details",
    "admission_requirements",
    "description",
)


def _coerce(field, value):
    if field in ("tuition_per_year", "minimum_gpa"):
        number = Decimal(str(value).replace(",", "").replace("$", ""))
        if number < 0 or (field == "minimum_gpa" and number > 4):
            raise ValueError
        return number
    if field == "application_deadline":
        return value if isinstance(value, date) else date.fromisoformat(str(value))
    if field == "funding_available":
        return bool(value)
    return str(value).strip()


def retrieve_program_information(program: GraduateProgram, apply=True, session=None):
    """Fetch the program's official page, extract facts and record a snapshot."""
    snapshot = SourceSnapshot(program=program, url=program.program_url)
    try:
        status_code, html = fetch_html(program.program_url, session=session)
        snapshot.http_status = status_code
        if status_code >= 400:
            raise requests.HTTPError(f"The page returned HTTP {status_code}.")
        title, text = html_to_text(html)
        snapshot.page_title = title
        snapshot.content_excerpt = text[:EXCERPT_LIMIT]

        extracted = extract_with_ai(program, text) if llm.is_configured() else None
        if extracted is not None:
            snapshot.extraction_method = "ai"
        else:
            extracted = extract_with_rules(text)
            snapshot.extraction_method = "rules"
        snapshot.extracted = extracted
        snapshot.status = SourceSnapshot.Status.SUCCESS

        if apply:
            applied, previous = [], {}
            for field in APPLICABLE_FIELDS:
                if field not in extracted:
                    continue
                try:
                    value = _coerce(field, extracted[field])
                except (ValueError, InvalidOperation, TypeError):
                    continue
                current = getattr(program, field)
                if current != value:
                    previous[field] = str(current) if current is not None else None
                    setattr(program, field, value)
                    applied.append(field)
            snapshot.applied_fields = applied
            if previous:
                snapshot.extracted = {**extracted, "_previous_values": previous}
            program.source_retrieved_at = timezone.now()
            program.save()
    except RetrievalBlocked as exc:
        snapshot.status = SourceSnapshot.Status.BLOCKED
        snapshot.error = str(exc)
    except (requests.RequestException, ValueError, UnicodeError) as exc:
        snapshot.status = SourceSnapshot.Status.FAILED
        snapshot.error = str(exc) or exc.__class__.__name__
        logger.warning("Retrieval failed for %s: %s", program.program_url, snapshot.error)
    snapshot.save()
    return snapshot
