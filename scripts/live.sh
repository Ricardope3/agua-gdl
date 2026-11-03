#!/usr/bin/env bash
# What's live vs origin/main. GET only; always exits 0.
set -u
cd "$(dirname "$0")/.." || exit 0
git fetch -q origin main 2>/dev/null || echo "(git fetch failed; origin/main may be stale)"
main=$(git rev-parse origin/main)

sha=$(curl -fsS -m 10 https://api.aguagdl.com/version 2>/dev/null | sed -n 's/.*"sha":"\([^"]*\)".*/\1/p')
if [ -z "$sha" ] || [ "$sha" = unknown ] || [ "$sha" = dev ]; then
  echo "api:  unknown (no /version; deployed before it existed or without GIT_SHA)"
elif git cat-file -e "$sha^{commit}" 2>/dev/null; then
  echo "api:  ${sha:0:9}, $(git rev-list --count "$sha..$main") commits behind origin/main ($(git rev-list --count "$main..$sha") not on main)"
else
  echo "api:  ${sha:0:9} (not in local git)"
fi

# Site: Pages exposes no commit, so compare live bytes of the web/ files that
# changed in origin/main's last 30 commits. HTML is fetched at its pretty URL.
diff=() n=0
for f in $(git log -30 --format= --name-only --diff-filter=AM "$main" -- web | grep -v "^web/_" | sort -u | head -20); do
  git cat-file -e "$main:$f" 2>/dev/null || continue
  p=${f#web/}; p=${p%.html}; [ "$p" = index ] && p=; p=${p%/index}
  live=$(curl -fsSL -m 10 "https://aguagdl.com/$p" 2>/dev/null | shasum | cut -c1-40)
  n=$((n+1))
  [ "$live" = "$(git show "$main:$f" | shasum | cut -c1-40)" ] || diff+=("$f")
done
if [ ${#diff[@]} -eq 0 ]; then
  echo "site: matches origin/main on $n recently changed files"
else
  echo "site: ${#diff[@]}/$n recently changed files differ from origin/main: ${diff[*]:0:5}"
fi

echo "local: $(git rev-list --count "$main..HEAD") unpushed commits on $(git branch --show-current)"
exit 0
