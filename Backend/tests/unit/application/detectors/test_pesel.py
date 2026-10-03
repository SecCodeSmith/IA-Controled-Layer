from control_layer.application.detectors.pesel import find_pesels, is_valid_pesel

VALID_PESEL = "44051401359"
INVALID_CHECKSUM = "44051401350"
INVALID_DATE = "44131401359"


def test_is_valid_pesel_accepts_valid_number() -> None:
    assert is_valid_pesel(VALID_PESEL) is True


def test_is_valid_pesel_rejects_bad_checksum() -> None:
    assert is_valid_pesel(INVALID_CHECKSUM) is False


def test_is_valid_pesel_rejects_invalid_month() -> None:
    assert is_valid_pesel(INVALID_DATE) is False


def test_is_valid_pesel_rejects_wrong_length() -> None:
    assert is_valid_pesel("123") is False


def test_find_pesels_detects_valid_pesel_in_text() -> None:
    text = f"Employee PESEL: {VALID_PESEL}, department: HR"
    matches = find_pesels(text)
    assert len(matches) == 1
    assert matches[0].kind == "pesel"
    assert matches[0].value == VALID_PESEL


def test_find_pesels_ignores_invalid_candidates() -> None:
    assert find_pesels(INVALID_CHECKSUM) == []


def test_find_pesels_not_reported_as_phone() -> None:
    from control_layer.application.detectors.patterns import find_phones

    text = f"PESEL {VALID_PESEL} on file."
    assert find_pesels(text)
    assert find_phones(text) == []
