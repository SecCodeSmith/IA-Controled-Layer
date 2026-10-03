from control_layer.application.detectors.iban import find_ibans, is_valid_iban

VALID_PL = "PL61109010140000071219812874"
VALID_DE = "DE89370400440532013000"
INVALID_CHECKSUM = "PL61109010140000071219812875"


def test_is_valid_iban_accepts_valid_polish_iban() -> None:
    assert is_valid_iban(VALID_PL) is True


def test_is_valid_iban_accepts_valid_german_iban() -> None:
    assert is_valid_iban(VALID_DE) is True


def test_is_valid_iban_rejects_bad_checksum() -> None:
    assert is_valid_iban(INVALID_CHECKSUM) is False


def test_is_valid_iban_rejects_too_short_value() -> None:
    assert is_valid_iban("PL123") is False


def test_find_ibans_detects_plain_iban_in_text() -> None:
    text = f"Please wire funds to {VALID_PL} before Friday."
    matches = find_ibans(text)
    assert len(matches) == 1
    assert matches[0].kind == "iban"
    assert matches[0].value == VALID_PL


def test_find_ibans_detects_spaced_iban() -> None:
    spaced = "PL61 1090 1014 0000 0712 1981 2874"
    matches = find_ibans(spaced)
    assert len(matches) == 1
    assert matches[0].value.replace(" ", "") == VALID_PL


def test_find_ibans_ignores_invalid_checksum() -> None:
    assert find_ibans(INVALID_CHECKSUM) == []
