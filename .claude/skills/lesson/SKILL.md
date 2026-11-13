---
name: lesson
description: Turn a correction Ricardo just made into a rule line (or a check) in the repo so the same mistake doesn't come back.
disable-model-invocation: true
---

1. State the lesson in one line: what was wrong and what to do instead.
2. If it's a rejected design, copy or feature, add a dated line to `.claude/rules/vetos.md`.
3. Otherwise add one line to the `.claude/rules/` file for that area (not AGENTS.md unless it applies to every task). Check no existing line already says it; edit that line instead of adding a second.
4. If the rule can be checked mechanically (a word, a field, a page invariant), add the check to the right script (`scripts/lint_copy.py`, `pipelines/publicaciones.py`, `scripts/check_web.mjs`) and run `scripts/check.sh --quick`.
5. Write the line as how things are now, with the reason: no «was removed», «used to be» or the story of the change. A file named as gone or in git history gets its full path. `scripts/check_docs.py` fails on those two wordings and on a bare file name beside «git history» that a tracked file shares; the rest is on you.
6. Show Ricardo the line(s) added; commit only if he says so.
