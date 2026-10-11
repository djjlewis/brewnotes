"""Comparing the loose version strings that Homebrew and release tags use."""

import re
from typing import NamedTuple

# Prerelease markers, earliest stage first. `a`/`b` count only between digits (Python's 1.2.0b1).
PRERELEASE_RANK = {"dev": 0, "alpha": 1, "a": 1, "beta": 2, "b": 2, "preview": 3, "pre": 3, "rc": 4}
PRERELEASE = r"(?:[-.]?(?:dev|alpha|beta|preview|pre|rc)|(?<=\d)[ab](?=\d))\.?\d*"
PRERELEASE_RE = re.compile(PRERELEASE, re.IGNORECASE)
TAG_VERSION_RE = re.compile(rf"\d+(?:[._]\d+)+(?:{PRERELEASE}|[a-z]\d*)?|\d+", re.IGNORECASE)

Segments = tuple[tuple[int, int | str], ...]


class VersionKey(NamedTuple):
    """Compares as a tuple: release segments, then final (1) above prerelease (0), then the stage."""

    release: Segments
    final: int
    stage: tuple[int, ...]


def clean_version(v: str) -> str:
    """Drop brew's bottle revision (`1.2.3_1`) and a cask's build suffix (`1.2,abcdef`)."""
    return re.sub(r"_\d+$", "", v.split(",")[0])


def version_from_tag(tag: str) -> str | None:
    """`v1.2.3` -> `1.2.3`, `Audacity-4.0.1` -> `4.0.1`, `azure-dev-cli_1.35.1` -> `1.35.1`.
    Keeps prerelease and letter suffixes (`2.0.0-rc1`, `9.6p1`) so they don't pass for the release.
    Returns None when the tag holds no number."""
    matches = TAG_VERSION_RE.findall(tag)
    if not matches:
        return None
    dotted = [m for m in matches if "." in m or "_" in m]
    return str((dotted or matches)[0]).replace("_", ".")


def norm(v: str) -> str:
    """Normalise a brew version the same way as a tag, so `0.21.3-Beta` meets `v0.21.3-Beta`."""
    return version_from_tag(v) or v


def version_key(v: str) -> VersionKey:
    """Sort key: numbers compare numerically and outrank letters (`1.1.1w` > `1.1.1`),
    and a prerelease sorts before its release (`2.0.0-rc1` < `2.0.0`)."""
    s = norm(v).lower()
    m = PRERELEASE_RE.search(s)
    release = list(_segments(s[: m.start()] if m else s))
    while release and release[-1] == (1, 0):  # 1.2 == 1.2.0
        release.pop()
    if not m:
        return VersionKey(tuple(release), 1, ())
    word = re.sub(r"[^a-z]", "", m.group())
    number = re.sub(r"\D", "", m.group())
    return VersionKey(tuple(release), 0, (PRERELEASE_RANK[word], int(number or 0)))


def _segments(s: str) -> Segments:
    return tuple((1, int(p)) if p.isdigit() else (0, p) for p in re.findall(r"\d+|[a-z]+", s))


def same_version(a: str, b: str) -> bool:
    return version_key(a) == version_key(b)


def leading_int(v: str) -> int | None:
    m = re.match(r"\D*(\d+)", v)
    return int(m.group(1)) if m else None
