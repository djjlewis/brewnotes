"""brewnotes: a triaged TL;DR of what your Homebrew updates actually change."""

import argparse
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

from rich.console import Console

from . import brew, llm
from .config import Config, Paths, load_config
from .github import GitHub
from .report import Item, render_terminal, save_markdown
from .sources import fetch_notes
from .triage import SCHEMA, Triager, heuristic, looks_security_related

UNITS = {"h": "hours", "d": "days", "w": "weeks"}


def parse_since(s: str, now: datetime) -> datetime:
    """`7d`, `48h`, `2w`, or an ISO date."""
    if m := re.fullmatch(r"(\d+)([hdw])", s):
        return now - timedelta(**{UNITS[m.group(2)]: int(m.group(1))})
    return datetime.fromisoformat(s)


def make_triager(cfg: Config, paths: Paths, use_cache: bool) -> Triager | None:
    """None for the heuristics-only backend."""
    if cfg.backend == "none":
        return None
    try:
        if cfg.backend == "api":
            ask, ask_web = llm.anthropic_api(SCHEMA, cfg.api_model), None
        else:
            ask = llm.claude_cli(SCHEMA, cfg.model)
            ask_web = llm.claude_cli(SCHEMA, cfg.model, web=True) if cfg.web_lookup else None
    except llm.BackendUnavailable as e:
        return Triager(cfg.backend, None, None, paths.cache, problem=str(e))
    return Triager(cfg.backend, ask, ask_web, paths.cache, cfg.interests, use_cache)


class Run:
    def __init__(self, cfg: Config, paths: Paths, args: argparse.Namespace) -> None:
        self.cfg, self.paths, self.args = cfg, paths, args
        self.err = Console(stderr=True)
        self.github = GitHub()
        self.triager = make_triager(cfg, paths, use_cache=not args.no_cache)

    def load_snapshot(self) -> brew.Snapshot | None:
        p = self.paths.snapshot
        return brew.snapshot_from_json(p.read_text()) if p.exists() else None

    def save_snapshot(self, snap: brew.Snapshot) -> None:
        self.paths.snapshot.parent.mkdir(parents=True, exist_ok=True)
        self.paths.snapshot.write_text(brew.snapshot_to_json(snap))

    def process(self, changes: list[brew.Change], since: datetime | None) -> list[Item]:
        changes = [c for c in changes if c.name not in self.cfg.ignore]
        with (
            self.err.status(f"Reading release notes for {len(changes)} packages…"),
            ThreadPoolExecutor(max_workers=self.cfg.workers) as pool,
        ):
            return [i for i in pool.map(lambda c: self._one(c, since), changes) if i]

    def _one(self, c: brew.Change, since: datetime | None) -> Item | None:
        notes = fetch_notes(self.github, c, since)
        # Dependencies only make the report if they look security-related.
        if not c.requested and not self.cfg.include_dependencies and not looks_security_related(notes):
            return None
        t = self.triager.triage(c, notes) if self.triager else heuristic(c, notes)
        return Item(c, notes, t)

    def finish(self, items: list[Item], mode: str, title: str) -> None:
        if self.triager and self.triager.problem:
            self.err.print(
                f"[bold red]LLM triage unavailable, used keyword heuristics:[/] {self.triager.problem}"
            )
        now = datetime.now()
        save = items and not self.args.no_save
        md = save_markdown(items, title, self.cfg.reports_path, mode, now) if save else None
        render_terminal(Console(), items, title, self.args.all, md)


def cmd_preview(run: Run) -> None:
    if not run.args.no_update:
        with run.err.status("brew update…"):
            brew.update()
    snap = brew.installed()
    if run.load_snapshot() is None:  # so the first recap has something to diff against
        run.save_snapshot(snap)
    items = run.process(brew.outdated(snap, greedy=run.args.greedy), None)
    run.finish(items, "preview", "brew preview: pending updates")


def cmd_recap(run: Run) -> None:
    current, before = brew.installed(), run.load_snapshot()
    if before is not None and not run.args.since:
        changes, since = brew.diff_snapshots(before, current), None
        title = "brew recap: changes since last run"
    else:
        since = parse_since(run.args.since or "7d", datetime.now())
        if before is None:
            run.err.print(
                f"[dim]No previous snapshot; reporting packages installed since {since:%Y-%m-%d}.[/]"
            )
        changes = brew.changed_since(current, since, before)
        title = f"brew recap: changes since {since:%Y-%m-%d}"
    items = run.process(changes, since)
    run.save_snapshot(current)
    run.finish(items, "recap", title)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="brewnotes", description=__doc__)
    sub = ap.add_subparsers(dest="cmd")
    preview = sub.add_parser("preview", help="what `brew upgrade` would change (default)")
    preview.add_argument("--no-update", action="store_true", help="skip `brew update` first")
    preview.add_argument("--greedy", action="store_true", help="include casks that auto-update")
    recap = sub.add_parser("recap", help="what changed since the last run")
    recap.add_argument("--since", help="e.g. 7d, 48h, 2w or 2026-10-01 (ignores the snapshot)")
    for p in (preview, recap):
        p.add_argument("--all", action="store_true", help="expand minor/unknown items")
        p.add_argument("--backend", choices=["claude-cli", "api", "none"], help="override the config backend")
        p.add_argument("--no-cache", action="store_true", help="re-triage even if cached")
        p.add_argument("--no-save", action="store_true", help="don't write a markdown report")
        p.add_argument("--deps", action="store_true", help="report all changed dependencies")
    sub.add_parser("config", help="print the config file path")
    return ap


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parses the command line. With no subcommand, the arguments go to `preview`."""
    commands = {"preview", "recap", "config", "-h", "--help"}
    if not argv or argv[0] not in commands:
        argv = ["preview", *argv]
    return build_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    paths = Paths.from_env(os.environ, Path.home())
    cfg = load_config(paths.config)
    if args.cmd == "config":
        print(paths.config)
        return
    cfg.backend = args.backend or cfg.backend
    cfg.include_dependencies = cfg.include_dependencies or args.deps
    try:
        (cmd_preview if args.cmd == "preview" else cmd_recap)(Run(cfg, paths, args))
    except KeyboardInterrupt:
        sys.exit(130)
