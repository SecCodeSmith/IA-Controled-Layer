from __future__ import annotations

import base64
import json

from control_layer.presentation.api.dependencies import client_label, gateway_session_id


def _jwt(sub: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"sub": sub}).encode()).decode().rstrip("=")
    return f"h.{payload}.s"


def test_client_label_sanitizes_user_agent() -> None:
    assert client_label("GitHubCopilotChat/0.30.1") == "GitHubCopilotChat"
    assert client_label(None) == "unknown"
    assert client_label("///") == "unknown"
    assert len(client_label("a" * 80)) == 24


def test_session_prefers_explicit_header() -> None:
    assert gateway_session_id(_jwt("anna"), "my-session", "curl/8") == "my-session"


def test_session_defaults_to_subject_and_client() -> None:
    assert gateway_session_id(_jwt("anna"), None, "curl/8.4") == "gateway-anna-curl"
    assert gateway_session_id("opaque", None, None) == "gateway-unknown-unknown"
