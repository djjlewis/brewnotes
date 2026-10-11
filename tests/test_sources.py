from datetime import datetime
from typing import Any

from brewnotes.brew import Change
from brewnotes.sources import PAGE_SIZE, fetch_notes

REPO_URL = "https://github.com/acme/tool/archive/refs/tags/v1.3.0.tar.gz"


class FakeGitHub:
    """Stands in for the GitHub API: serves canned releases (newest first) and repo files."""

    def __init__(self, releases: list[dict[str, Any]] | None = None, files: dict[str, str] | None = None):
        self._releases = releases or []
        self._files = files or {}

    def releases(self, repo: str, page: int, per_page: int) -> list[dict[str, Any]] | None:
        return self._releases[(page - 1) * per_page : page * per_page]

    def root_files(self, repo: str) -> list[str] | None:
        return list(self._files)

    def read_file(self, repo: str, name: str) -> str | None:
        return self._files.get(name)


def release(tag: str, published: str = "2026-10-01T00:00:00Z", prerelease: bool = False) -> dict[str, Any]:
    return {
        "tag_name": tag,
        "body": f"notes for {tag}",
        "html_url": f"https://github.com/acme/tool/releases/tag/{tag}",
        "published_at": published,
        "prerelease": prerelease,
        "draft": False,
    }


def change(old: str | None, new: str, urls: list[str] | None = None) -> Change:
    return Change(name="tool", kind="formula", old=old, new=new, urls=urls or [REPO_URL])


def headings(text: str) -> list[str]:
    return [line.split(" ")[1] for line in text.splitlines() if line.startswith("## ")]


def test_includes_releases_after_old_up_to_new_newest_first() -> None:
    gh = FakeGitHub([release("v1.4.0"), release("v1.3.0"), release("v1.2.1"), release("v1.2.0")])

    notes = fetch_notes(gh, change("1.2.0", "1.3.0"))

    assert headings(notes.text) == ["v1.3.0", "v1.2.1"]


def test_links_to_new_release_and_diff_from_old_tag() -> None:
    gh = FakeGitHub([release("v1.3.0"), release("v1.2.0")])

    notes = fetch_notes(gh, change("1.2.0", "1.3.0"))

    assert notes.links[0] == ("release notes", "https://github.com/acme/tool/releases/tag/v1.3.0")
    assert ("diff", "https://github.com/acme/tool/compare/v1.2.0...v1.3.0") in notes.links


def test_monorepo_keeps_only_the_tag_family_of_the_new_version() -> None:
    gh = FakeGitHub([release("rust-v0.5.0"), release("sdk-v0.4.5"), release("rust-v0.4.0")])

    notes = fetch_notes(gh, change("0.4.0", "0.5.0"))

    assert headings(notes.text) == ["rust-v0.5.0"]


def test_skips_prereleases_between_versions() -> None:
    gh = FakeGitHub([release("v2.0.0"), release("v2.0.0-rc1", prerelease=True), release("v1.9.0")])

    notes = fetch_notes(gh, change("1.9.0", "2.0.0"))

    assert headings(notes.text) == ["v2.0.0"]


def test_unknown_old_version_takes_releases_in_the_window_plus_the_current_one() -> None:
    gh = FakeGitHub(
        [
            release("v1.3.0", published="2026-08-01T00:00:00Z"),
            release("v1.2.0", published="2026-07-20T00:00:00Z"),
            release("v1.1.0", published="2026-07-13T00:00:00Z"),
        ]
    )

    notes = fetch_notes(gh, change(None, "1.3.0"), since=datetime(2026, 7, 15))

    assert headings(notes.text) == ["v1.3.0", "v1.2.0"]


def test_pages_back_until_the_old_version() -> None:
    newer = [release(f"v2.{n}.0") for n in range(PAGE_SIZE + 5, 0, -1)]
    gh = FakeGitHub([*newer, release("v1.0.0")])

    notes = fetch_notes(gh, change("1.0.0", f"2.{PAGE_SIZE + 5}.0"))

    assert headings(notes.text)[-1] == "v2.1.0"


def test_falls_back_to_the_changelog_section_for_the_range() -> None:
    changelog = "# Changelog\n\n## 1.3.0\n- new thing\n\n## 1.2.1\n- fix\n\n## 1.2.0\n- old\n"
    gh = FakeGitHub(files={"README.md": "", "CHANGELOG.md": changelog})

    notes = fetch_notes(gh, change("1.2.0", "1.3.0"))

    assert notes.source == "changelog"
    assert notes.text == "## 1.3.0\n- new thing\n\n## 1.2.1\n- fix\n"


