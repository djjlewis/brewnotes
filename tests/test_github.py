from pathlib import Path

import pytest

from brewnotes.github import GitHub, GitHubError

from .fakes import fake_executable


def fake_gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, api_error: str) -> None:
    """A logged-in `gh` whose `gh api` calls fail with `api_error` on stderr."""
    script = f'[ "$1" = auth ] && exit 0\necho "gh: {api_error}" >&2\nexit 1'
    fake_executable(tmp_path, monkeypatch, "gh", script)


def test_a_rate_limit_from_gh_raises_with_the_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_gh(tmp_path, monkeypatch, "API rate limit exceeded for user ID 1. (HTTP 403)")

    with pytest.raises(GitHubError, match="rate limited"):
        GitHub().releases("acme/tool", 1, 30)


def test_a_missing_repo_is_nothing_rather_than_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_gh(tmp_path, monkeypatch, "Not Found (HTTP 404)")

    assert GitHub().releases("acme/tool", 1, 30) is None
