import re

from control_layer.application.detectors.models import Match

_CANDIDATE_RE = re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)")


def is_valid_pan(digits: str) -> bool:
    if not digits.isdigit():
        return False
    total = 0
    for index, char in enumerate(reversed(digits)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def find_pans(text: str) -> list[Match]:
    matches: list[Match] = []
    for candidate in _CANDIDATE_RE.finditer(text):
        raw = candidate.group()
        digits = re.sub(r"[ -]", "", raw)
        if 13 <= len(digits) <= 19 and is_valid_pan(digits):
            matches.append(
                Match(kind="pan", start=candidate.start(), end=candidate.end(), value=raw)
            )
    return matches
