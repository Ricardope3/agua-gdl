#!/bin/bash
# SessionStart hook: what a new session needs before it touches anything. Stdout goes into context.
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)" || exit 0
echo "## Repo state"
git status -sb | head -15
unpushed=$(git log --oneline @{u}..HEAD 2>/dev/null)
[ -n "$unpushed" ] && printf 'Unpushed:\n%s\n' "$unpushed"
[ -n "$(git stash list)" ] && echo "Stashes exist (git stash list): someone's work may be parked there."
state="$HOME/agua-gdl-notes/STATE.md"
if [ -f "$state" ]; then
  echo "## ~/agua-gdl-notes/STATE.md (Now and Open; read the file for the rest)"
  awk '/^## Now/{p=1} /^## (Upcoming|Rules)/{p=0} p' "$state" | head -60
fi