def test_github_docs_urls_are_not_mistaken_for_repos() -> None:
    gh = FakeGitHub([release("v1.3.0")])
    c = change("1.2.0", "1.3.0", urls=["https://docs.github.com/en/copilot/about"])
    c.homepage = "https://docs.github.com/en/copilot/about"

    notes = fetch_notes(gh, c)

    assert (notes.repo, notes.text) == (None, "")
    assert notes.links == [("homepage", "https://docs.github.com/en/copilot/about")]


def test_a_release_candidate_sorts_before_its_release() -> None:
    gh = FakeGitHub([release("v2.0.0"), release("v2.0.0-rc1", prerelease=True)])

    notes = fetch_notes(gh, change("2.0.0-rc1", "2.0.0"))

    assert headings(notes.text) == ["v2.0.0"]


def test_a_backport_among_newer_releases_does_not_stop_paging() -> None:
    page_one = [release(f"v2.{n}.0") for n in range(30, 1, -1)] + [release("v1.9.9")]
    gh = FakeGitHub([*page_one, release("v2.1.0"), release("v2.0.0")])

    notes = fetch_notes(gh, change("2.0.0", "2.30.0"))

    assert headings(notes.text)[-1] == "v2.1.0"


def test_diff_link_stays_within_the_tag_family() -> None:
    gh = FakeGitHub([release("rust-v0.5.0"), release("sdk-v0.4.0"), release("rust-v0.4.0")])

    notes = fetch_notes(gh, change("0.4.0", "0.5.0"))

    assert ("diff", "https://github.com/acme/tool/compare/rust-v0.4.0...rust-v0.5.0") in notes.links


def test_no_diff_link_when_the_new_version_has_no_release() -> None:
    gh = FakeGitHub([release("v1.2.1"), release("v1.2.0")])

    notes = fetch_notes(gh, change("1.2.0", "1.3.0"))

    assert [label for label, _ in notes.links if label == "diff"] == []


def test_a_changelog_bullet_mentioning_the_old_version_does_not_end_the_section() -> None:
    changelog = "## 1.3.0\n- Fix regression from 1.2.0\n- Faster\n\n## 1.2.0\n- old\n"
    gh = FakeGitHub(files={"CHANGELOG.md": changelog})

    notes = fetch_notes(gh, change("1.2.0", "1.3.0"))

    assert notes.text == "## 1.3.0\n- Fix regression from 1.2.0\n- Faster\n"


def test_changelog_section_ends_below_an_old_version_with_no_heading() -> None:
    changelog = "## 1.3.0\n- new\n\n## 1.2.1\n- fix\n\n## 1.1.0\n- older\n"
    gh = FakeGitHub(files={"CHANGELOG.md": changelog})

    notes = fetch_notes(gh, change("1.2.0", "1.3.0"))

    assert notes.text == "## 1.3.0\n- new\n\n## 1.2.1\n- fix\n"


def test_a_monorepo_page_with_another_familys_old_version_does_not_stop_paging() -> None:
    newer = [release(f"rust-v0.9.{n}") for n in range(14, 0, -1)]
    older = [release(f"rust-v0.6.{n}") for n in range(15, 0, -1)]
    gh = FakeGitHub([*newer, release("sdk-v0.4.0"), *older, release("rust-v0.5.0"), release("rust-v0.4.0")])

    notes = fetch_notes(gh, change("0.4.0", "0.9.14"))

    assert headings(notes.text)[-1] == "rust-v0.5.0"


def test_a_python_style_prerelease_sorts_before_its_release() -> None:
    gh = FakeGitHub([release("v1.2.0"), release("v1.2.0b1", prerelease=True)])

    notes = fetch_notes(gh, change("1.2.0b1", "1.2.0"))

    assert headings(notes.text) == ["v1.2.0"]


def test_numbered_previews_are_different_versions() -> None:
    gh = FakeGitHub(
        [release("v3.0.0-preview2", prerelease=True), release("v3.0.0-preview1", prerelease=True)]
    )

    notes = fetch_notes(gh, change("3.0.0-preview1", "3.0.0-preview2"))

    assert headings(notes.text) == ["v3.0.0-preview2"]


def test_changelog_body_lines_starting_with_a_number_are_not_headings() -> None:
    changelog = "Version 1.3.0\n0.5 GB less memory\n2.5x faster startup\n\nVersion 1.2.0\n- old\n"
    gh = FakeGitHub(files={"CHANGELOG.md": changelog})

    notes = fetch_notes(gh, change("1.2.0", "1.3.0"))

    assert notes.text == "Version 1.3.0\n0.5 GB less memory\n2.5x faster startup\n"


def test_changelog_section_ends_at_an_old_version_heading_of_a_higher_level() -> None:
    changelog = "## 2.1.0\n- a\n\n# 2.0.0\n- major stuff\n\n## 1.9.0\n- b\n"
    gh = FakeGitHub(files={"CHANGELOG.md": changelog})

    notes = fetch_notes(gh, change("2.0.0", "2.1.0"))

    assert notes.text == "## 2.1.0\n- a\n"
