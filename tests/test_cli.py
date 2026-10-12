from pathlib import Path

import pytest

from brewnotes.brew import Change
from brewnotes.cli import main, parse_args, split_hidden_dependencies
from brewnotes.sources import Notes


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


def test_hidden_dependencies_are_left_out_but_their_failures_are_kept() -> None:
    failed_dep = Change(name="libfoo", kind="formula", old="1", new="2", requested=False)
    security_dep = Change(name="openssl", kind="formula", old="3.5", new="3.6", requested=False)
    leaf = Change(name="jq", kind="formula", old="1.7", new="1.8")
    fetched = [
        (failed_dep, Notes(error="rate limited")),
        (security_dep, Notes(text="Fixes CVE-2026-1234")),
        (leaf, Notes(error="rate limited")),
    ]

    shown, dependency_errors = split_hidden_dependencies(fetched, include_dependencies=False)

    assert ([c.name for c, _ in shown], dependency_errors) == (["openssl", "jq"], ["rate limited"])
