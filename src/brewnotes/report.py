"""Rendering triaged updates to the terminal (rich) and to markdown."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from rich.console import Console
from rich.markup import escape

from .brew import Change
from .sources import RATE_LIMITED, Notes
from .triage import Severity, Triage


class Section(NamedTuple):
    icon: str
    title: str
    style: str
    collapsed: bool  # names only in the terminal, a table in markdown


SECTIONS = {
    Severity.SECURITY: Section("🔴", "Security fixes", "bold red", False),
    Severity.BREAKING: Section("🟠", "Breaking changes / action needed", "bold yellow", False),
    Severity.NOTABLE: Section("🟢", "Notable enhancements", "bold green", False),
    Severity.MINOR: Section("⚪", "Minor (fixes & tweaks)", "dim", True),
    Severity.UNKNOWN: Section("❔", "Couldn't find notes", "dim", True),
    Severity.UNCHECKED: Section("⚠️", "Couldn't check", "yellow", True),
}


@dataclass(frozen=True)
class Item:
    change: Change
    notes: Notes
    triage: Triage

    def links(self) -> list[tuple[str, str]]:
        links = list(self.notes.links)
        if self.triage.notes_url and all(u != self.triage.notes_url for _, u in links):
            links.insert(0, ("notes", self.triage.notes_url))
        return links


def _ver(c: Change) -> str:
    return f"{c.old} → {c.new}" if c.old else f"→ {c.new}"


def grouped(items: list[Item]) -> dict[Severity, list[Item]]:
    """Items by severity, most severe first, sorted by name within each group."""
    groups: dict[Severity, list[Item]] = {s: [] for s in Severity}
    for it in sorted(items, key=lambda i: i.change.name):
        groups[it.triage.severity].append(it)
    return groups


def fetch_problem(items: list[Item], dependency_errors: Sequence[str] = ()) -> str | None:
    """One line summing up what GitHub couldn't be checked for, with the fix for a rate limit.
    Counts the shown packages left unchecked and, separately, the hidden dependencies whose
    fetch failed (`dependency_errors` holds their reasons). None when there are none."""
    package_errors = [i.notes.error for i in items if i.triage.severity is Severity.UNCHECKED]
    reasons = Counter([*package_errors, *dependency_errors])
    if not reasons:
        return None
    counts = [
        _count(len(package_errors), "package"),
        _count(len(dependency_errors), "dependency", "dependencies"),
    ]
    detail = ", ".join(f"{reason}: {count}" for reason, count in reasons.most_common())
    message = f"GitHub couldn't be checked for {' and '.join(c for c in counts if c)} ({detail})."
    if RATE_LIMITED in reasons:
        message += " Run `gh auth login` for a higher rate limit, or try again later."
    return message


def _count(n: int, one: str, many: str = "") -> str:
    """'' for 0, else '1 package' or '3 packages'."""
    if not n:
        return ""
    return f"{n} {one if n == 1 else many or one + 's'}"


def summary_line(items: list[Item]) -> str:
    if not items:
        return "No updates."
    return f"{len(items)} updates: " + ", ".join(f"{len(g)} {s}" for s, g in grouped(items).items() if g)


# --- terminal ---------------------------------------------------------------


def render_terminal(
    con: Console, items: list[Item], title: str, show_all: bool, md_path: Path | None
) -> None:
    con.print()
    con.rule(f"[bold]{escape(title)}")
    con.print(f"  {summary_line(items)}\n")
    for sev, group in grouped(items).items():
        if not group:
            continue
        sec = SECTIONS[sev]
        con.print(f"{sec.icon} [{sec.style}]{sec.title}[/] ({len(group)})")
        if sev is Severity.UNCHECKED and not show_all:
            _print_unchecked(con, group)
        elif sec.collapsed and not show_all:
            con.print(f"   [dim]{', '.join(_name_link(i) for i in group)}[/dim]\n")
        else:
            for it in group:
                _print_item(con, it)
    if md_path:
        con.print(f"[dim]Full report: {md_path}[/]")
    if not show_all and any(SECTIONS[i.triage.severity].collapsed for i in items):
        con.print("[dim]Use --all to expand the collapsed sections.[/]")


def _print_unchecked(con: Console, group: list[Item]) -> None:
    """Names grouped by the reason GitHub couldn't be checked."""
    by_reason: dict[str, list[Item]] = {}
    for it in group:
        by_reason.setdefault(it.notes.error, []).append(it)
    for reason, its in by_reason.items():
        con.print(f"   [dim]{escape(reason)}: {', '.join(_name_link(i) for i in its)}[/dim]")
    con.print()


def _name_link(it: Item) -> str:
    links = it.links()
    return f"[link={links[0][1]}]{escape(it.change.name)}[/link]" if links else escape(it.change.name)


def _print_item(con: Console, it: Item) -> None:
    c, t = it.change, it.triage
    tag = " [magenta]MAJOR[/]" if c.major_bump else ""
    dep = " [dim](dependency)[/]" if not c.requested else ""
    con.print(f"   [bold]{escape(c.name)}[/] [cyan]{escape(_ver(c))}[/]{tag}{dep}")
    con.print(f"     {escape(t.tldr)}")
    for h in t.highlights:
        con.print(f"     • {escape(h)}")
    if t.action_needed:
        con.print(f"     [yellow]⚠ {escape(t.action_needed)}[/]")
    if t.cves:
        con.print(f"     [red]{escape(', '.join(t.cves[:6]))}[/]")
    links = "  ".join(f"[link={u}]{escape(label)}[/link]" for label, u in it.links()[:3])
    if links:
        con.print(f"     [blue]{links}[/]")
    con.print()


# --- markdown ---------------------------------------------------------------


def render_markdown(items: list[Item], title: str, now: datetime) -> str:
    out = [f"# {title}", "", f"_{now:%Y-%m-%d %H:%M}_ · {summary_line(items)}", ""]
    for sev, group in grouped(items).items():
        if not group:
            continue
        sec = SECTIONS[sev]
        out += [f"## {sec.icon} {sec.title} ({len(group)})", ""]
        out += _md_table(group) if sec.collapsed else [line for it in group for line in _md_item(it)]
    return "\n".join(out)


def _md_table(group: list[Item]) -> list[str]:
    rows = ["| Package | Version | Summary | Links |", "|---|---|---|---|"]
    for it in group:
        links = " · ".join(f"[{label}]({u})" for label, u in it.links()[:2])
        rows.append(
            f"| {it.change.name} | {_ver(it.change)} | {it.triage.tldr.replace('|', '/')} | {links} |"
        )
    return [*rows, ""]


def _md_item(it: Item) -> list[str]:
    c, t = it.change, it.triage
    extra = (" **MAJOR**" if c.major_bump else "") + ("" if c.requested else " _(dependency)_")
    out = [f"### {c.name} `{_ver(c)}`{extra}", "", t.tldr, ""]
    if t.highlights:
        out += [*(f"- {h}" for h in t.highlights), ""]
    if t.action_needed:
        out += [f"> ⚠️ **Action:** {t.action_needed}", ""]
    if t.cves:
        out += ["**Advisories:** " + ", ".join(t.cves), ""]
    if links := " · ".join(f"[{label}]({u})" for label, u in it.links()):
        out += [links, ""]
    return out


def save_markdown(items: list[Item], title: str, reports_dir: Path, mode: str, now: datetime) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{now:%Y-%m-%d-%H%M}-{mode}.md"
    path.write_text(render_markdown(items, title, now))
    return path
