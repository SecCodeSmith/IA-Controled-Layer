import re

from control_layer.application.detectors.models import Match

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

_PHONE_INTL_RE = re.compile(
    r"(?<!\d)\+\d{1,3}[\s-]?(?:\(\d{1,4}\)[\s-]?)?\d{2,4}(?:[\s-]?\d{2,4}){1,3}(?!\d)"
)
_PHONE_PL_DOMESTIC_RE = re.compile(r"(?<!\d)\d{3}[\s-]\d{3}[\s-]\d{3}(?!\d)")

_AWS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")
_STRIPE_KEY_RE = re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}\b")
_GITHUB_KEY_RE = re.compile(r"\bghp_[A-Za-z0-9]{36}\b")
_GENERIC_API_KEY_RE = re.compile(r"\bapi[_-]?key\s*[:=]\s*\S{16,}", re.IGNORECASE)

_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)

_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")


def find_emails(text: str) -> list[Match]:
    return [
        Match(kind="email", start=m.start(), end=m.end(), value=m.group())
        for m in _EMAIL_RE.finditer(text)
    ]


def _drop_overlapping(spans: list[re.Match[str]]) -> list[re.Match[str]]:
    by_length_desc = sorted(spans, key=lambda m: (-(m.end() - m.start()), m.start()))
    kept: list[re.Match[str]] = []
    for span in by_length_desc:
        if not any(span.start() < other.end() and other.start() < span.end() for other in kept):
            kept.append(span)
    return sorted(kept, key=lambda m: m.start())


def find_phones(text: str) -> list[Match]:
    spans: list[re.Match[str]] = list(_PHONE_INTL_RE.finditer(text))
    spans += list(_PHONE_PL_DOMESTIC_RE.finditer(text))
    spans = _drop_overlapping(spans)
    return [Match(kind="phone", start=m.start(), end=m.end(), value=m.group()) for m in spans]


def find_api_keys(text: str) -> list[Match]:
    spans: list[re.Match[str]] = []
    key_patterns = (
        _AWS_KEY_RE,
        _OPENAI_KEY_RE,
        _STRIPE_KEY_RE,
        _GITHUB_KEY_RE,
        _GENERIC_API_KEY_RE,
    )
    for pattern in key_patterns:
        spans.extend(pattern.finditer(text))
    spans.sort(key=lambda m: m.start())
    return [Match(kind="api_key", start=m.start(), end=m.end(), value=m.group()) for m in spans]


def find_private_keys(text: str) -> list[Match]:
    return [
        Match(kind="private_key", start=m.start(), end=m.end(), value=m.group())
        for m in _PRIVATE_KEY_RE.finditer(text)
    ]


def find_jwts(text: str) -> list[Match]:
    return [
        Match(kind="jwt", start=m.start(), end=m.end(), value=m.group())
        for m in _JWT_RE.finditer(text)
    ]
