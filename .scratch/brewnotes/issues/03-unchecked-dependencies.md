# Decide how to report dependencies GitHub couldn't check

Status: open

A dependency appears in the report only when its notes look security-related. If GitHub can't be checked for a dependency, there are no notes to look at, so the report drops it without a word. The spec says a failure marks the package "couldn't check", so this is a gap. The `/code-review` of ticket 02 found it.

A `recap` over a few weeks can include dozens of changed dependencies, so the owner needs to choose:

1. List every unchecked dependency under "Couldn't check". This is complete, but it floods the section on a rate-limited run.
2. Count unchecked dependencies in the rate-limit message without listing them, for example "15 packages and 40 dependencies".
3. Keep dropping them, and say so in the spec.

## Comments
