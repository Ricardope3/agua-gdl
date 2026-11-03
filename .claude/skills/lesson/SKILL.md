---
name: lesson
description: Turn a correction Ricardo just made into a rule line (or a check) in the repo so the same mistake doesn't come back.
disable-model-invocation: true
---

1. State the lesson in one line: what was wrong and what to do instead.
2. If it's a rejected design, copy or feature, add a dated line to `.claude/rules/vetos.md`.
3. Otherwise add one line to the `.claude/rules/` file for that area (not AGENTS.md unless it applies to every task). Check no existing line already says it; edit that line instead of adding a second.
4. If the rule can be checked mechanically (a word, a field, a page invariant), add the check to the right script (`scripts/lint_copy.py`, `pipelines/publicaciones.py`, `scripts/check_web.mjs`) and run `scripts/check.sh --quick`.
5. Keep each rules file short: if one passes about 40 lines, merge or drop stale lines.
6. Show Ricardo the line(s) added; commit only if he says so.
