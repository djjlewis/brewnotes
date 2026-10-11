"""Finding the release notes for a version range: GitHub releases first, then a changelog file."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from .brew import Change
from .versions import same_version, version_from_tag, version_key

MAX_NOTES_CHARS = 60_000
PAGE_SIZE = 30  # repos with huge release bodies make GitHub time out at 100
GITHUB_RE = re.compile(r"(?:^|//)(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
CHANGELOG_RE = re.compile(
    r"^(changelog|changes|news|history|release[-_]?notes)(\.(md|markdown|rst|txt))?$", re.IGNORECASE
)
NOT_OWNERS = {"sponsors", "orgs", "apps", "features", "marketplace", "settings"}


class Source(Protocol):
    """Where release data comes from. Each method returns None when the request fails."""

    def releases(self, repo: str, page: int, per_page: int) -> list[dict[str, Any]] | None: ...
    def root_files(self, repo: str) -> list[str] | None: ...
    def read_file(self, repo: str, name: str) -> str | None: ...


@dataclass(frozen=True)
class Release:
    tag: str
    version: str
    body: str
    url: str
    published: datetime | None
    prerelease: bool

    @staticmethod
    def parse(raw: dict[str, Any]) -> "Release | None":
        """None for drafts and tags with no version number."""
        tag = raw.get("tag_name") or ""
        v = version_from_tag(tag) or version_from_tag(raw.get("name") or "")
        if raw.get("draft") or not v:
            return None
        published = raw.get("published_at")
        return Release(
            tag=tag,
            version=v,
            body=(raw.get("body") or "").strip(),
            url=raw.get("html_url") or "",
            published=datetime.fromisoformat(published[:19]) if published else None,
            prerelease=bool(raw.get("prerelease")),
        )


@dataclass
class Notes:
    repo: str | None = None
    text: str = ""
    source: str = ""  # "releases" | "changelog" | ""
    links: list[tuple[str, str]] = field(default_factory=list)  # (label, url)
    truncated: bool = False


def find_repo(change: Change) -> str | None:
    for url in change.urls:
        m = GITHUB_RE.search(url or "")
        if m and m.group(1).lower() not in NOT_OWNERS:
            return f"{m.group(1)}/{m.group(2).removesuffix('.git')}"
    return None


# --- picking releases -------------------------------------------------------


def _tag_prefix(r: Release) -> str:
    """The part of the tag before the version: 'rust-v' in 'rust-v0.1.0'."""
    for form in (r.version, r.version.replace(".", "_")):
        if form in r.tag:
            return r.tag.split(form)[0]
    return r.tag


def _same_family(rels: list[Release], target: str) -> list[Release]:
    """Monorepos tag several products in one repo; keep the family whose tag matches `target`."""
    anchor = next((r for r in rels if same_version(r.version, target)), None)
    if not anchor:
        return rels
    prefix = _tag_prefix(anchor)
    return [r for r in rels if _tag_prefix(r) == prefix]


def _wanted(r: Release, change: Change, since: datetime | None) -> bool:
    is_target = same_version(r.version, change.new)
    if r.prerelease and not is_target:
        return False
    if version_key(r.version) > version_key(change.new):
        return False
    if change.old:
        return version_key(r.version) > version_key(change.old)
    # Unknown previous version: releases published in the window, plus the one we're on.
    in_window = since is not None and r.published is not None and r.published >= since - timedelta(days=3)
    return in_window or is_target


def select_releases(rels: list[Release], change: Change, since: datetime | None) -> list[Release]:
    """Releases after `change.old` up to and including `change.new`, newest first."""
    picked = [r for r in _same_family(rels, change.new) if _wanted(r, change, since)]
    return sorted(picked, key=lambda r: version_key(r.version), reverse=True)


def _list_releases(src: Source, repo: str, change: Change, since: datetime | None) -> list[Release]:
    """Newest-first releases, paging until past the old version (or the `since` date)."""
    out: list[Release] = []
    for page in range(1, 9):
        batch = src.releases(repo, page, PAGE_SIZE) or src.releases(repo, page, PAGE_SIZE)  # retry 5xx blips
        if not batch:
            break
        out += [r for raw in batch if (r := Release.parse(raw))]
        if len(batch) < PAGE_SIZE or not out or _past_range(out[-1], change, since):
            break
    return out


def _past_range(oldest: Release, change: Change, since: datetime | None) -> bool:
    if change.old:
        return version_key(oldest.version) <= version_key(change.old)
    if since and oldest.published:
        return oldest.published < since - timedelta(days=30)
    return True


# --- changelog fallback -----------------------------------------------------


def changelog_section(text: str, new: str, old: str | None) -> str | None:
    """The lines from the `new` version's heading down to the `old` one's, or to the next
    version heading when `old` is unknown. None when `new` has no heading."""
    lines = text.splitlines()
    start = _heading_line(lines, new, 0)
    if start is None:
        return None
    end = _heading_line(lines, old, start + 1) if old else None
    if end is None:
        marker = lines[start][:2]
        end = next(
            (
                i
                for i in range(start + 1, len(lines))
                if lines[i].startswith(marker) and version_from_tag(lines[i])
            ),
            len(lines),
        )
    return "\n".join(lines[start:end])


def _heading_line(lines: list[str], version: str, start: int) -> int | None:
    pat = re.compile(rf"(^|[^\d.]){re.escape(version)}($|[^\d])")
    for i in range(start, len(lines)):
        looks_like_heading = lines[i].startswith(("#", "=", "v", "V", "[")) or len(lines[i]) < 60
        if looks_like_heading and pat.search(lines[i]):
            return i
    return None


def _changelog(src: Source, repo: str, change: Change) -> str | None:
    name = next((f for f in src.root_files(repo) or [] if CHANGELOG_RE.match(f)), None)
    text = src.read_file(repo, name) if name else None
    return changelog_section(text, change.new, change.old) if text else None


# --- entry point ------------------------------------------------------------


def fetch_notes(src: Source, change: Change, since: datetime | None = None) -> Notes:
    """Release notes covering `change`, with links to read more. Empty text when none were found."""
    notes = Notes(repo=find_repo(change))
    if change.homepage:
        notes.links.append(("homepage", change.homepage))
    if not notes.repo:
        return notes

    everything = _list_releases(src, notes.repo, change, since)
    rels = select_releases(everything, change, since)
    if rels:
        notes.text = "\n\n".join(f"## {r.tag} ({_date(r)})\n{r.body or '(no notes)'}" for r in rels)
        notes.source = "releases"
        notes.links.insert(0, ("release notes", rels[0].url))
        old_tag = next(
            (r.tag for r in everything if change.old and same_version(r.version, change.old)), None
        )
        if old_tag:
            notes.links.append(("diff", f"https://github.com/{notes.repo}/compare/{old_tag}...{rels[0].tag}"))
    else:
        notes.text = _changelog(src, notes.repo, change) or ""
        notes.source = "changelog" if notes.text else ""
        notes.links.insert(0, ("releases", f"https://github.com/{notes.repo}/releases"))

    if len(notes.text) > MAX_NOTES_CHARS:
        notes.text = notes.text[:MAX_NOTES_CHARS] + "\n\n[... truncated ...]"
        notes.truncated = True
    return notes


def _date(r: Release) -> str:
    return f"{r.published:%Y-%m-%d}" if r.published else "undated"
