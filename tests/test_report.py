from brewnotes.brew import Change
from brewnotes.report import Item, fetch_problem
from brewnotes.sources import Notes
from brewnotes.triage import Severity, Triage


def item(name: str, error: str = "", severity: Severity | None = None) -> Item:
    return Item(
        Change(name=name, kind="formula", old="1.0", new="1.1"),
        Notes(error=error),
        Triage(severity or (Severity.UNCHECKED if error else Severity.MINOR), "tldr"),
    )


def test_rate_limited_packages_get_one_message_with_the_count_and_the_fix() -> None:
    items = [item("a", "rate limited"), item("b", "rate limited"), item("c")]

    message = fetch_problem(items, [])

    assert message is not None
    assert "2 packages" in message and "gh auth login" in message


def test_no_message_when_every_package_was_checked() -> None:
    assert fetch_problem([item("a"), item("b")], []) is None


def test_the_message_counts_only_packages_left_unchecked() -> None:
    found_on_the_web = item("b", "rate limited", Severity.NOTABLE)

    message = fetch_problem([item("a", "rate limited"), found_on_the_web], [])

    assert message is not None and "for 1 package " in message


def test_unchecked_dependencies_are_counted_but_not_listed() -> None:
    items = [item("a", "rate limited"), item("b", "rate limited")]

    message = fetch_problem(items, ["rate limited"] * 3)

    assert message is not None
    assert "2 packages and 3 dependencies (rate limited: 5)" in message and "gh auth login" in message


def test_a_single_unchecked_dependency_still_gets_the_message() -> None:
    message = fetch_problem([item("a")], ["rate limited"])

    assert message is not None and "for 1 dependency (rate limited: 1)" in message
