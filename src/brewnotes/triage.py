"""Turning release notes into a severity and a TL;DR, with Claude or with keyword heuristics."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from .brew import Change
from .llm import Ask, BackendError, BackendUnavailable
from .sources import Notes


class Severity(StrEnum):
    """Most severe first. The report shows sections in this order."""

    SECURITY = "security"
    BREAKING = "breaking"
    NOTABLE = "notable"
    MINOR = "minor"
    UNKNOWN = "unknown"
    UNCHECKED = "unchecked"  # GitHub couldn't be checked. Set by brewnotes, never by Claude.


LLM_SEVERITIES = [s.value for s in Severity if s is not Severity.UNCHECKED]

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "severity": {"type": "string", "enum": LLM_SEVERITIES},
        "tldr": {"type": "string"},
        "highlights": {"type": "array", "items": {"type": "string"}},
        "action_needed": {"type": "string"},
        "cves": {"type": "array", "items": {"type": "string"}},
        "notes_url": {"type": "string"},
    },
    "required": ["severity", "tldr", "highlights", "action_needed", "cves", "notes_url"],
    "additionalProperties": False,
}

PROMPT = """You triage software release notes for a busy developer who updates their Mac with Homebrew.
They want to know only what matters, never a list of every bug fix.

About them: {interests}

Package: {name} ({kind}), {desc}
Update: {old} -> {new}{major}
{notes_section}

Return JSON:
- severity: the single highest that applies:
  - "security": fixes a vulnerability (CVE, advisory, "security fix") in this software.
  - "breaking": removes or renames commands/flags/config/APIs, changes defaults or behaviour
    in a way they may trip over, drops platform support, or needs migration steps.
  - "notable": new features or improvements a typical user of this tool would notice or want to try.
  - "minor": bug fixes, performance tweaks, docs, internal refactors, dependency bumps.
  - "unknown": you could not find or read any notes.
- tldr: one plain sentence (max ~25 words) saying what changed and whether they should care.
- highlights: up to 5 terse bullets of the items that matter, most important first. Empty for minor.
- action_needed: what they must do (e.g. "rename `foo` to `bar` in ~/.config/x"), or "" if nothing.
- cves: CVE/GHSA IDs mentioned, or [].
- notes_url: URL of the notes you used if you found them on the web, else "".
"""

NOTES_PROVIDED = """
Release notes ({source}{trunc}):
<release_notes>
{text}
</release_notes>
"""

NOTES_MISSING_WEB = """
No release notes were found automatically{repo}. Use web search/fetch to find the official release notes
or changelog covering versions after {old} up to {new} (homepage: {homepage}). Keep it quick: a couple of
lookups at most. If you can't find them, use severity "unknown".
"""

ADVISORY_RE = re.compile(r"CVE-\d{4}-\d+|GHSA-\w{4}-\w{4}-\w{4}")
SECURITY_RE = re.compile(
    r"\bCVE-\d{4}-\d+|GHSA-\w{4}-\w{4}-\w{4}|\bsecurity\b|vulnerab|exploit|\bXSS\b|RCE\b", re.IGNORECASE
)
BREAKING_RE = re.compile(r"breaking|\bremoved?\b|no longer|deprecat|incompatib|migrat|renamed", re.IGNORECASE)

HEURISTIC_TLDR = {
    Severity.SECURITY: "Release notes mention security fixes.",
    Severity.BREAKING: "Major version bump or breaking changes mentioned. Check the notes.",
    Severity.NOTABLE: "Mentions removals or deprecations. Worth a skim.",
    Severity.MINOR: "Nothing flagged by keyword scan.",
    Severity.UNKNOWN: "No release notes found.",
}


@dataclass
class Triage:
    severity: Severity
    tldr: str
    highlights: list[str] = field(default_factory=list)
    action_needed: str = ""
    cves: list[str] = field(default_factory=list)
    notes_url: str = ""
    by: str = ""  # which backend produced this

    @staticmethod
    def from_llm(data: dict[str, Any], by: str) -> "Triage":
        severity = data.get("severity")
        return Triage(
            severity=Severity(severity) if severity in LLM_SEVERITIES else Severity.UNKNOWN,
            tldr=str(data.get("tldr") or ""),
            highlights=[str(h) for h in data.get("highlights") or []][:5],
            action_needed=str(data.get("action_needed") or ""),
            cves=[str(c) for c in data.get("cves") or []],
            notes_url=str(data.get("notes_url") or ""),
            by=by,
        )


def looks_security_related(notes: Notes) -> bool:
    return bool(SECURITY_RE.search(notes.text))


def unchecked(notes: Notes) -> Triage:
    """The result for a package GitHub couldn't be checked for, with the reason as the TL;DR."""
    return Triage(Severity.UNCHECKED, f"Couldn't check GitHub: {notes.error}.", by="brewnotes")


