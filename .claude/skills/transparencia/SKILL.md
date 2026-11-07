---
name: transparencia
description: Agua GDL's PNT transparency work. Use it to draft or rewrite a request, decide on or draft an appeal (a «Queja» on the folio), process a «Mis solicitudes» export, a «Seguimiento» screenshot or an acuse Ricardo sends, read answers that arrived, or say what is due. Use it whenever the conversation mentions a folio, a solicitud, a recurso de revisión, a queja, the PNT, the sender page, or ids like F28, P1, R5, even if Ricardo doesn't name the skill. Drafts only: Ricardo files.
---

# Transparencia

Arguments: the job, such as a request id (F33, P2), «appeal <folio>», an export, screenshot or answer just sent, or «what's due».

The process lives in `research/transparency/` (gitignored, so it exists only in the main checkout, not in worktrees). This skill gives the order of the steps and says which file governs each one. Read those files; don't work from memory or from this page. A filing that goes out wrong costs weeks and can't be taken back, so every step favours checking over speed.

## Start

1. **Effort.** Requests, appeals and legal analysis run at high reasoning effort or above, and so does every subagent you start for them (pass `effort: "high"`). If Ricardo has said the session runs lower, tell him before you draft. If you can't tell, don't guess.
2. **Read** `AGENT-CONTEXT.md`: «Where things stand», «Rules», «Facts settled against primary sources» and «Open findings», plus the row of «Where things are» that you need. Don't load `combined/`, `evidence/sources.json` or the source memos whole.
3. **Status comes from the log.** Take each folio's status from section D of `subsequent-requests.md` and the newest `mis_solicitudes-*.xls`, never from AGENT-CONTEXT, a README or STATE.md. PNT fields (acuse addressee, «fecha en que se notificó», due dates) are claims to check.
4. **Deadlines.** Run `python3 ~/agua-gdl-notes/scripts/plazos.py`. Compute every date in Python. Write the legal date beside the PNT date, because the PNT counts rest days as working days (AGENT-CONTEXT rule 15). For entries with a fixed `due`, plazos.py prints the PNT date in its «legal» column, so compute the legal date yourself.
5. **Someone may be editing.** Run `git -C ~/agua-gdl/research status --porcelain` and check the file's modification time right before you write to it.

**Every claim names its source.** This covers drafts, decisions, deadlines and your messages to Ricardo, not only filed texts. Give each fact the file and line, page or cell it came from, read this session; otherwise mark it «not checked». «From the 4 Nov review» is not a source. A subagent's report, a memo's «verified» or a status file is a lead until you read the source yourself.

## Pick the job

| Ricardo brings | Section that governs it |
|---|---|
| A new request, or a rewrite of an unfiled one | DRAFTING-GUIDE: «Before drafting» through «Keep out of the text», then «Drafting» below |
| A bad answer, or «should we appeal?» | DRAFTING-GUIDE «Appeals», and the «Decisión por folio» table in `recursos-de-revision-2026-11-02.md` (editing it changes its hash: re-check its claims and update the `<!-- ledger DECISIONES … -->` pin in the ledger); then «Drafting» below |
| A «Seguimiento» screenshot | «Lock anything that needs Ricardo»: write the date into the text, the Registro and the folio's `plazos.json` `start`, replacing the assumed oficio date; rebuild, and the card unlocks by itself |
| A «Mis solicitudes» export | «Updating the page from his export». Every folio «En proceso» needs an open `plazos.json` entry with a `due` and the folio in `what`; `check_export.py` fails without one |
| An acuse after he filed | «After he files a queja» |
| Answers that arrived | DRAFTING-GUIDE «After an answer arrives», and «Answers» below |
| «What's due?» | `plazos.py` and section D; give legal and PNT dates |

## Answers

Follow DRAFTING-GUIDE «After an answer arrives» for each folio. The points that are easy to miss:

