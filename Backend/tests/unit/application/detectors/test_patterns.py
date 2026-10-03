from control_layer.application.detectors.patterns import (
    find_api_keys,
    find_emails,
    find_jwts,
    find_phones,
    find_private_keys,
)

JWT_SAMPLE = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
    "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
)

PEM_PRIVATE_KEY = (
    "-----BEGIN RSA PRIVATE KEY-----\n"
    "MIIBVgIBADANBgkqhkiG9w0BAQEFAASCAT8wggE7AgEAAkEAwqk8Q0AAAAAAAAAA\n"
    "-----END RSA PRIVATE KEY-----"
)


def test_find_emails_detects_standard_address() -> None:
    text = "Contact anna.kowalska@bank.pl for approval."
    matches = find_emails(text)
    assert len(matches) == 1
    assert matches[0].kind == "email"
    assert matches[0].value == "anna.kowalska@bank.pl"


def test_find_emails_returns_empty_when_absent() -> None:
    assert find_emails("no contact information here") == []


def test_find_phones_detects_polish_international_format() -> None:
    matches = find_phones("call +48 123 456 789 now")
    assert len(matches) == 1
    assert matches[0].kind == "phone"


def test_find_phones_detects_generic_international_format() -> None:
    matches = find_phones("reach me at +1 555-123-4567")
    assert len(matches) == 1


def test_find_phones_detects_domestic_grouped_format() -> None:
    matches = find_phones("office line 123-456-789 is open")
    assert len(matches) == 1


def test_find_phones_returns_empty_when_absent() -> None:
    assert find_phones("no numbers in this sentence") == []


def test_find_api_keys_detects_aws_key() -> None:
    matches = find_api_keys("AKIA key is AKIAIOSFODNN7EXAMPLE in the config")
    assert any(m.kind == "api_key" for m in matches)


def test_find_api_keys_detects_openai_style_key() -> None:
    text = "token sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    matches = find_api_keys(text)
    assert len(matches) == 1


def test_find_api_keys_detects_stripe_live_key() -> None:
    matches = find_api_keys("stripe key sk_live_4eC39HqLyjWDarjtT1zdp7dc here")
    assert [m.value for m in matches] == ["sk_live_4eC39HqLyjWDarjtT1zdp7dc"]


def test_find_api_keys_detects_stripe_test_key() -> None:
    assert len(find_api_keys("sk_test_4eC39HqLyjWDarjtT1zdp7dc")) == 1


def test_find_api_keys_detects_github_token() -> None:
    text = "ghp_" + "a" * 36
    matches = find_api_keys(text)
    assert len(matches) == 1


def test_find_api_keys_detects_generic_api_key_assignment() -> None:
    text = "api_key: 1234567890abcdef1234"
    matches = find_api_keys(text)
    assert len(matches) == 1


def test_find_api_keys_returns_empty_when_absent() -> None:
    assert find_api_keys("just a normal sentence") == []


def test_find_private_keys_detects_pem_block() -> None:
    matches = find_private_keys(PEM_PRIVATE_KEY)
    assert len(matches) == 1
    assert matches[0].kind == "private_key"
    assert matches[0].value.startswith("-----BEGIN")
    assert matches[0].value.endswith("-----END RSA PRIVATE KEY-----")


def test_find_private_keys_returns_empty_when_absent() -> None:
    assert find_private_keys("no keys here") == []


def test_find_jwts_detects_token() -> None:
    matches = find_jwts(f"Authorization: Bearer {JWT_SAMPLE}")
    assert len(matches) == 1
    assert matches[0].kind == "jwt"
    assert matches[0].value == JWT_SAMPLE


def test_find_jwts_returns_empty_when_absent() -> None:
    assert find_jwts("no tokens here") == []
