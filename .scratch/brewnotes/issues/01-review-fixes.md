# Fix the spec review's wrong behaviours

Status: claimed
Branch: fix/review-findings

The `/code-review` Spec axis found 12 behaviours that contradict [the spec](../spec.md). Fix each one test-first. Standards findings and scope questions are out of scope here. They wait on the owner.

## Acceptance examples

1. A `claude -p` call that runs past its timeout fails that package only. The run continues.
2. `--backend api` with no credentials falls back to heuristics, and the problem names `ANTHROPIC_API_KEY`.
3. An update from 2.0.0-rc1 to 2.0.0, with releases `v2.0.0` and `v2.0.0-rc1`, shows the notes for `v2.0.0` only.
4. The old version is 2.0.0. Page 1 holds `v2.30.0` down to `v2.2.0` and then a backport `v1.9.9`. Page 2 holds `v2.1.0` and `v2.0.0`. The notes include `v2.1.0`.
5. An update from 0.4.0 to 0.5.0, with tags `rust-v0.5.0`, `sdk-v0.4.0`, and `rust-v0.4.0`, links the diff `compare/rust-v0.4.0...rust-v0.5.0`. If the new version has no release, there is no diff link.
6. A changelog bullet that mentions the old version does not end the section. If the old version has no heading, the section ends at the first heading below it.
7. With `--since 2026-07-15`, the notes leave out a release published on 2026-07-13.
8. `recap --since` skips a cask reinstalled at the same version, such as `latest`.
9. `brewnotes --all` runs `preview` with `--all`.
10. A major bump with no notes is `unknown`.
11. A cached answer is still used after the backend becomes unavailable.
12. A transient `claude -p` API error fails that package only. An authentication error stops LLM triage and says to run `/login`.

Boundaries under test: `fetch_notes`, `Triager.triage`, `llm.claude_cli` and `llm.anthropic_api` (with a fake `claude` executable on `PATH` and no API credentials), `brew.changed_since`, and `cli.parse_args`.

## Comments

A second `/code-review` of commit b674a2a found regressions and gaps in these fixes. The branch now also covers them, each with a test that failed first:

- Paging judges each page by the target's tag family, so an old version from another product in a monorepo doesn't stop it.
- Python-style prereleases (`1.2.0b1`) sort before their release, and `3.0.0-preview1` and `3.0.0-preview2` are different versions. The prerelease words live in one list in `versions.py`.
- Changelog body lines that start with a number (`0.5 GB less memory`) are not headings. Only a heading of the same or a higher level ends a section.
- Only login errors stop the `claude-cli` backend. "Rate limit exceeded for this API key" fails one package.
- A major bump with no notes and no web lookup skips the LLM and is `unknown`. The spec line now says so.
- `--no-cache` applies when the backend is unavailable from the start.
- A missing `claude` executable stops the backend with a message. This path already existed and now has a test.

Example 8 is open. The code skips only casks versioned `latest`. Skipping every package whose snapshot version equals the installed one would hide real updates whenever the snapshot was saved after an upgrade. The owner decides which rule the spec should state.

Verification on the branch: `uv run ruff format --check . && uv run ruff check . && uv run mypy . && uv run pytest` passes with 36 tests. A real `brewnotes --no-update --greedy --no-save` run against Homebrew printed the triaged report.
