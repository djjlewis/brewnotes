"""The config file, plus where state and cache files live."""

import tomllib
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
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


TYPE_NAMES = {str: "a string", bool: "true or false", int: "a whole number", list: "a list of strings"}


def ensure_config(path: Path) -> None:
    """Writes the commented default config if there is none."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_CONFIG)


def load_config(path: Path) -> Config:
    """Reads the config, writing the default first if there is none. Raises ConfigError for
    invalid TOML, an unknown setting, or a value of the wrong type or range."""
    ensure_config(path)
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from e
    defaults = asdict(Config())
    for key, value in data.items():
        if key not in defaults:
            raise ConfigError(f"{path}: unknown setting `{key}`")
        _check_type(path, key, value, type(defaults[key]))
    if data.get("backend", "claude-cli") not in BACKENDS:
        raise ConfigError(f"{path}: `backend` must be one of {', '.join(BACKENDS)}, not {data['backend']!r}")
    if data.get("workers", 1) < 1:
        raise ConfigError(f"{path}: `workers` must be at least 1, not {data['workers']}")
    return Config(**data)


def _check_type(path: Path, key: str, value: object, expected: type) -> None:
    strings = isinstance(value, list) and all(isinstance(v, str) for v in value)
    if type(value) is not expected or (expected is list and not strings):
        raise ConfigError(f"{path}: `{key}` must be {TYPE_NAMES[expected]}, not {value!r}")
