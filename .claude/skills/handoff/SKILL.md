---
name: handoff
description: Update the private Agua GDL handoff (~/agua-gdl-notes/STATE.md) at the end of a session.
disable-model-invocation: true
---

Update `~/agua-gdl-notes/STATE.md` so the next session can resume.

1. `git -C ~/agua-gdl-notes status --porcelain`; stop and ask if STATE.md has someone else's uncommitted edits.
2. Edit STATE.md in place: Now, Open, Upcoming dates, Rules. Drop items that are done. Set the "as of" line to `git -C ~/agua-gdl rev-parse --short HEAD`. Don't restate what `git log` or the code already says.
3. What happened this session goes in `log/<yyyy>-<mm>.md` (append, dated), never in STATE.md.
4. STATE.md stays under 6 KB; the notes repo's pre-commit hook rejects more. Over that, move detail to `topics/` or the log.
5. Commit in the notes repo as soporte@aguagdl.com, without any AI attribution trailer. Render or republish the handoff artifact only if Ricardo asks.
