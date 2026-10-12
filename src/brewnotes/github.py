"""GitHub REST access through `gh` when it's installed and logged in, otherwise anonymously.

Anonymous access needs no setup but allows 60 requests an hour; a logged-in `gh` allows 5,000."""

import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from typing import Any

RATE_LIMITED = "rate limited"


class GitHubError(RuntimeError):
    """A request failed for a reason other than "not found". The message is the reason."""


class GitHub:
    """Implements `sources.Source`. Methods return None when the repo or file doesn't exist and
    raise GitHubError for any other failure, after one retry for server errors."""

    def __init__(self) -> None:
        gh = shutil.which("gh")
        logged_in = (
            gh and subprocess.run([gh, "auth", "status"], capture_output=True, check=False).returncode == 0
        )
        self.gh = gh if logged_in else None

    def releases(self, repo: str, page: int, per_page: int) -> list[dict[str, Any]] | None:
        data = self._json(f"repos/{repo}/releases?per_page={per_page}&page={page}")
        return data if isinstance(data, list) else None

    def root_files(self, repo: str) -> list[str] | None:
        data = self._json(f"repos/{repo}/contents/")
        if not isinstance(data, list):
            return None
        return [x["name"] for x in data if x.get("type") == "file"]

    def read_file(self, repo: str, name: str) -> str | None:
        return self._fetch(f"repos/{repo}/contents/{name}", "application/vnd.github.raw")

    def _json(self, path: str) -> Any:
        text = self._fetch(path, "application/vnd.github+json")
        return json.loads(text) if text is not None else None

    def _fetch(self, path: str, accept: str) -> str | None:
        try:
            return self._fetch_once(path, accept)
        except _ServerError:
            try:
                return self._fetch_once(path, accept)
            except _ServerError as e:
                raise GitHubError(str(e)) from e

    def _fetch_once(self, path: str, accept: str) -> str | None:
        if self.gh:
            p = subprocess.run(
                [self.gh, "api", path, "-H", f"Accept: {accept}"], capture_output=True, text=True, check=False
            )
            if p.returncode == 0:
                return p.stdout
            status = re.search(r"HTTP (\d{3})", p.stderr)
            _raise_unless_missing(int(status.group(1)) if status else None, p.stderr)
            return None
        req = urllib.request.Request(f"https://api.github.com/{path}", headers={"Accept": accept})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return str(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            _raise_unless_missing(e.code, e.read().decode("utf-8", "replace"))
            return None
        except (urllib.error.URLError, TimeoutError) as e:
            raise GitHubError(f"network error: {e}") from e


class _ServerError(Exception):
    """A 5xx response, worth one retry."""


def _raise_unless_missing(status: int | None, detail: str) -> None:
    """Returns for a 404, which means the repo or file doesn't exist. Raises for anything else."""
    if status == 404:
        return
    if status == 429 or (status == 403 and "rate limit" in detail.lower()):
        raise GitHubError(RATE_LIMITED)
    if status and status >= 500:
        raise _ServerError(f"GitHub server error {status}")
    first_line = detail.strip().splitlines()[0] if detail.strip() else "no detail"
    raise GitHubError(f"HTTP {status}: {first_line}" if status else first_line.removeprefix("gh: "))
