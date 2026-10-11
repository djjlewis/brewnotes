"""Rendering triaged updates to the terminal (rich) and to markdown."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from .brew import Change
from .sources import Notes
from .triage import SEVERITIES, Triage

ICONS = {"security": "🔴", "breaking": "🟠", "notable": "🟢", "minor": "⚪", "unknown": "❔"}
TITLES = {
    "security": "Security fixes",
    "breaking": "Breaking changes / action needed",
    "notable": "Notable enhancements",
    "minor": "Minor (fixes & tweaks)",
    "unknown": "Couldn't find notes",
}
STYLES = {
    "security": "bold red",
    "breaking": "bold yellow",
    "notable": "bold green",
    "minor": "dim",
    "unknown": "dim",
}
COLLAPSED = ("minor", "unknown")


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


def grouped(items: list[Item]) -> dict[str, list[Item]]:
    """Items by severity, most severe first, sorted by name within each group."""
    groups: dict[str, list[Item]] = {s: [] for s in SEVERITIES}
    for it in sorted(items, key=lambda i: i.change.name):
        groups[it.triage.severity].append(it)
    return groups


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
        con.print(f"{ICONS[sev]} [{STYLES[sev]}]{TITLES[sev]}[/] ({len(group)})")
        if sev in COLLAPSED and not show_all:
            con.print(f"   [dim]{', '.join(_name_link(i) for i in group)}[/dim]\n")
        else:
            for it in group:
                _print_item(con, it)
    if md_path:
        con.print(f"[dim]Full report: {md_path}[/]")
    if not show_all and any(i.triage.severity in COLLAPSED for i in items):
        con.print("[dim]Use --all to expand minor/unknown items.[/]")


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
        out += [f"## {ICONS[sev]} {TITLES[sev]} ({len(group)})", ""]
        out += _md_table(group) if sev in COLLAPSED else [line for it in group for line in _md_item(it)]
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
