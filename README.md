# brewnotes

`brewnotes` reads the release notes behind your Homebrew updates and reports the ones that matter. Security fixes and breaking changes come first, with a one-line summary, the action you need to take, and links. Minor fixes collapse to a single line of names.

```
🔴 Security fixes           CVEs and advisories
🟠 Breaking changes         removed flags, changed defaults, migrations ("⚠ action needed")
🟢 Notable enhancements     features you would want to know about
⚪ Minor                    bug fixes and tweaks, names only (use --all)
❔ Couldn't find notes      names only, with links
⚠️ Couldn't check          GitHub failed; names grouped by the reason
```

## Install

You need `uv`. The default backend also needs the `claude` CLI, logged in.

`gh` is optional. Without a logged-in `gh`, `brewnotes` reads GitHub anonymously, which GitHub limits to 60 requests an hour. That covers a typical `preview`, but a long `recap` can run out. Run `gh auth login` to raise the limit to 5,000.

```bash
uv tool install --editable .
```

## Use

```bash
brewnotes                    # same as `brewnotes preview`
brewnotes preview            # what `brew upgrade` would change; runs `brew update` first
brewnotes preview --greedy   # also include casks that update themselves
brewnotes recap              # what changed since the last run
brewnotes recap --since 7d   # what changed in the last 7 days
brewnotes config             # print the config file path
```

Each run prints to the terminal and saves a markdown report in `~/Documents/brewnotes/`. Add `--no-save` to skip the file and `--all` to expand the minor items.

To review before you upgrade, add this function to your shell rc:

```bash
bup() { brewnotes preview && read -q "?Upgrade? [y/N] " && echo && brew upgrade && brewnotes recap --no-save; }
```

The recap reuses the cached triage from the preview, so it costs nothing extra.

## How it works

1. `preview` reads `brew outdated`. `recap` compares installed versions with the snapshot saved by the last run. With `--since`, it uses install times instead.
2. The report covers formulae you installed yourself and all casks. A dependency appears only when its notes mention security. Add `--deps` to include every dependency.
3. `brewnotes` finds the GitHub repo in the Homebrew metadata. It reads every release between your version and the new one. If the repo has no releases, it reads the section of `CHANGELOG`, `NEWS`, or a similar file.
4. If GitHub can't be checked, for example because of the rate limit, the package appears under "Couldn't check" with the reason, instead of looking like it has no notes.
5. Claude assigns each package a severity and writes the summary. If no notes were found, the `claude-cli` backend lets Claude search the web for them. Results are cached in `~/.cache/brewnotes/` per version range.

## Configure

The first run writes `~/.config/brewnotes/config.toml` with comments. The settings you are most likely to change are listed below.

| Setting | Default | Purpose |
|---|---|---|
| `backend` | `claude-cli` | `claude-cli` uses your Claude login and counts against your subscription limits. `api` uses the Anthropic API with `ANTHROPIC_API_KEY`. `none` uses keyword matching only. |
| `api_model` | `claude-opus-5-5` | The model for the `api` backend. |
| `interests` | developer tools | Free text that tells Claude what counts as notable for you. |
| `ignore` | `[]` | Package names to leave out of reports. |
| `web_lookup` | `true` | Lets the `claude-cli` backend search the web when no GitHub notes exist. |
| `workers` | `4` | How many packages to fetch and triage at once. |

`brewnotes` checks the file when it starts. An unknown setting or a value of the wrong type stops the run with a message that names the setting.

Pass `--backend` to override the backend for one run.

## Develop

[AGENTS.md](AGENTS.md) lists the checks, and [the coding guidelines](docs/coding-guidelines.md) list the standards.
