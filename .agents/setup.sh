#!/bin/sh
# Install the pinned skills for Claude Code, Codex, and Copilot, and enable the git hooks.
# Copier runs this on copy and update. Run it yourself after cloning.
set -e
cd "$(git rev-parse --show-toplevel)"

git config core.hooksPath .githooks

npx -y skills@1.7.2 add mattpocock/skills#v1.3.1 \
  -s tdd -s code-review -s codebase-design -s grill-with-docs -s grilling -s domain-modeling \
  -a claude-code -a codex -a github-copilot -y

npx -y skills@1.7.2 add https://github.com/cursor/plugins/tree/11713c683fe4add4fd403ea880580abbc9e0875f/pstack/skills \
  -s unslop -s technical-writing \
  -a claude-code -a codex -a github-copilot -y

# The local implement skill is in the template, so link it for Claude Code by hand.
mkdir -p .claude/skills
ln -sfn ../../.agents/skills/implement .claude/skills/implement
