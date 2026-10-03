from collections.abc import Callable

from control_layer.application.detectors.iban import find_ibans
from control_layer.application.detectors.luhn import find_pans
from control_layer.application.detectors.models import Match
from control_layer.application.detectors.patterns import (
    find_api_keys,
    find_emails,
    find_jwts,
    find_phones,
    find_private_keys,
)
from control_layer.application.detectors.pesel import find_pesels

DETECTORS: dict[str, Callable[[str], list[Match]]] = {
    "email": find_emails,
    "phone": find_phones,
    "pesel": find_pesels,
    "iban": find_ibans,
    "pan": find_pans,
    "api_key": find_api_keys,
    "private_key": find_private_keys,
    "jwt": find_jwts,
}
