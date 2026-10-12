# brewnotes v1

Homebrew updates arrive most days, and the owner rarely knows what changed. `brewnotes` reads the release notes for those updates and reports what matters: security fixes, breaking changes, and notable enhancements. It collapses trivial fixes so the report stays short, and it links to the full notes.

Decisions in this spec were agreed with the owner on 2026-10-11.

## Modes

- `brewnotes preview` reports what `brew upgrade` would change. It runs `brew update` first unless given `--no-update`. `--greedy` includes casks that update themselves.
- `brewnotes recap` reports what changed since the last run. It compares installed versions with the snapshot saved by the previous run, then saves a new snapshot.
- `brewnotes recap --since <7d|48h|2w|ISO date>` reports packages installed after that time instead. The old version comes from the snapshot when one exists, and is otherwise unknown.
- With no snapshot and no `--since`, `recap` covers the last 7 days.
- The first `preview` saves a snapshot, so the next `recap` has a baseline.
- `brewnotes` with no subcommand runs `preview`.

## Scope

- Reports cover formulae installed on request (or listed by `brew leaves`) and all casks.
- A dependency appears only when its notes look security-related. `--deps` or `include_dependencies = true` includes every changed dependency.
- Packages in the config's `ignore` list never appear.
- In `preview`, an update whose old and new versions are the same (such as a cask versioned `latest`) is not a change.
- `recap --since` skips casks versioned `latest`. It still reports a package whose snapshot version matches the installed one, because the snapshot may have been saved after the upgrade.

## Finding the notes

1. Find the GitHub repo in the package's homepage and download URLs. Only `github.com` URLs count, not `docs.github.com`.
   - Use `gh api` when `gh` is installed and logged in. Otherwise call the GitHub API anonymously, so the tool works without `gh`.
   - A 404 means the repo or file doesn't exist, which counts as no notes. Any other failure, such as a rate limit or a network error, marks the package "couldn't check" with the reason.
2. Read the releases after the old version, up to and including the new one, newest first.
   - Skip prereleases unless the new version is one.
   - In a repo that tags several products, keep only the tag family of the new version (`rust-v0.5.0`, not `sdk-v0.4.5`).
   - When the old version is unknown, take releases published in the `--since` window plus the release for the new version.
   - Page back through releases until the old version is reached.
3. If there are no matching releases, read the section of the root `CHANGELOG`, `NEWS`, `CHANGES`, `HISTORY`, or `RELEASE-NOTES` file, from the new version's heading down to the old version's heading.
4. Cut notes longer than 60,000 characters and mark them truncated.
5. Link to the new release, a compare view from the old tag to the new tag when both exist, and the homepage.

## Triage

Each package gets one severity, the highest that applies:

- `security`: fixes a vulnerability (a CVE, an advisory, or a security fix).
- `breaking`: removes or renames commands, flags, config, or APIs; changes defaults; drops platform support; or needs migration steps.
- `notable`: features or improvements a typical user would notice.
- `minor`: bug fixes, performance, docs, refactors, or dependency bumps.
- `unknown`: no notes found.
- `unchecked`: GitHub couldn't be checked, and no notes came from elsewhere. Only brewnotes sets this. Claude never returns it.

Each package also gets a one-sentence TL;DR, up to 5 highlights, the action needed (if any), and the CVE or advisory IDs mentioned. The config's `interests` text tells Claude what the owner counts as notable.

Backends, chosen by `backend` in the config or `--backend`:

- `claude-cli` (default) runs `claude -p` with the owner's subscription login. When no notes were found for a requested package and `web_lookup` is on, Claude may search the web for them and return the URL it used.
- `api` uses the Anthropic SDK with `api_model` (default `claude-opus-5-5`). It is an option because Max plans now include monthly API credit. It asks for low effort, because sorting notes into a few severities is a simple task, and it turns on server-side fallback, so notes full of CVE details that trip a safety filter still get an answer.
- `none` uses keyword heuristics only.

Failure handling:

- If the backend can't work at all (an expired login or a missing key), the run uses heuristics for every remaining package and prints why, with the fix.
- If one request fails, that package gets the heuristic result with the error in its TL;DR. Other packages still use the LLM.
- A package with no notes and no web lookup skips the LLM and is `unknown`.
- Results are cached per package, version range, and notes text, so a `recap` after a `preview` doesn't triage again. `--no-cache` bypasses the cache.

## Output

- The terminal shows a summary count, then sections in severity order. Security, breaking, and notable items show the version change, TL;DR, highlights, action, CVEs, and clickable links. Minor and unknown items collapse to one line of names unless `--all` is given.
- A major version bump is marked. Browser-style and date-stamped versions (a leading number of 50 or more) don't count as major.
- Packages that couldn't be checked get their own "Couldn't check" section with the reason. The run prints one message with the count. Hidden dependencies that couldn't be checked are not listed, but the message counts them separately ("27 packages and 39 dependencies"). When any failed for a rate limit, the message says that a logged-in `gh` raises the limit.
- If `brew update` fails, `preview` prints a warning and reports from the last successful update.
- Each run with updates saves a markdown report to `reports_dir` (default `~/Documents/brewnotes`) unless given `--no-save`. Minor and unknown items appear there as a table.
- `brewnotes config` prints the config file path. The first run writes a commented default config.
- A config file with an unknown setting, a value of the wrong type, an unknown backend, or `workers` below 1 stops the run with a message naming the setting.

## Acceptance examples

- Releases `v1.4.0`, `v1.3.0`, `v1.2.1`, and `v1.2.0`, updating 1.2.0 to 1.3.0: the notes hold `v1.3.0` then `v1.2.1`.
- The same update links to the `v1.3.0` release page and to `compare/v1.2.0...v1.3.0`.
- Tags `rust-v0.5.0`, `sdk-v0.4.5`, and `rust-v0.4.0`, updating 0.4.0 to 0.5.0: the notes hold only `rust-v0.5.0`.
- Releases `v2.0.0`, `v2.0.0-rc1` (prerelease), and `v1.9.0`, updating 1.9.0 to 2.0.0: the notes hold only `v2.0.0`.
- Unknown old version, `--since 2026-07-15`, releases published 2026-08-01 (`v1.3.0`), 2026-07-20 (`v1.2.0`), and 2026-06-01 (`v1.1.0`), new version 1.3.0: the notes hold `v1.3.0` and `v1.2.0`.
- 35 newer releases before `v1.0.0`, updating from 1.0.0: the notes reach back to the release just after 1.0.0.
- No releases, and a `CHANGELOG.md` with headings `1.3.0`, `1.2.1`, `1.2.0`, updating 1.2.0 to 1.3.0: the notes hold the `1.3.0` and `1.2.1` sections.
- A package whose only URL is on `docs.github.com` has no repo and no notes, and links to its homepage.
- The backend reports an expired login on the first package: that package and every later one get heuristic results, and the run explains the problem.
- One request times out: that package's TL;DR says the triage failed, and the next package uses the LLM.
- A requested package with no notes, on `claude-cli` with web lookup: the result carries the URL Claude found.

## Out of scope for v1

macOS notifications, an HTML report, scheduled runs, and wrapping `brew upgrade` (the README shows a shell function instead).
