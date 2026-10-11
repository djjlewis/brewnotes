from pathlib import Path
from typing import Any

from brewnotes.brew import Change
from brewnotes.llm import Ask, BackendError, BackendUnavailable
from brewnotes.sources import Notes
from brewnotes.triage import Triager

ANSWER = {
    "severity": "breaking",
    "tldr": "Config moved.",
    "highlights": ["moved ~/.foo to ~/.config/foo"],
    "action_needed": "Move your config.",
    "cves": [],
    "notes_url": "",
}


def answers(*results: dict[str, Any] | Exception) -> Ask:
    """A fake LLM: returns or raises each result in turn."""
    queue = list(results)

    def ask(prompt: str) -> dict[str, Any]:
        r = queue.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    return ask


def change(name: str = "tool", old: str = "1.2.0", new: str = "1.3.0") -> Change:
    return Change(name=name, kind="formula", old=old, new=new)


NOTES = Notes(repo="acme/tool", text="## v1.3.0\nMoved the config file.", source="releases")


def test_uses_the_llm_answer(tmp_path: Path) -> None:
    t = Triager("claude-cli", answers(ANSWER), None, tmp_path).triage(change(), NOTES)

    assert (t.severity, t.tldr, t.action_needed) == ("breaking", "Config moved.", "Move your config.")


def test_reuses_a_cached_answer_for_the_same_range_and_notes(tmp_path: Path) -> None:
    Triager("claude-cli", answers(ANSWER), None, tmp_path).triage(change(), NOTES)

    t = Triager("claude-cli", answers(BackendError("should not be asked")), None, tmp_path).triage(
        change(), NOTES
    )

    assert t.tldr == "Config moved."


def test_unavailable_backend_falls_back_to_heuristics_for_the_rest_of_the_run(tmp_path: Path) -> None:
    triager = Triager("claude-cli", answers(BackendUnavailable("login expired"), ANSWER), None, tmp_path)

    first = triager.triage(change("a"), NOTES)
    second = triager.triage(change("b"), NOTES)

    assert (first.by, second.by, triager.problem) == ("heuristic", "heuristic", "login expired")


def test_one_failed_request_falls_back_for_that_package_only(tmp_path: Path) -> None:
    triager = Triager("claude-cli", answers(BackendError("timeout"), ANSWER), None, tmp_path)

    failed = triager.triage(change("a"), NOTES)
    ok = triager.triage(change("b"), NOTES)

    assert failed.by == "heuristic" and "LLM triage failed: timeout" in failed.tldr
    assert ok.by == "claude-cli"


def test_missing_notes_go_to_web_lookup(tmp_path: Path) -> None:
    from_web = {**ANSWER, "notes_url": "https://example.com/releases"}
    triager = Triager("claude-cli", answers(ANSWER), answers(from_web), tmp_path)

    t = triager.triage(change(), Notes())

    assert t.notes_url == "https://example.com/releases"


def test_missing_notes_without_web_lookup_skip_the_llm(tmp_path: Path) -> None:
    triager = Triager("api", answers(BackendError("should not be asked")), None, tmp_path)

    t = triager.triage(change(), Notes())

    assert (t.severity, t.tldr) == ("unknown", "No release notes found.")