- **Overlap groups first.** Answers that cover the same records are read together (`verification-2026-11-03/09-answer-readiness.md`). An answer that sends us to another of our own folios is not delivery.
- **Downloads.** Ask Ricardo once per batch, listing each folio's files and sizes. His OK covers that list. If he prefers, he sends the files himself.
- **Score every item asked** as delivered, partial or none, with the page that shows it, and say whether the request was properly addressed. The narrative's count is redone from properly addressed requests only.
- **Deadlines the same day.** Mark the answer entry `answered`. Open the appeal entry with the folio in `what`, starting at the oficio date marked as assumed; replace that date when the «Seguimiento» screenshot arrives. A referral (art. 81.3) gets its own window, counted from the referral.
- **When an answer changes a conclusion**, update the narrative assessment, `public-claims-vs-responses.md` and `official-contradictions.md`. Then take each folio through «Appeals» and record the decision in the «Decisión por folio» table.

## Drafting (requests and appeals)

1. **Don't research or file twice.** Run `python3 evidence/refs.py find "<term>"`, read AGENT-CONTEXT «Already investigated» and the topic's `verification-*/README.md`, and check section D for a pending request on the same records. Rewriting an unfiled draft, or relying on a pending follow-up, beats adding a new request. A new request has to name what it settles that nothing pending does. Check whether an appeal would beat a new request, since a new request doesn't keep an appeal's deadline.
2. **Read every source yourself.** For a scanned document, compare quotes with the page image, not the OCR. Get line, page and cell pins from code (`grep -n`, a parse), never by estimating them.
3. **Ledger.** Give every claim a row in `verification-<date>-<topic>/sources-for-every-claim.md` with the source, its pin, how you read it and the verdict, pinned to the text by its hash. `validate_three_drafts.py` fails a text without one.
4. **Write the text** into its home file: F in `subsequent-requests.md`, P in `drafts-three-priority-requests-2026-11-01.md`, R in `recursos-de-revision-2026-11-02.md`. `validate_three_drafts.py` fails a text over 3,900 characters (the PNT box takes 4,000); report the count.
5. **Three single-lens reviews, in parallel:** read-only `verificador` agents at high effort, briefed from section D, each given the text and the ledger and told to assume mistakes exist. The lenses are (a) facts and quotes, letter for letter; (b) law and procedure, meaning grounds, custodian, `pnt-subjects.md` and dates; (c) the official trying to dodge (DRAFTING-GUIDE «Final test», 1–7). `verificador` doesn't load CLAUDE.md and is briefed for evidence, so the law lens's brief has to include DRAFTING-GUIDE «Legal traps» and the relevant rows of `legal-options.md`. Check every finding against its source before you apply it.
6. **Answer Final test 8–13 yourself.**
7. **Put it into the system** following DRAFTING-GUIDE «Writing it into the system»: the authority, the plan row, section D, sources and checks. Then run `./check.sh`, rebuild the sender page, open it in Chrome to see the cards render, and publish that same local file to the sender artifact named in AGENT-CONTEXT. The local copy and the artifact must always match.
8. **Record the round** in the topic's `verification-*/README.md` (method, what each lens found, what changed), so nobody repeats it. A mistake you made goes in `lessons-learned.md`. If a check can catch it, add the check to `validate_three_drafts.py` or `lint_context.py`, tested on a planted copy of the mistake. Not `/lesson`, which writes to the public repo.

## Commits

- **`~/agua-gdl/research`** (private): commit once `check.sh` passes (the pre-commit hook runs it when `transparency/` files are staged). Stage only your own files. Author soporte@aguagdl.com, no AI trailer, an English subject of at most 72 characters. Push only when Ricardo says so.
- **`~/agua-gdl-notes`** (STATE.md, `plazos.json`, the log): commit and push after editing, as STATE.md's rules say.
- **`~/agua-gdl`** (public): only the skills and rules live there, and the evals stay out of it. Commit only when Ricardo says so, and never run `git add .`.

## Never

- File, submit or fill a PNT form, or open a composer. Ricardo files.
- Download without the per-batch OK above.
- Raise a source's `read` status without doing the reading.
- Adopt an official's framing or an accusing tone. Write «X said», not «X did», until a record backs it.
- Unlock a card that waits on Ricardo's judgment, or keep locked one whose input he has already sent.

## Report to Ricardo

Keep it short, in this order:
- what was drafted or changed, with ids and character counts;
- what each review found and what changed because of it;
- what he has to do, as steps on the PNT in Spanish;
- deadlines, with the legal and the PNT date;
- what a lawyer should confirm before he relies on it, such as which law governs, the garante, rest days or a ground's provision;
- what is committed and pushed, in each repo;
- every claim you didn't check this session, marked «not checked».
