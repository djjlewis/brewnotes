"""The config file, plus where state and cache files live."""

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path

DEFAULT_CONFIG = """\
# brewnotes config

# How release notes get triaged:
#   "claude-cli" - runs `claude -p` (uses your Claude subscription login)
#   "api"        - Anthropic API via the SDK (needs ANTHROPIC_API_KEY or `ant auth login`)
#   "none"       - keyword heuristics only, no LLM
backend = "claude-cli"

# Model for claude-cli. "" means Claude Code's default; aliases like "sonnet" or "haiku" work.
model = ""
# Model for the api backend: a full model ID.
api_model = "claude-opus-5-5"

# Let claude-cli search the web for release notes when no GitHub repo is found
# (casks like Chrome or Docker, or projects hosted elsewhere).
web_lookup = true

# Where markdown reports are saved.
reports_dir = "~/Documents/brewnotes"

# Free text that helps the triage decide what is "notable" for you.
interests = "I'm a developer. I care about CLI/config changes in tools I use daily, terminal workflows, git, \
neovim, and anything security-related."

# Packages to never report on (still tracked in the snapshot).
ignore = []

# Formulae you didn't install directly (dependencies) are only reported when
# their release notes look security-related. Set true to report them all.
include_dependencies = false

# Parallel workers for fetching and triage.
workers = 4
"""


@dataclass
class Config:
    backend: str = "claude-cli"
    model: str = ""
    api_model: str = "claude-opus-5-5"
    web_lookup: bool = True
    reports_dir: str = "~/Documents/brewnotes"
    interests: str = ""
    ignore: list[str] = field(default_factory=list)
    include_dependencies: bool = False
    workers: int = 4

    @property
    def reports_path(self) -> Path:
        return Path(self.reports_dir).expanduser()


@dataclass(frozen=True)
class Paths:
    config: Path
    snapshot: Path
    cache: Path

    @staticmethod
    def from_env(env: Mapping[str, str], home: Path) -> "Paths":
        """XDG locations, defaulting to ~/.config, ~/.local/state and ~/.cache."""
        config = Path(env.get("XDG_CONFIG_HOME") or home / ".config") / "brewnotes"
        state = Path(env.get("XDG_STATE_HOME") or home / ".local" / "state") / "brewnotes"
        cache = Path(env.get("XDG_CACHE_HOME") or home / ".cache") / "brewnotes"
        return Paths(config=config / "config.toml", snapshot=state / "snapshot.json", cache=cache / "triage")


def load_config(path: Path) -> Config:
    """Reads the config, writing the commented default first if there is none.
    Unknown keys are ignored."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_CONFIG)
    data = tomllib.loads(path.read_text())
    names = {f.name for f in fields(Config)}
    return Config(**{k: v for k, v in data.items() if k in names})
