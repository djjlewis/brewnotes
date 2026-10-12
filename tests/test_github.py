from pathlib import Path

import pytest

from brewnotes.github import GitHub
from brewnotes.sources import RATE_LIMITED, FetchError

from .fakes import fake_executable


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Anonymous requests go through a dead proxy, so a test can never reach GitHub."""
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")


def fake_gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, api: str, auth: str = "exit 0") -> None:
    """A stand-in `gh`: `gh auth ...` runs `auth`, `gh api ...` runs `api`."""
    script = f'if [ "$1" = auth ]; then\n{auth}\nfi\n{api}'
    fake_executable(tmp_path, monkeypatch, "gh", script)


def api_error(message: str) -> str:
    return f'echo "gh: {message}" >&2\nexit 1'


def test_a_rate_limit_from_gh_raises_with_the_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_gh(tmp_path, monkeypatch, api_error("API rate limit exceeded for user ID 1. (HTTP 403)"))

    with pytest.raises(FetchError, match=RATE_LIMITED):
        GitHub().releases("acme/tool", 1, 30)


def test_a_missing_repo_is_nothing_rather_than_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_gh(tmp_path, monkeypatch, api_error("Not Found (HTTP 404)"))

    assert GitHub().releases("acme/tool", 1, 30) is None


def test_a_server_error_is_retried_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    marker = tmp_path / "called-once"
    first_fails = (
        f'if [ ! -e {marker} ]; then touch {marker}; {api_error("Bad Gateway (HTTP 502)")}; fi\necho "[]"'
    )
    fake_gh(tmp_path, monkeypatch, first_fails)

    assert GitHub().releases("acme/tool", 1, 30) == []


def test_a_logged_out_gh_falls_back_to_anonymous_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_gh(tmp_path, monkeypatch, api='echo "[]"', auth="exit 1")

    with pytest.raises(FetchError, match="network error"):  # the dead proxy, so not `gh`
        GitHub().releases("acme/tool", 1, 30)


def test_only_the_github_com_login_matters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    other_host_stale = 'case "$*" in *"--hostname github.com"*) exit 0;; esac\nexit 1'
    fake_gh(tmp_path, monkeypatch, api='echo "[]"', auth=other_host_stale)

    assert GitHub().releases("acme/tool", 1, 30) == []
