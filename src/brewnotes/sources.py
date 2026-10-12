"""Finding the release notes for a version range: GitHub releases first, then a changelog file."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, NamedTuple, Protocol

from .brew import Change
from .github import GitHubError
from .versions import same_version, version_from_tag, version_key

MAX_NOTES_CHARS = 60_000
PAGE_SIZE = 30  # repos with huge release bodies make GitHub time out at 100
GITHUB_RE = re.compile(r"(?:^|//)(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
CHANGELOG_RE = re.compile(
    r"^(changelog|changes|news|history|release[-_]?notes)(\.(md|markdown|rst|txt))?$", re.IGNORECASE
)
BARE_HEADING_RE = re.compile(
    r"\s*\[?(v|version |release )?\d+(\.\d+)+\S*(\s*$|\s+[-(\[]|\s+\d{4}-\d\d)", re.IGNORECASE
)
UNDERLINE_RE = re.compile(r"\s*(=+|-+)\s*")
NOT_OWNERS = {"sponsors", "orgs", "apps", "features", "marketplace", "settings"}


class Source(Protocol):
    """Where release data comes from. Each method returns None when the repo or file doesn't
    exist, and raises GitHubError when the request fails."""

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
    source: Literal["releases", "changelog", ""] = ""
    links: list[tuple[str, str]] = field(default_factory=list)  # (label, url)
    truncated: bool = False
    error: str = ""  # why GitHub couldn't be checked; empty when it was


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
    in_window = since is not None and r.published is not None and r.published >= since
    return in_window or is_target


def select_releases(rels: list[Release], change: Change, since: datetime | None) -> list[Release]:
    """Releases after `change.old` up to and including `change.new`, newest first."""
    picked = [r for r in _same_family(rels, change.new) if _wanted(r, change, since)]
    return sorted(picked, key=lambda r: version_key(r.version), reverse=True)


def _list_releases(src: Source, repo: str, change: Change, since: datetime | None) -> list[Release]:
    """Newest-first releases, paging until past the old version (or the `since` date)."""
    out: list[Release] = []
    for page in range(1, 9):
        batch = src.releases(repo, page, PAGE_SIZE)
        if not batch:
            break
        page_rels = [r for raw in batch if (r := Release.parse(raw))]
        out += page_rels
        # Judge the page by the target's tag family only, so another product's old version
        # in a monorepo doesn't stop paging.
        family = {r.tag for r in _same_family(out, change.new)}
        page_family = [r for r in page_rels if r.tag in family]
        if len(batch) < PAGE_SIZE or (page_family and _reached_start(page_family, change, since)):
            break
    return out


def _reached_start(page: list[Release], change: Change, since: datetime | None) -> bool:
    """True once a page holds the old version, or holds nothing newer than it. Checking the
    whole page, not its last entry, keeps a backport (v1.9.9 among v2.x) from stopping early."""
    if change.old:
        old = version_key(change.old)
        has_old = any(same_version(r.version, change.old) for r in page)
        return has_old or all(version_key(r.version) <= old for r in page)
    if since:
        return all(r.published is not None and r.published < since for r in page)
    return True


# --- changelog fallback -----------------------------------------------------


class Heading(NamedTuple):
    line: int
    level: int  # the number of `#`s, 0 for an underlined or bare version line
    version: str


def changelog_section(text: str, new: str, old: str | None) -> str | None:
    """The lines from the `new` version's heading down to the first heading at or below `old`,
    or to the next version heading when `old` is unknown. Only headings of the same or a higher
    level end the section. None when `new` has no heading."""
    lines = text.splitlines()
    headings = _version_headings(lines)
    start = next((h for h in headings if same_version(h.version, new)), None)
    if start is None:
        return None
    later = [h for h in headings if h.line > start.line and _same_or_higher(h, start)]
    if old:
        end = next((h.line for h in later if version_key(h.version) <= version_key(old)), len(lines))
    else:
        end = next((h.line for h in later if not same_version(h.version, new)), len(lines))
    return "\n".join(lines[start.line : end])


def _same_or_higher(h: Heading, start: Heading) -> bool:
    if start.level == 0:
        return h.level == 0
    return 1 <= h.level <= start.level


def _version_headings(lines: list[str]) -> list[Heading]:
    """Each heading that names a version: `#` headings, underlined headings, and lines that are
    only a version with an optional date (`Version 1.3.0`, `1.3.0 (2026-10-01)`)."""
    out = []
    for i, line in enumerate(lines):
        level = len(line) - len(line.lstrip("#"))
        underlined = i + 1 < len(lines) and bool(line.strip()) and bool(UNDERLINE_RE.fullmatch(lines[i + 1]))
        is_heading = level > 0 or underlined or bool(BARE_HEADING_RE.match(line))
        if is_heading and (v := version_from_tag(line)):
            out.append(Heading(i, level, v))
    return out


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
    try:
        _read_notes(src, notes, notes.repo, change, since)
    except GitHubError as e:
        notes.text, notes.source, notes.error = "", "", str(e)
        notes.links.insert(0, ("releases", f"https://github.com/{notes.repo}/releases"))
        return notes

    if len(notes.text) > MAX_NOTES_CHARS:
        notes.text = notes.text[:MAX_NOTES_CHARS] + "\n\n[... truncated ...]"
        notes.truncated = True
    return notes


def _read_notes(src: Source, notes: Notes, repo: str, change: Change, since: datetime | None) -> None:
    everything = _list_releases(src, repo, change, since)
    rels = select_releases(everything, change, since)
    if rels:
        notes.text = "\n\n".join(f"## {r.tag} ({_date(r)})\n{r.body or '(no notes)'}" for r in rels)
        notes.source = "releases"
        new_rel = next((r for r in rels if same_version(r.version, change.new)), None)
        family = _same_family(everything, change.new)
        old_rel = next((r for r in family if change.old and same_version(r.version, change.old)), None)
        notes.links.insert(0, ("release notes", (new_rel or rels[0]).url))
        if new_rel and old_rel:
            notes.links.append(("diff", f"https://github.com/{repo}/compare/{old_rel.tag}...{new_rel.tag}"))
    else:
        notes.text = _changelog(src, repo, change) or ""
        notes.source = "changelog" if notes.text else ""
        notes.links.insert(0, ("releases", f"https://github.com/{repo}/releases"))


def _date(r: Release) -> str:
    return f"{r.published:%Y-%m-%d}" if r.published else "undated"
