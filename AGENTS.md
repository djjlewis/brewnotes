# brewnotes

A triaged TL;DR of release notes for your Homebrew updates: security fixes and breaking changes first, trivia collapsed.

## Checks

- Python: `uv run ruff format --check . && uv run ruff check . && uv run mypy . && uv run pytest`

## How we work

- Build only what a current, named behaviour needs. KISS and YAGNI decide every design question: add a layer, option, or abstraction when a real behaviour or real duplication calls for it.
- Work in small vertical slices. Agree concrete examples of the behaviour first, then build test-first.
- Scope, architecture, and new dependencies are the owner's decisions. Ask; record the answer where the work is tracked.
- Keep modules cohesive and small, with one reason to change each. Split by responsibility, not into forwarding layers. The pre-commit hook rejects source files over 400 lines.
- Name modules for what they do. Generic `utils`, `helpers`, `common`, and `managers` modules hide that.
- Finish the agreed scope only. Record anything else you find as a ticket and leave unrelated code as it is.
- One agent owns implementation. Use subagents for bounded research and review.

Standards for code and tests are in [the coding guidelines](docs/coding-guidelines.md).

## Keep the output small

- The diff is the deliverable. Before finishing, delete code, parameters, tests, and docs whose removal breaks no agreed example.
- Write a document only when a named reader needs it now, and prefer updating an existing one. Summary, notes, and plan files are written only on request.
- Comments say why, not what.
- In replies, lead with the result and keep it short. End a session with one `Next:` line: one action and why.

## Writing

Before writing prose (docs, tickets, PR descriptions, commit messages), read `.agents/skills/unslop/SKILL.md` and apply it. For docs, also read `.agents/skills/technical-writing/SKILL.md`. Link to the single source of truth instead of restating it. Commit messages and PR descriptions carry no agent, tool, or model attribution.

## Done

A change is done when its agreed examples pass as tests, the checks pass, and `/code-review` leaves no correctness or scope findings. Report a skipped or blocked check as skipped.

## Agent skills

Start each ticket with `/implement`. Settle a decision with the owner through `/grill-with-docs`.

- Issue tracker: local markdown in `.scratch/`. See `docs/agents/issue-tracker.md`.
- Domain docs: single-context. See `docs/agents/domain.md`.
