from pathlib import Path

import pytest

from brewnotes.cli import main, parse_args


def test_flags_without_a_subcommand_go_to_preview() -> None:
    args = parse_args(["--all", "--no-update"])

    assert (args.cmd, args.all, args.no_update) == ("preview", True, True)


def test_config_prints_the_path_even_when_the_file_is_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = tmp_path / "brewnotes" / "config.toml"
    path.parent.mkdir()
    path.write_text("colour = 1\n")

    main(["config"])

    assert capsys.readouterr().out.strip() == str(path)
