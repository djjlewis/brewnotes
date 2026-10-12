# Decide how to report dependencies GitHub couldn't check

Status: resolved
Branch: fix/unchecked-dependencies

A dependency appears in the report only when its notes look security-related. If GitHub can't be checked for a dependency, there are no notes to look at, so the report drops it without a word. The spec says a failure marks the package "couldn't check", so this is a gap. The `/code-review` of ticket 02 found it.

A `recap` over a few weeks can include dozens of changed dependencies, so the owner needs to choose:

1. List every unchecked dependency under "Couldn't check". This is complete, but it floods the section on a rate-limited run.
2. Count unchecked dependencies in the rate-limit message without listing them, for example "15 packages and 40 dependencies".
3. Keep dropping them, and say so in the spec.

The owner chose option 2 on 2026-10-12.

## Acceptance examples

1. Two packages and three hidden dependencies were rate-limited. The message says GitHub couldn't be checked for 2 packages and 3 dependencies, gives `rate limited: 5`, and gives the `gh auth login` hint.
2. Only one hidden dependency couldn't be checked. The message says "1 dependency" and gives the hint.
3. Unchecked dependencies don't appear in the "Couldn't check" section.

Boundary under test: `report.fetch_problem`, which takes the shown items and the reasons for hidden dependencies.

## Comments

Examples 1 and 2 have tests at `report.fetch_problem`, and example 3 has a test at `cli.split_hidden_dependencies`. Each test failed before its change.

The message counts hidden dependencies for every failure reason, not only rate limits, because the run's message already covered every reason.

`/code-review` of commit 8d8f77d found no spec problems. Its standards findings are fixed. `Run.process` returns the dependency failures with the items instead of storing them on `Run`, and the dependency filter is now the pure function `split_hidden_dependencies`, which the example 3 test drives.

The checks pass with 60 tests. A real `GH_TOKEN=invalid brewnotes recap --since 21d --backend none --no-save` printed "GitHub couldn't be checked for 27 packages and 39 dependencies (rate limited: 66)" with the `gh auth login` hint. The "Couldn't check" section listed the 27 packages only.
