import re


INCOMPLETE_RESPONSE_FALLBACK = (
    "I started to answer, but the local model returned an incomplete response. "
    "Try again or rephrase and I'll rerun it."
)

FRAGMENT_PREFIXES = {
    "based",
    "based on",
    "the",
    "it",
    "i",
    "here",
    "sure",
    "because",
    "given",
}

UNFINISHED_ENDINGS = (
    "based on",
    "because",
    "given",
    "here is",
    "here are",
    "for example",
    "such as",
    "including",
    "if",
    "when",
    "while",
    "and",
    "or",
    "but",
    "so",
    "to",
    "with",
    "from",
    "about",
)

LEGIT_SHORT_RESPONSES = {
    "yes",
    "yes.",
    "no",
    "no.",
    "done",
    "done.",
    "saved",
    "saved.",
    "ok",
    "ok.",
    "okay",
    "okay.",
    "speaking now",
    "speaking now.",
}

TINY_REQUEST_PATTERNS = (
    r"\b(answer|reply|respond)\s+(yes|no)\b",
    r"\byes or no\b",
    r"\bone word\b",
    r"\bbriefly\b",
    r"\bquick answer\b",
)


def _compact_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _normalize_short_text(text: str | None) -> str:
    return _compact_text(text).lower()


def user_requested_tiny_answer(user_message: str | None) -> bool:
    normalized = _normalize_short_text(user_message)
    if not normalized:
        return False

    return any(re.search(pattern, normalized) for pattern in TINY_REQUEST_PATTERNS)


def is_incomplete_response(
    response: str | None,
    *,
    user_message: str | None = None,
    allow_short_response: bool = False,
) -> bool:
    text = _compact_text(response)
    normalized = text.lower().strip("\"'`“”‘’")

    if not text:
        return True

    if normalized in LEGIT_SHORT_RESPONSES:
        return False

    if allow_short_response or user_requested_tiny_answer(user_message):
        return False

    if normalized in FRAGMENT_PREFIXES:
        return True

    words = re.findall(r"[A-Za-z0-9']+", text)
    if len(words) <= 2:
        return True

    if len(text) < 24:
        return True

    stripped = normalized.rstrip(".!?;:,- ")
    if any(stripped.endswith(ending) for ending in UNFINISHED_ENDINGS):
        return True

    return False


def build_response_repair_prompt(
    *,
    base_prompt: str,
    user_message: str,
    bad_response: str,
) -> str:
    return (
        base_prompt
        + "\n\nThe previous assistant response was incomplete and must not be used.\n"
        + f"User message: {user_message}\n"
        + f"Incomplete response: {bad_response}\n\n"
        + "Answer the user's message fully. Do not start with a dangling fragment. "
        + "If the question depends on current news or market claims you cannot verify, "
        + "say that clearly and frame your take conditionally.\n"
        + "Assistant:"
    )
