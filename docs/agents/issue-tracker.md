# Issue tracker: local markdown

Tickets live as markdown files in `.scratch/`, which is committed.

- One directory per feature or effort: `.scratch/<slug>/`.
- A spec, when one is needed, is `.scratch/<slug>/spec.md`.
- One file per ticket: `.scratch/<slug>/issues/<NN>-<slug>.md`, numbered from `01`.
- A `Status:` line near the top records `open`, `claimed`, `resolved`, or `cancelled`.
- Discussion appends under a `## Comments` heading at the bottom.

When a skill says "publish to the issue tracker", create the file. When it says "fetch the relevant ticket", read the file the user names.
