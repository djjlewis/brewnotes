"""Comparing the loose version strings that Homebrew and release tags use."""

import re

Parts = tuple[tuple[int, int | str], ...]
VersionKey = tuple[Parts, int, Parts]  # (release parts, 1 if final else 0, prerelease parts)
PRERELEASE_RE = re.compile(r"[-.]?(rc|beta|alpha|pre|dev)", re.IGNORECASE)


def clean_version(v: str) -> str:
    """Drop brew's bottle revision (`1.2.3_1`) and a cask's build suffix (`1.2,abcdef`)."""
    return re.sub(r"_\d+$", "", v.split(",")[0])


def version_from_tag(tag: str) -> str | None:
    """`v1.2.3` -> `1.2.3`, `Audacity-4.0.1` -> `4.0.1`, `azure-dev-cli_1.35.1` -> `1.35.1`.
    Keeps prerelease and letter suffixes (`2.0.0-rc1`, `9.6p1`) so they don't pass for the release.
    Returns None when the tag holds no number."""
    matches = re.findall(
        r"\d+(?:[._]\d+)+(?:[-.]?(?:rc|beta|alpha|pre|dev)\.?\d*|[a-z]\d*)?|\d+", tag, re.IGNORECASE
    )
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
    release, pre = (s[: m.start()], s[m.start() :]) if m else (s, "")
    main = list(_parts(release))
    while main and main[-1] == (1, 0):  # 1.2 == 1.2.0
        main.pop()
    return tuple(main), 0 if pre else 1, _parts(pre)


def _parts(s: str) -> Parts:
    return tuple((1, int(p)) if p.isdigit() else (0, p) for p in re.findall(r"\d+|[a-z]+", s))


def same_version(a: str, b: str) -> bool:
    return version_key(a) == version_key(b)


def leading_int(v: str) -> int | None:
    m = re.match(r"\D*(\d+)", v)
    return int(m.group(1)) if m else None
