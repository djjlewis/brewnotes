from datetime import datetime
from pathlib import Path

import pytest

from brewnotes.brew import Installed, changed_since, update

from .fakes import fake_executable

SINCE = datetime(2026, 10, 1)
AFTER = int(datetime(2026, 10, 5).timestamp())


def test_recap_since_skips_a_cask_reinstalled_at_the_same_version() -> None:
    before = {"cask:font-x": Installed(version="latest"), "formula:jq": Installed(version="1.8.1")}
    now = {
        "cask:font-x": Installed(version="latest", time=AFTER),
        "formula:jq": Installed(version="1.8.2", time=AFTER),
    }

    changes = changed_since(now, SINCE, before)

    assert [(c.name, c.old, c.new) for c in changes] == [("jq", "1.8.1", "1.8.2")]


def test_a_failed_brew_update_returns_the_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_executable(tmp_path, monkeypatch, "brew", 'echo "Error: Failed to update tap" >&2\nexit 1')

    assert update() == "Error: Failed to update tap"
