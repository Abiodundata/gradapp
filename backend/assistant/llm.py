"""Thin wrapper around the OpenAI API.

Every AI feature in GradApp (Ask AI answers, recommendation summaries and
program-information extraction) goes through ``complete``. When no API key is
configured, or the API call fails, ``complete`` returns ``None`` and callers
fall back to rule-based behaviour, so the application keeps working.
"""

import logging

from django.conf import settings


logger = logging.getLogger(__name__)

_client = None

DEFAULT_BASE_URL = "https://api.openai.com/v1"


def is_configured():
    return bool(settings.OPENAI_API_KEY)


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            # Always pass an explicit URL: if OPENAI_BASE_URL exists but is empty
            # (as Docker Compose sets it when unused), the SDK would otherwise use "".
            base_url=settings.OPENAI_BASE_URL.strip() or DEFAULT_BASE_URL,
            timeout=settings.AI_TIMEOUT_SECONDS,
            max_retries=1,
        )
    return _client


def complete(system, messages, max_tokens=700):
    """Return the model's text reply, or ``None`` if AI is unavailable.

    ``messages`` is a list of {"role": "user" | "assistant", "content": str}.
    The system prompt is sent as the first message.
    """
    if not is_configured():
        return None
    try:
        response = _get_client().chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "system", "content": system}, *messages],
            # Reasoning models count hidden reasoning tokens against this limit,
            # so leave headroom beyond the visible answer length.
            max_completion_tokens=max_tokens + settings.AI_REASONING_TOKEN_HEADROOM,
        )
    except Exception as exc:  # network errors, rate limits, invalid key, unknown model, etc.
        logger.warning("AI request failed: %s", exc)
        return None
    if not response.choices:
        return None
    text = (response.choices[0].message.content or "").strip()
    return text or None


def web_search(instructions, question, max_tokens=900):
    """Search the web with OpenAI's built-in ``web_search`` tool (Responses API).

    Returns ``{"text": str, "citations": [{"url", "title"}]}`` or ``None`` when
    AI is not configured or the request fails.
    """
    if not is_configured():
        return None
    try:
        response = _get_client().responses.create(
            model=settings.OPENAI_MODEL,
            instructions=instructions,
            input=question,
            tools=[{"type": "web_search"}],
            max_output_tokens=max_tokens + settings.AI_REASONING_TOKEN_HEADROOM,
            timeout=settings.AI_WEB_SEARCH_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning("AI web search failed: %s", exc)
        return None

    citations, seen = [], set()
    for item in getattr(response, "output", None) or []:
        if getattr(item, "type", "") != "message":
            continue
        for part in getattr(item, "content", None) or []:
            for annotation in getattr(part, "annotations", None) or []:
                if getattr(annotation, "type", "") != "url_citation":
                    continue
                url = clean_url(annotation.url)
                if url and url not in seen:
                    seen.add(url)
                    citations.append({"url": url, "title": (annotation.title or url)[:300]})
    text = (getattr(response, "output_text", "") or "").strip()
    if not text:
        return None
    return {"text": text, "citations": citations}


def clean_url(url):
    """Drop tracking parameters such as ?utm_source=openai from cited URLs."""
    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

    if not url:
        return ""
    parsed = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(parsed.query) if not k.lower().startswith("utm_")]
    return urlunparse(parsed._replace(query=urlencode(query)))
