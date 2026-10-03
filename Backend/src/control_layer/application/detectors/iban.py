import re

from control_layer.application.detectors.models import Match

_CANDIDATE_RE = re.compile(r"\b[A-Z]{2}[ -]?\d{2}(?:[ -]?[A-Z0-9]){10,30}\b", re.IGNORECASE)
_COUNTRY_LENGTHS: dict[str, int] = {
    "PL": 28,
    "DE": 22,
    "FR": 27,
    "GB": 22,
}


def is_valid_iban(iban: str) -> bool:
    candidate = iban.replace(" ", "").replace("-", "").upper()
    if len(candidate) < 15 or len(candidate) > 34:
        return False
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]+", candidate):
        return False
    country = candidate[:2]
    expected_length = _COUNTRY_LENGTHS.get(country)
    if expected_length is not None and len(candidate) != expected_length:
        return False
    rearranged = candidate[4:] + candidate[:4]
    numeric = "".join(str(int(ch, 36)) if ch.isalpha() else ch for ch in rearranged)
    return int(numeric) % 97 == 1


def find_ibans(text: str) -> list[Match]:
    matches: list[Match] = []
    for candidate in _CANDIDATE_RE.finditer(text):
        start = candidate.start()
        value = candidate.group()
        while len(value) >= 15:
            stripped = value.rstrip(" -")
            if is_valid_iban(stripped):
                matches.append(
                    Match(kind="iban", start=start, end=start + len(stripped), value=stripped)
                )
                break
            value = value[:-1]
    return matches
