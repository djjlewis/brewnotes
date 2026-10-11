"""GitHub REST access through the `gh` CLI (authenticated), or anonymously when it's missing."""

import json
import shutil
import subprocess
import urllib.error
import urllib.request
from typing import Any


class GitHub:
    """Implements `sources.Source`. Every method returns None on any HTTP or CLI failure."""

    def __init__(self) -> None:
        self.gh = shutil.which("gh")

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
        if self.gh:
            p = subprocess.run(
                [self.gh, "api", path, "-H", f"Accept: {accept}"], capture_output=True, text=True, check=False
            )
            return p.stdout if p.returncode == 0 else None
        req = urllib.request.Request(f"https://api.github.com/{path}", headers={"Accept": accept})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return str(r.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, TimeoutError):
            return None
