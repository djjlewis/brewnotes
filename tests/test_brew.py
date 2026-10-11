from datetime import datetime

from brewnotes.brew import Installed, changed_since

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
