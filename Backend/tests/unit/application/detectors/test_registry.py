from control_layer.application.detectors.registry import DETECTORS

EXPECTED_KEYS = {"email", "phone", "pesel", "iban", "pan", "api_key", "private_key", "jwt"}


def test_registry_exposes_expected_kinds() -> None:
    assert set(DETECTORS.keys()) == EXPECTED_KEYS


def test_registry_entries_are_callable_and_return_list() -> None:
    for finder in DETECTORS.values():
        assert callable(finder)
        assert finder("no match here") == []
