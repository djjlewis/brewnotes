# Fix the spec review's wrong behaviours

Status: claimed
Branch: fix/review-findings

The `/code-review` Spec axis found 12 behaviours that contradict [the spec](../spec.md). Fix each one test-first. Standards findings and scope questions are out of scope here; they wait on the owner.

## Acceptance examples

1. A `claude -p` call that runs past its timeout fails that package only. The run continues.
2. `--backend api` with no credentials falls back to heuristics, and the problem names `ANTHROPIC_API_KEY`.
3. Updating 2.0.0-rc1 to 2.0.0 with releases `v2.0.0` and `v2.0.0-rc1`: the notes hold `v2.0.0`.
4. Old 2.0.0. Page 1 holds `v2.30.0` down to `v2.2.0` and then a backport `v1.9.9`. Page 2 holds `v2.1.0` and `v2.0.0`. The notes include `v2.1.0`.
5. Tags `rust-v0.5.0`, `sdk-v0.4.0`, and `rust-v0.4.0`, updating 0.4.0 to 0.5.0: the diff link is `compare/rust-v0.4.0...rust-v0.5.0`. If the new version has no release, there is no diff link.
6. A changelog bullet that mentions the old version does not end the section. If the old version has no heading, the section ends at the first heading below it.
7. With `--since 2026-07-15`, a release published on 2026-07-13 is left out.
8. `recap --since` skips a cask reinstalled at the same version, such as `latest`.
9. `brewnotes --all` runs `preview` with `--all`.
10. A major bump with no notes is `unknown`.
11. A cached answer is still used after the backend becomes unavailable.
12. A transient `claude -p` API error fails that package only. An authentication error stops LLM triage and says to run `/login`.

Boundaries under test: `fetch_notes`, `Triager.triage`, `llm.claude_cli` and `llm.anthropic_api` (with a fake `claude` executable on `PATH` and no API credentials), `brew.changed_since`, and `cli.parse_args`.

## Comments
