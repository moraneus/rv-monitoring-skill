#!/usr/bin/env bash
# Install the rv skill for Claude Code (and compatible agent harnesses).
#
#   ./install.sh              # user-level:   ~/.claude/skills/rv
#   ./install.sh --project    # project-level: ./.claude/skills/rv (run from
#                             # the project root)
set -euo pipefail
cd "$(dirname "$0")"

if [ "${1:-}" = "--project" ]; then
  TARGET="$(pwd -P)"
  TARGET="${OLDPWD:-$TARGET}/.claude/skills/rv"
else
  TARGET="$HOME/.claude/skills/rv"
fi

mkdir -p "$(dirname "$TARGET")"
rm -rf "$TARGET"
cp -R skills/rv "$TARGET"

echo "installed: $TARGET"
echo "target projects need:  pip install behave-rv"
echo "invoke interactively with /rv, or let the agent use it when monitoring is relevant"
