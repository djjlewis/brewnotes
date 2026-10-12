"""GitHub REST access through `gh` when it's installed and logged in, otherwise anonymously.

Anonymous access needs no setup but allows 60 requests an hour. A logged-in `gh` allows 5,000."""

import http.client
import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from typing import Any

from .sources import RATE_LIMITED, FetchError


class GitHub:
    """Implements `sources.Source`. Methods return None when the repo or file doesn't exist and
    raise FetchError for any other failure, after one retry for server errors."""

    def __init__(self) -> None:
        gh = shutil.which("gh")
        # Ask about github.com only: `gh auth status` fails if any other configured host is logged out.
        status = [gh, "auth", "status", "--hostname", "github.com"] if gh else []
        logged_in = gh and subprocess.run(status, capture_output=True, check=False).returncode == 0
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
                raise FetchError(str(e)) from e

    def _fetch_once(self, path: str, accept: str) -> str | None:
        if self.gh:
            p = subprocess.run(
                [self.gh, "api", path, "-H", f"Accept: {accept}"], capture_output=True, text=True, check=False
            )
            if p.returncode == 0:
                return p.stdout
            status = re.search(r"HTTP (\d{3})", p.stderr)
            _raise_unless_not_found(int(status.group(1)) if status else None, p.stderr)
            return None
        req = urllib.request.Request(f"https://api.github.com/{path}", headers={"Accept": accept})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return str(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            code, detail = e.code, e.read().decode("utf-8", "replace")
        except (OSError, http.client.HTTPException) as e:  # URLError, timeouts, resets, short reads
            raise FetchError(f"network error: {e}") from e
        _raise_unless_not_found(code, detail)
        return None


class _ServerError(Exception):
    """A 5xx response, worth one retry."""


def _raise_unless_not_found(status: int | None, detail: str) -> None:
    """Returns for a 404, which means the repo or file doesn't exist. Otherwise raises FetchError
    (rate limit, other HTTP errors) or _ServerError (5xx)."""
    if status == 404:
        return
    if status == 429 or (status == 403 and "rate limit" in detail.lower()):
        raise FetchError(RATE_LIMITED)
    if status and status >= 500:
        raise _ServerError(f"GitHub server error {status}")
    first_line = detail.strip().splitlines()[0] if detail.strip() else "no detail"
    raise FetchError(f"HTTP {status}: {first_line}" if status else first_line.removeprefix("gh: "))
