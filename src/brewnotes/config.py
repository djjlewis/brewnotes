"""The config file, plus where state and cache files live."""

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Literal, get_args

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


Backend = Literal["claude-cli", "api", "none"]
BACKENDS: tuple[Backend, ...] = get_args(Backend)


class ConfigError(ValueError):
    """The config file can't be used. The message names the setting and says what's allowed."""


@dataclass(frozen=True)
class Config:
    backend: Backend = "claude-cli"
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
    """Reads the config, writing the commented default first if there is none. Raises
    ConfigError for invalid TOML, an unknown setting, or a value of the wrong type or range."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_CONFIG)
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from e
    for key, value in data.items():
        _check(path, key, value)
    return Config(**data)


def _check(path: Path, key: str, value: object) -> None:
    defaults = Config()
    if key not in {f.name for f in fields(Config)}:
        raise ConfigError(f"{path}: unknown setting `{key}`")
    expected = type(getattr(defaults, key))
    strings = isinstance(value, list) and all(isinstance(v, str) for v in value)
    if type(value) is not expected or (expected is list and not strings):
        wanted = "a list of strings" if expected is list else f"a {expected.__name__}"
        raise ConfigError(f"{path}: `{key}` must be {wanted}, not {value!r}")
    if key == "backend" and value not in BACKENDS:
        raise ConfigError(f"{path}: `backend` must be one of {', '.join(BACKENDS)}, not {value!r}")
    if key == "workers" and isinstance(value, int) and value < 1:
        raise ConfigError(f"{path}: `workers` must be at least 1, not {value}")
