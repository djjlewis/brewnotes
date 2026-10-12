# Report fetch failures, check the config, and type the fixed value sets

Status: claimed
Branch: fix/standards-followups

The first `/code-review` Standards axis left these open. The owner decided them on 2026-10-12.

- Keep the `workers` setting, and check its type.
- Keep anonymous GitHub access, because a future open release should work without `gh`. If `gh` is installed but not logged in, use anonymous access too.
- Keep the `claude-cli` `model` setting. Keep the API backend's low effort and server-side fallback, and add them to the spec.
- Do the rest: say when GitHub couldn't be checked, check the config file on load, warn when `brew update` fails, and replace severity strings with an enum and the other fixed sets with `Literal` types.

## Acceptance examples

1. GitHub rate-limits the release request for a package. That package shows as "Couldn't check" with the reason `rate limited`, not as "Couldn't find notes".
2. The repo returns 404. That package has no notes and no error.
3. `gh api` exits with `HTTP 403: API rate limit exceeded`. The GitHub adapter raises a rate-limit error. With `HTTP 404`, it returns nothing.
4. Some packages couldn't be checked because of the rate limit. The run prints one message with the count, and it says how to get a higher limit.
5. A config file with `backend = "claude"` stops the run with a message that lists the allowed backends. So do `workers = "4"` and an unknown setting name.
6. `brew update` fails. The preview prints a warning and carries on from the last update.

Severity becomes a `StrEnum`. `Change.kind`, `Notes.source`, and `Config.backend` become `Literal` types. Behaviour doesn't change, so the existing tests cover them.

Boundaries under test: `fetch_notes` and `Triager.triage` with fakes, `GitHub` with a fake `gh` on `PATH`, `report.fetch_problem`, `load_config` with files in a temporary directory, and `brew.update` with a fake `brew` on `PATH`.

## Comments

Implemented test-first. Each of the six examples has a test that failed on behaviour before its fix.

- A web lookup after a GitHub failure that also finds nothing stays `unchecked`. Results for a package with a GitHub error are not cached, so the next run tries GitHub again.
- The GitHub adapter retries a 5xx once. The retry that used to live in `sources.py` is gone.
- `Config` is now frozen, and the CLI applies `--backend` and `--deps` with `dataclasses.replace`.
- The report's five lookup tables keyed by severity strings are now one `SECTIONS` table keyed by `Severity`.

Not covered: a dependency whose fetch fails is still dropped silently, because the dependency filter needs notes to look for security terms. Reporting every unchecked dependency would flood the report. This needs an owner decision if it matters.

Verification: `uv run ruff format --check . && uv run ruff check . && uv run mypy . && uv run pytest` passes with 51 tests. Two real runs:

- `brewnotes --no-update --greedy --no-save` triaged 11 pending updates with the owner's existing config.
- `GH_TOKEN=invalid brewnotes recap --since 21d --backend none --no-save` used anonymous access. It reported "GitHub couldn't be checked for 15 packages (rate limited: 15)" with the `gh auth login` hint, and listed those packages under "Couldn't check".
