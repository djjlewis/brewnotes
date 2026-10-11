"""The two ways of asking Claude: the `claude` CLI and the Anthropic API.

Both take a prompt and a JSON schema and return the parsed JSON object."""

import json
import re
import subprocess
import tempfile
from collections.abc import Callable
from typing import Any

Ask = Callable[[str], dict[str, Any]]


class BackendUnavailable(RuntimeError):
    """The backend can't work at all (expired login, missing key). Stop trying for this run."""


class BackendError(RuntimeError):
    """One request failed. Other requests may still work."""


def claude_cli(schema: dict[str, Any], model: str = "", web: bool = False) -> Ask:
    """Ask via `claude -p`, which uses the user's Claude Code login. `web` allows the
    WebSearch and WebFetch tools so Claude can look up notes itself."""
    cmd = ["claude", "-p", "--output-format", "json", "--json-schema", json.dumps(schema)]
    cmd += ["--no-session-persistence", "--setting-sources", "user"]
    cmd += (
        ["--tools", "WebSearch,WebFetch", "--allowedTools", "WebSearch", "WebFetch"]
        if web
        else ["--tools", ""]
    )
    cmd += ["--model", model] if model else []

    def ask(prompt: str) -> dict[str, Any]:
        # An empty working dir keeps any project CLAUDE.md or settings out of the prompt.
        with tempfile.TemporaryDirectory() as tmp:
            p = subprocess.run(
                cmd, input=prompt, capture_output=True, text=True, cwd=tmp, timeout=300, check=False
            )
        try:
            envelope = json.loads(p.stdout)
        except json.JSONDecodeError as e:
            raise BackendError(p.stderr.strip()[:300] or f"claude exited {p.returncode}") from e
        if envelope.get("is_error") or p.returncode != 0:
            msg = str(envelope.get("result") or envelope.get("terminal_reason"))[:300]
            if envelope.get("terminal_reason") == "api_error" or "authenticat" in msg.lower():
                raise BackendUnavailable(f"claude CLI: {msg}")
            raise BackendError(msg)
        out = envelope.get("structured_output")
        return out if isinstance(out, dict) else _json_in(str(envelope.get("result", "")))

    return ask


def anthropic_api(schema: dict[str, Any], model: str) -> Ask:
    """Ask via the Anthropic SDK. Credentials come from ANTHROPIC_API_KEY or an `ant auth login` profile."""
    import anthropic

    try:
        client = anthropic.Anthropic()
    except anthropic.AnthropicError as e:
        raise BackendUnavailable(f"Anthropic API: {e}") from e

    def ask(prompt: str) -> dict[str, Any]:
        try:
            response = client.beta.messages.create(
                model=model,
                max_tokens=4096,
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
                # Security-heavy notes can trip a safety classifier. Let the API retry on a
                # fallback model instead of returning nothing.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=[{"role": "user", "content": prompt}],
            )
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            raise BackendUnavailable(f"Anthropic API: {e}") from e
        except anthropic.APIError as e:
            raise BackendError(str(e)) from e
        if response.stop_reason == "refusal":
            raise BackendError("model declined")
        text = next((b.text for b in response.content if b.type == "text"), "")
        return _json_in(text)

    return ask


def _json_in(text: str) -> dict[str, Any]:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise BackendError(f"no JSON in response: {text[:200]}")
    data = json.loads(m.group(0))
    if not isinstance(data, dict):
        raise BackendError("response JSON is not an object")
    return data
