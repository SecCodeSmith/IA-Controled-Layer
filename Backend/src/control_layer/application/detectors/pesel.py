import re

from control_layer.application.detectors.models import Match

_CANDIDATE_RE = re.compile(r"(?<!\d)\d{11}(?!\d)")
_WEIGHTS = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
_MONTH_CENTURY_OFFSETS = (0, 20, 40, 60, 80)


def _has_valid_date_part(pesel: str) -> bool:
    month_raw = int(pesel[2:4])
    day = int(pesel[4:6])
    month = month_raw % 20
    century_index = month_raw // 20
    if not (1 <= month <= 12) or century_index >= len(_MONTH_CENTURY_OFFSETS):
        return False
    return 1 <= day <= 31


def is_valid_pesel(pesel: str) -> bool:
    if len(pesel) != 11 or not pesel.isdigit():
        return False
    checksum = sum(int(digit) * weight for digit, weight in zip(pesel, _WEIGHTS, strict=False))
    control = (10 - checksum % 10) % 10
    if control != int(pesel[10]):
        return False
    return _has_valid_date_part(pesel)


def find_pesels(text: str) -> list[Match]:
    matches: list[Match] = []
    for candidate in _CANDIDATE_RE.finditer(text):
        raw = candidate.group()
        if is_valid_pesel(raw):
            matches.append(
                Match(kind="pesel", start=candidate.start(), end=candidate.end(), value=raw)
            )
    return matches
