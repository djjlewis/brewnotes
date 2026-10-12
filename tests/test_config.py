from pathlib import Path

import pytest

from brewnotes.config import ConfigError, load_config


@pytest.mark.parametrize(
    ("toml", "setting"),
    [
        ('workers = "4"\n', "workers"),
        ("workers = 0\n", "workers"),
        ('colour = "red"\n', "colour"),
    ],
)
def test_a_bad_setting_stops_the_run_and_names_the_setting(tmp_path: Path, toml: str, setting: str) -> None:
    path = tmp_path / "config.toml"
    path.write_text(toml)

    with pytest.raises(ConfigError, match=setting):
        load_config(path)


def test_an_unknown_backend_lists_the_allowed_ones(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('backend = "claude"\n')

    with pytest.raises(ConfigError, match="claude-cli, api, none"):
        load_config(path)


def test_the_default_config_written_on_first_run_loads(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "config.toml")

    assert cfg.backend == "claude-cli"
