"""Small, dependency-free text helpers used for matching profiles to records.

The matching is intentionally simple and explainable: text is lower-cased,
split into words, stop words are removed, and words are reduced to a crude
stem so that "robotics" and "robot" or "learning" and "learn" match. Common
multi-word phrases (e.g. "machine learning") are also kept as single terms so
they can be reported back to the user as the reason for a match.
"""

import re

STOP_WORDS = {
    "a", "about", "after", "all", "also", "an", "and", "any", "are", "as", "at",
    "be", "been", "but", "by", "can", "could", "degree", "do", "does", "for",
    "from", "get", "graduate", "has", "have", "how", "i", "in", "interested",
    "into", "is", "it", "its", "me", "more", "most", "my", "near", "not", "of",
    "on", "or", "other", "our", "program", "programs", "school", "should", "so",
    "some", "study", "studies", "than", "that", "the", "their", "them", "there",
    "these", "they", "this", "to", "university", "universities", "want", "was",
    "what", "when", "where", "which", "who", "why", "will", "with", "would",
    "you", "your", "ms", "phd", "master", "masters", "doctoral", "doctorate",
    "student", "students", "like", "good", "best", "find", "show", "list",
    "work", "field", "area", "areas", "research", "science", "sciences",
}

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9+#\-]*")


def stem(word):
    """Very small suffix-stripping stemmer (good enough for keyword matching)."""
    for suffix in ("ations", "ation", "ings", "ing", "ics", "ies", "ers", "ed", "er", "es", "s", "al"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            if suffix == "ies":
                return word[: -len(suffix)] + "y"
            return word[: -len(suffix)]
    return word


def tokenize(text):
    """Return the set of stemmed, meaningful words in ``text``."""
    if not text:
        return set()
    words = _WORD_RE.findall(str(text).lower())
    return {stem(word.strip("-")) for word in words if word not in STOP_WORDS and len(word) > 1}


def phrases(text):
    """Split comma/semicolon/newline separated lists into normalised phrases."""
    if not text:
        return []
    parts = re.split(r"[,;\n/]+", str(text).lower())
    return [part.strip() for part in parts if part.strip()]


def overlap(query_tokens, text):
    """Return the stemmed query words that also appear in ``text``."""
    if not query_tokens:
        return set()
    return query_tokens & tokenize(text)


def matched_phrases(profile_text, candidate_text):
    """Return human-readable phrases from ``candidate_text`` that match the profile.

    Used to explain *why* something matched, e.g. "machine learning".
    """
    profile_tokens = tokenize(profile_text)
    matches = []
    for phrase in phrases(candidate_text):
        if tokenize(phrase) & profile_tokens:
            matches.append(phrase)
    return matches


def original_words(stems, text):
    """Return the readable words in ``text`` whose stem is in ``stems`` (for explanations)."""
    seen, words = set(), []
    for word in _WORD_RE.findall(str(text or "").lower()):
        if word in STOP_WORDS:
            continue
        key = stem(word.strip("-"))
        if key in stems and key not in seen:
            seen.add(key)
            words.append(word)
    return words
