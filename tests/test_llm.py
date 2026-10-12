import json
from pathlib import Path

import pytest

from brewnotes.llm import BackendError, BackendUnavailable, anthropic_api, claude_cli
from brewnotes.triage import SCHEMA

from .fakes import fake_executable

AUTH_VARS = ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE", "ANTHROPIC_FEDERATION_RULE_ID"]


def fake_claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, script: str) -> None:
    fake_executable(tmp_path, monkeypatch, "claude", script)


def error_envelope(result: str) -> str:
    envelope = {"type": "result", "is_error": True, "terminal_reason": "api_error", "result": result}
    return f"cat <<'EOF'\n{json.dumps(envelope)}\nEOF\nexit 1"


def test_a_hung_claude_call_fails_only_that_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_claude(tmp_path, monkeypatch, "sleep 5")

    with pytest.raises(BackendError):
        claude_cli(SCHEMA, timeout=0.2)("prompt")


@pytest.mark.parametrize("message", ["API Error: 529 Overloaded", "Rate limit exceeded for this API key"])
def test_a_transient_api_error_fails_only_that_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, message: str
) -> None:
    fake_claude(tmp_path, monkeypatch, error_envelope(message))

    with pytest.raises(BackendError):
        claude_cli(SCHEMA)("prompt")


def test_a_missing_claude_stops_the_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))

    with pytest.raises(BackendUnavailable, match="not found"):
        claude_cli(SCHEMA)("prompt")


def test_an_expired_login_stops_the_backend_and_says_how_to_fix_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_claude(tmp_path, monkeypatch, error_envelope("Failed to authenticate: OAuth session expired"))

    with pytest.raises(BackendUnavailable, match="/login"):
        claude_cli(SCHEMA)("prompt")


def test_the_api_without_credentials_stops_the_backend_and_names_the_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for var in AUTH_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    # If the SDK ever finds credentials somewhere else, fail locally instead of calling the API.
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:9")

    with pytest.raises(BackendUnavailable, match="ANTHROPIC_API_KEY"):
        anthropic_api(SCHEMA, "claude-opus-5-5")("prompt")
