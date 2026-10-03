from control_layer.application.detectors.luhn import find_pans, is_valid_pan

VALID_VISA = "4532015112830366"
INVALID_VISA = "4532015112830367"


def test_is_valid_pan_accepts_luhn_valid_number() -> None:
    assert is_valid_pan(VALID_VISA) is True


def test_is_valid_pan_rejects_luhn_invalid_number() -> None:
    assert is_valid_pan(INVALID_VISA) is False


def test_is_valid_pan_rejects_non_digit_string() -> None:
    assert is_valid_pan("12ab") is False


def test_find_pans_detects_valid_card_number_in_text() -> None:
    text = f"Please charge card {VALID_VISA} for the invoice."
    matches = find_pans(text)
    assert len(matches) == 1
    assert matches[0].kind == "pan"
    assert matches[0].value == VALID_VISA
    assert text[matches[0].start : matches[0].end] == VALID_VISA


def test_find_pans_detects_spaced_and_dashed_card_numbers() -> None:
    spaced = "4532 0151 1283 0366"
    dashed = "4532-0151-1283-0366"
    assert len(find_pans(spaced)) == 1
    assert len(find_pans(dashed)) == 1


def test_find_pans_ignores_luhn_invalid_sequences() -> None:
    assert find_pans(INVALID_VISA) == []


def test_find_pans_ignores_sequences_outside_length_range() -> None:
    too_short = "123456789012"
    too_long = "12345678901234567890"
    assert find_pans(too_short) == []
    assert find_pans(too_long) == []
