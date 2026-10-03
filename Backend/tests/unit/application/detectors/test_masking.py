from control_layer.application.detectors.masking import mask

VALID_PESEL = "44051401359"
VALID_PAN = "4532015112830366"


def test_mask_replaces_single_email_with_placeholder() -> None:
    result = mask("contact anna@bank.pl now", ["email"])
    assert result.text == "contact [EMAIL_1] now"
    assert result.counts == {"email": 1}


def test_mask_numbers_distinct_values_sequentially() -> None:
    text = "cc anna@bank.pl and marek@bank.pl"
    result = mask(text, ["email"])
    assert "[EMAIL_1]" in result.text
    assert "[EMAIL_2]" in result.text
    assert result.counts == {"email": 2}


def test_mask_reuses_placeholder_for_repeated_value() -> None:
    text = "anna@bank.pl wrote to anna@bank.pl"
    result = mask(text, ["email"])
    assert result.text == "[EMAIL_1] wrote to [EMAIL_1]"
    assert result.counts == {"email": 2}


def test_mask_handles_multiple_kinds_independently() -> None:
    text = f"PESEL {VALID_PESEL} card {VALID_PAN}"
    result = mask(text, ["pesel", "pan"])
    assert "[PESEL_1]" in result.text
    assert "[PAN_1]" in result.text
    assert result.counts == {"pesel": 1, "pan": 1}


def test_mask_returns_original_text_when_no_matches() -> None:
    result = mask("nothing sensitive here", ["email", "pesel"])
    assert result.text == "nothing sensitive here"
    assert result.counts == {}


def test_mask_resolves_overlap_by_keeping_longest_match() -> None:
    text = "contact user+48123456789@example.com now"
    result = mask(text, ["email", "phone"])
    assert "user+48123456789@example.com" not in result.text
    assert "[EMAIL_1]" in result.text
    assert "[PHONE_1]" not in result.text
    assert result.counts == {"email": 1}


def test_mask_returns_match_objects() -> None:
    result = mask("anna@bank.pl", ["email"])
    assert len(result.matches) == 1
    assert result.matches[0].kind == "email"
