"""Homebrew: what's installed, what's outdated, and what changed between two snapshots."""

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from .versions import clean_version, leading_int


@dataclass(frozen=True)
class Installed:
    version: str
    time: int | None = None  # unix time of install
    requested: bool = True  # installed on request rather than as a dependency
    desc: str = ""
    homepage: str = ""
    urls: list[str] = field(default_factory=list)  # candidates for locating the source repo


Snapshot = dict[str, Installed]  # keyed "formula:name" / "cask:name"


@dataclass
class Change:
    name: str
    kind: str  # "formula" | "cask"
    old: str | None  # None when unknown (recap without a snapshot)
    new: str
    desc: str = ""
    homepage: str = ""
    urls: list[str] = field(default_factory=list)
    requested: bool = True

    @property
    def major_bump(self) -> bool:
        if not self.old:
            return False
        a, b = leading_int(self.old), leading_int(self.new)
        # Browsers and date-stamped versions (Firefox 154, Teams 26213) bump the
        # leading number every release, so it says nothing there.
        return a is not None and b is not None and a < b < 50

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.name}@{self.old or '?'}..{self.new}"


def diff_snapshots(before: Snapshot, after: Snapshot) -> list[Change]:
    """Packages whose version differs between the snapshots. New installs are skipped."""
    return [
        _change(key, prev.version, now)
        for key, now in after.items()
        if (prev := before.get(key)) and prev.version != now.version
    ]


def changed_since(snap: Snapshot, since: datetime, before: Snapshot | None = None) -> list[Change]:
    """Anything (re)installed after `since`, except casks versioned `latest`, whose reinstall
    changes no version. The old version comes from `before` when it has a different one, and is
    otherwise unknown."""
    ts = since.timestamp()
    changes = []
    for key, now in snap.items():
        if now.time is None or now.time < ts or now.version == "latest":
            continue
        prev = (before or {}).get(key)
        changes.append(_change(key, prev.version if prev and prev.version != now.version else None, now))
    return changes


def _change(key: str, old: str | None, now: Installed) -> Change:
    kind, name = key.split(":", 1)
    return Change(
        name=name,
        kind=kind,
        old=old,
        new=now.version,
        desc=now.desc,
        homepage=now.homepage,
        urls=now.urls,
        requested=now.requested,
    )


def snapshot_to_json(snap: Snapshot) -> str:
    return json.dumps({k: asdict(v) for k, v in snap.items()}, indent=1, sort_keys=True)


def snapshot_from_json(text: str) -> Snapshot:
    return {k: Installed(**v) for k, v in json.loads(text).items()}


# --- the brew CLI -----------------------------------------------------------


def _brew_json(*args: str) -> Any:
    out = subprocess.run(["brew", *args], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def update() -> None:
    subprocess.run(["brew", "update", "--quiet"], check=False)


def installed() -> Snapshot:
    data = _brew_json("info", "--json=v2", "--installed")
    leaves = subprocess.run(["brew", "leaves"], capture_output=True, text=True, check=True).stdout.split()
    snap: Snapshot = {}
    for f in data["formulae"]:
        inst = (f.get("installed") or [{}])[-1]
        if inst.get("version"):
            snap[f"formula:{f['name']}"] = Installed(
                version=clean_version(inst["version"]),
                time=inst.get("time"),
                requested=bool(inst.get("installed_on_request")) or f["name"] in leaves,
                desc=f.get("desc") or "",
                homepage=f.get("homepage") or "",
                urls=[f.get("homepage") or ""]
                + [u["url"] for u in (f.get("urls") or {}).values() if isinstance(u, dict) and u.get("url")],
            )
    for c in data["casks"]:
        if c.get("installed"):
            snap[f"cask:{c['token']}"] = Installed(
                version=clean_version(c["installed"]),
                time=c.get("installed_time"),
                desc=c.get("desc") or "",
                homepage=c.get("homepage") or "",
                urls=[c.get("homepage") or "", c.get("url") or ""],
            )
    return snap


def outdated(snap: Snapshot, greedy: bool = False) -> list[Change]:
    data = _brew_json("outdated", "--json=v2", *(["--greedy"] if greedy else []))
    changes = []
    for kind, items in (("formula", data["formulae"]), ("cask", data["casks"])):
        for it in items:
            old, new = clean_version(it["installed_versions"][-1]), clean_version(it["current_version"])
            if old == new:  # casks versioned "latest"
                continue
            meta = snap.get(f"{kind}:{it['name']}", Installed(version=old))
            changes.append(
                _change(f"{kind}:{it['name']}", old, Installed(**{**asdict(meta), "version": new}))
            )
    return changes