def heuristic(change: Change, notes: Notes) -> Triage:
    text = notes.text
    if not text and notes.error:
        return unchecked(notes)
    if not text:
        sev = Severity.UNKNOWN
    elif SECURITY_RE.search(text):
        sev = Severity.SECURITY
    elif change.major_bump or re.search(r"breaking change|BREAKING", text):
        sev = Severity.BREAKING
    elif BREAKING_RE.search(text):
        sev = Severity.NOTABLE
    else:
        sev = Severity.MINOR
    return Triage(sev, HEURISTIC_TLDR[sev], cves=sorted(set(ADVISORY_RE.findall(text))), by="heuristic")


def build_prompt(change: Change, notes: Notes, interests: str) -> str:
    """With no notes, the prompt asks Claude to find them on the web."""
    if notes.text:
        section = NOTES_PROVIDED.format(
            source=notes.source, trunc=", truncated" if notes.truncated else "", text=notes.text
        )
    else:
        section = NOTES_MISSING_WEB.format(
            repo=_why_no_notes(notes),
            old=change.old or "the previous version",
            new=change.new,
            homepage=change.homepage or "unknown",
        )
    return PROMPT.format(
        interests=interests or "a general developer",
        name=change.name,
        kind=change.kind,
        desc=change.desc or "no description",
        old=change.old or "(unknown previous version)",
        new=change.new,
        major="  [MAJOR VERSION BUMP]" if change.major_bump else "",
        notes_section=section,
    )


def _why_no_notes(notes: Notes) -> str:
    if notes.error:
        return f" (GitHub couldn't be checked: {notes.error})"
    if notes.repo:
        return f" (GitHub repo {notes.repo} has no releases or changelog for this range)"
    return ""


class Triager:
    """Triages changes with an LLM, caching results per version range and notes text.

    Falls back to `heuristic` when there's nothing to read, when one request fails, and
    for the rest of the run once the backend is unavailable (see `problem`)."""

    def __init__(
        self,
        name: str,
        ask: Ask | None,
        ask_web: Ask | None,
        cache_dir: Path,
        interests: str = "",
        use_cache: bool = True,
        problem: str | None = None,
    ) -> None:
        self.name, self.ask, self.ask_web = name, ask, ask_web
        self.cache_dir, self.interests, self.use_cache = cache_dir, interests, use_cache
        self.problem = problem

    def triage(self, change: Change, notes: Notes) -> Triage:
        cache = self.cache_dir / _cache_name(change, notes)
        # A GitHub failure has no notes text, so it shares a cache key with "no notes exist".
        # Skip the cache both ways, so the failure shows and the next run tries GitHub again.
        if self.use_cache and not notes.error and cache.exists():
            data = json.loads(cache.read_text())
            return Triage(**{**data, "severity": Severity(data["severity"])})
        if self.problem or self.ask is None:
            return heuristic(change, notes)

        web = self.ask_web is not None and not notes.text and change.requested
        if not notes.text and not web:
            return heuristic(change, notes)  # nothing for an LLM to read
        ask = self.ask_web if web and self.ask_web else self.ask
        try:
            t = Triage.from_llm(ask(build_prompt(change, notes, self.interests)), self.name)
        except BackendUnavailable as e:
            self.problem = str(e)
            return heuristic(change, notes)
        except BackendError as e:
            t = heuristic(change, notes)
            t.tldr += f" (LLM triage failed: {str(e)[:120]})"
            return t
        if notes.error:
            return unchecked(notes) if t.severity is Severity.UNKNOWN else t
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(asdict(t)))
        return t


def _cache_name(change: Change, notes: Notes) -> str:
    digest = hashlib.sha1(notes.text.encode()).hexdigest()[:10]
    return re.sub(r"[^\w.@-]+", "_", change.key) + f"-{digest}.json"
