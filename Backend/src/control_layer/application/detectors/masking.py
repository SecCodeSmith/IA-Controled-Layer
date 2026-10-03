from dataclasses import dataclass

from control_layer.application.detectors.models import Match
from control_layer.application.detectors.registry import DETECTORS

_PLACEHOLDER_NAMES: dict[str, str] = {
    "email": "EMAIL",
    "phone": "PHONE",
    "pesel": "PESEL",
    "iban": "IBAN",
    "pan": "PAN",
    "api_key": "API_KEY",
    "private_key": "PRIVATE_KEY",
    "jwt": "JWT",
}


@dataclass(frozen=True, slots=True)
class MaskResult:
    text: str
    counts: dict[str, int]
    matches: list[Match]


def _select_non_overlapping(matches: list[Match]) -> list[Match]:
    by_length_desc = sorted(matches, key=lambda m: (-(m.end - m.start), m.start))
    selected: list[Match] = []
    for match in by_length_desc:
        if not any(match.start < other.end and other.start < match.end for other in selected):
            selected.append(match)
    return sorted(selected, key=lambda m: m.start)


def mask(text: str, kinds: list[str]) -> MaskResult:
    all_matches: list[Match] = []
    for kind in kinds:
        all_matches.extend(DETECTORS[kind](text))

    selected = _select_non_overlapping(all_matches)

    counts: dict[str, int] = {}
    for match in selected:
        counts[match.kind] = counts.get(match.kind, 0) + 1

    placeholder_numbers: dict[tuple[str, str], int] = {}
    next_number: dict[str, int] = {}
    pieces: list[str] = []
    cursor = 0
    for match in selected:
        key = (match.kind, match.value)
        if key not in placeholder_numbers:
            next_number[match.kind] = next_number.get(match.kind, 0) + 1
            placeholder_numbers[key] = next_number[match.kind]
        placeholder = f"[{_PLACEHOLDER_NAMES[match.kind]}_{placeholder_numbers[key]}]"
        pieces.append(text[cursor : match.start])
        pieces.append(placeholder)
        cursor = match.end
    pieces.append(text[cursor:])

    return MaskResult(text="".join(pieces), counts=counts, matches=selected)
