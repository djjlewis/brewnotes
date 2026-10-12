from brewnotes.brew import Change
from brewnotes.report import Item, fetch_problem
from brewnotes.sources import Notes
from brewnotes.triage import Severity, Triage


def item(name: str, error: str = "") -> Item:
    return Item(
        Change(name=name, kind="formula", old="1.0", new="1.1"),
        Notes(error=error),
        Triage(Severity.UNCHECKED if error else Severity.MINOR, "tldr"),
    )


def test_rate_limited_packages_get_one_message_with_the_count_and_the_fix() -> None:
    items = [item("a", "rate limited"), item("b", "rate limited"), item("c")]

    message = fetch_problem(items)

    assert message is not None
    assert "2 packages" in message and "gh auth login" in message


def test_no_message_when_every_package_was_checked() -> None:
    assert fetch_problem([item("a"), item("b")]) is None
