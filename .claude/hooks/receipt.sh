#!/bin/bash
# Stop hook: a short receipt of what is committed, pushed and live, shown to the user after each turn.
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)" || exit 0
notes="$HOME/agua-gdl-notes"

dirty=$(git status --porcelain | wc -l | tr -d ' ')
ahead=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo "?")
line="repo: $dirty uncommitted, $ahead unpushed"

if [ -d "$notes/.git" ]; then
  nd=$(git -C "$notes" status --porcelain | wc -l | tr -d ' ')
  na=$(git -C "$notes" rev-list --count @{u}..HEAD 2>/dev/null || echo "?")
  line="$line · notes: $nd uncommitted, $na unpushed"
fi

# The live API commit, cached for 5 minutes so the hook stays fast.
cache="${TMPDIR:-/tmp}/agua-gdl-live-sha"
if [ ! -f "$cache" ] || [ -n "$(find "$cache" -mmin +5 2>/dev/null)" ]; then
  curl -s -m 3 https://api.aguagdl.com/version | sed -n 's/.*"sha":"\([0-9a-f]*\)".*/\1/p' > "$cache"
fi
live=$(cat "$cache" 2>/dev/null)
if [ -n "$live" ] && git cat-file -e "$live^{commit}" 2>/dev/null; then
  line="$line · API live ${live:0:7}, $(git rev-list --count "$live"..origin/main) behind main"
else
  line="$line · API live version unknown"
fi

if [ -f "$notes/STATE.md" ]; then
  asof=$(sed -n 's/.*`~\/agua-gdl` at `\([0-9a-f]*\)`.*/\1/p' "$notes/STATE.md" | head -1)
  [ -n "$asof" ] && git cat-file -e "$asof^{commit}" 2>/dev/null &&
    line="$line · STATE.md $(git rev-list --count "$asof"..HEAD) commits old"
fi

printf '{"systemMessage": "%s"}\n' "$line"
