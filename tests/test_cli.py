from brewnotes.cli import parse_args


def test_flags_without_a_subcommand_go_to_preview() -> None:
    args = parse_args(["--all", "--no-update"])

    assert (args.cmd, args.all, args.no_update) == ("preview", True, True)
