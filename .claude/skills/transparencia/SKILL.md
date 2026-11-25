---
name: transparencia
description: Agua GDL's PNT transparency work. Use it to draft or rewrite a request, decide on or draft an appeal (a «Queja» on the folio), process a «Mis solicitudes» export, a «Seguimiento» screenshot or an acuse Ricardo sends, read answers that arrived, say what the answers so far show, or say what is due. Use it whenever the conversation mentions a folio, a solicitud, a recurso de revisión, a queja, the PNT, the sender page, or ids like F28, P1, R5, even if Ricardo doesn't name the skill. Drafts only: Ricardo files.
---

# Transparencia

Arguments: the job, such as a request id (F33, P2), «appeal <folio>», an export, screenshot or answer just sent, or «what's due».

The process lives in `~/agua-gdl/research/transparency/` (private and gitignored, so only in the main checkout, not in worktrees). This page gives the order of the steps and the file that governs each:

- `WORKING-RULES.md` holds every rule of every step, by section (§1.4, §8.6…), most with the incident or lessons-learned section behind it. Read the section a step names when you reach that step, in this session: not from memory, and not from this page.
- `DRAFTING-GUIDE.md` governs how a text is written, appealed and followed up; `AGENT-CONTEXT.md` holds the state and the settled facts; `lessons-learned.md` is the history (don't load it whole).

This repo is public: case names, folios, strategy and dated incidents go in those files, never here. A filing that goes out wrong costs weeks and can't be taken back, so checking comes before speed. The one exception is a prudent fifteenth day within the next two business days: WORKING-RULES §0.

## The mistakes that keep coming back

These are the kinds of slip that come back again and again in `lessons-learned.md`'s section titles. Each has a check. Run it, and read its output whole: saved to a file and read in full, never through `head`, `tail` or `grep -v`, and opened when Claude Code shows only a preview (§3).

1. **A claim not read this session.** A subagent's report, a summary, a status file, a README, your memory after a context reset and your own earlier message are all leads. Every fact in a text, a note, a register row or a message to Ricardo names the file and line, page, cell or URL you read it from in this session; otherwise it says «not checked». Counts come from a saved script, and pins from code. Checks: `check_claims.py`, `check_register.py`, `check_time_labels.py`. §3, §4.
2. **A law cite from anything but the law.** Read the article in the law file this session, quote the fracción whole (or mark the cut with «…») and pin its line. A guide, a memo or an agent's report only tells you which article to read. Check: `check_cites.py`. §2.
3. **A date reasoned out.** Every date comes from code (`plazos.py` with `plazos.py --check`, `plazos.py --if-filed`), with the legal and the PNT date, the day it counts from and that day's source. §1.4, §7.12, §11.
4. **An absence nobody proved.** «Missing», «not on disk», «not online», «none», «only» and «no newer» each name the search that shows it: its terms, what it read and its window. Open the page image before you call a scanned column, attachment or act absent. Check: `check_register.py`. §3, §7.7, §7.8.
5. **«Ready» before a lens read the final text.** A text is ready only with a reviewed marker on its current text, after three single-lens reviews whose fixes were ticked off by code. Checks: `check.sh`, `check_records.py`. §8.6, §10, §11.
6. **Another session's lines.** Several sessions edit the same files. Right before each write, check `git status` and the file's modification time; ask the session that may still hold a job or a file and wait for its reply; take a new F or R number only after telling the others; commit by path. §1.5, §9.
7. **A shell slip.** Absolute paths and `git -C`, never `cd`; `set -u`; gate each step on the status of the step it needs; zsh's rules. §1.6.
8. **An official's word taken as fact.** What a body, an official or an oficio says is a claim to test against the documents, never a finding. §5.

When you make a new kind of mistake, see «Keeping this page short» below.

## Start

1. **Effort.** Requests, appeals and legal analysis run at high reasoning effort or above, and so does every subagent you start for them (`effort: "high"`). §1.1.
2. **Read** `AGENT-CONTEXT.md`'s «Where things stand», «Rules», «Facts settled against primary sources», «Open findings» and the row of «Where things are» you need. §1.2.
3. **Status** comes from section D of `subsequent-requests.md` and the newest `mis_solicitudes-*.xls`, never from a README, AGENT-CONTEXT or STATE.md. §1.3.
4. **Deadlines.** Run `python3 ~/agua-gdl-notes/scripts/plazos.py` and `plazos.py --check` and read both. §1.4.
5. **Other sessions.** List them (`ListAgents`), ask any that may hold the job or the file, and wait for the reply before you write. §1.5.

## Pick the job

| Ricardo brings | Governing section |
|---|---|
| A new request, or a rewrite of an unfiled one | DRAFTING-GUIDE «Before drafting» through «Keep out of the text»; «Requests and appeals» below; §6.1 |
| A lead (a post, a news item, a company) about who holds water, discharges or emits, or «shall we investigate this?» | DRAFTING-GUIDE «Before drafting» 10 and «Public registers: REPDA and RETC»: say first what it could give Agua GDL, look it up in the public registers and ask only for what they lack; §6.2 |
| A bad answer, or «should we appeal?» | DRAFTING-GUIDE «Appeals»; the «Decisión por folio» table; §6.3 |
| A «Seguimiento» screenshot | §6.4: the date goes everywhere the old day 15 stood, in one commit |
| A «Mis solicitudes» export | §6.5 and `check_export.py` |
| A due date passed with no answer | DRAFTING-GUIDE «When no answer arrives»; §6.6 |
| A request's acuse after he filed | DRAFTING-GUIDE «After he files a request»; `record_request.py --dry-run` first; §6.7 |
| A queja's acuse after he filed | `record_acuse.py`; §6.8 |
| Anything from the garante, or a queja to follow | DRAFTING-GUIDE «After a queja is filed»; §6.9 |
| Answers that arrived | DRAFTING-GUIDE «After an answer arrives»; «Answers» below; §6.10, §7 |
| An answer that uses a lawful dodge, or a clean inexistence ruling | DRAFTING-GUIDE «Routes a well-advised official would use next», «When they prove inexistence properly», «Other moves in an answer»; §6.11 |
| Anyone contacting Ricardo about a request | DRAFTING-GUIDE «Pressure on the requester»: save it, log it, don't reply in substance; §6.12 |
| «What's due?» | `plazos.py` and section D, legal and PNT dates; any appeal held back whose prudent day 15 is within two business days goes to Ricardo as «decide today»; §6.13, §8.8d |
| «Any gap in the narrative?» | §6.14 |
| «What do the answers show?» | `score_answers.py`, `--bodies`, `--moves`; §6.15 |

## Requests and appeals

1. **Don't research or file twice.** `refs.py find`, «Already investigated», section D and the unfiled drafts; an appeal may beat a new request. §8.1.
2. **Read the addressee's record.** Run `python3 score_answers.py --body "<addressee>"`. For each move it has used, name in the round's README the row of DRAFTING-GUIDE «Close their exits» or «Routes a well-advised official would use next» that the draft meets, and the clause that meets it. DRAFTING-GUIDE «Read the addressee's record».
3. **Read every source yourself**, scans on the page image. §8.2.
4. **Ledger as you draft.** A sentence with no source to put in its row comes out of the text. §8.3.
5. **Name the type and its content** in every item. §8.4.
6. **Write the text** into its home file and measure it with `measure_cards.py`, never with a counter of your own. §8.5.
7. **Your own two reads first** (the text against every appeal that shares a document or a garante, and against the law and our memos), so the lens briefs carry what you found; **then three single-lens reviews in parallel** (facts, law, dodge), read-only `verificador` agents at high effort on frozen copies, their reports saved with `save_lens_report.py`. §8.6.
8. **Answer Final test 8–13 yourself**, and for an appeal the case-theory questions; practice points are in DRAFTING-GUIDE «Before day 15». §8.7, §8.10.
9. **Put it into the system**: register, plan, section D, checks, the sender page and its artifact, the evidence zip (PDF only, 20 MB); before a filing sitting, the list of cards for Ricardo; before any text reaches him, the read a Jalisco transparency lawyer would give it. §7.14, §8.8, §8.8a–d.
10. **Record the round** in its README as it goes, and each slip of yours in `lessons-learned.md`. §8.9.

## Answers

Follow DRAFTING-GUIDE «After an answer arrives» for each folio, and read all of §7. Read answers that cover the same records together (§7.1); quote both the label an answer denies and the activity it describes (§7.2). Read every page of every file, images included, and set the resolution against itself and against the request (§7.5, §7.6). Open every link it cites (§7.3). Ask Ricardo before any download, once per batch, with files and sizes (§7.4). Score every item asked before any appeal decision, an inexistence with no Comité ruling as `none` and each lawful move as «X answered with Y» (§7.9–7.11). Open the deadline entries the same day (§7.12, §7.13). Before you write a register entry, run the lookup and read the gap notes (§7.14). When an answer changes a conclusion, update the narrative files and «Decisión por folio» (§7.16). Carry what the batch teaches into the guide and the unfiled drafts that day (§7.17).

## Subagents

Every agent writes its claims to a ledger CSV and runs `check_claims.py` before it reports. You run the checks again and read the meaning of every row that reaches a text or Ricardo. Tell it to download nothing, and give it its own scratch folder. §4.

## Commits

- `~/agua-gdl/research` (private): by path, once `check.sh` passes; push when Ricardo says so. §9.1.
- `~/agua-gdl-notes`: commit and push after editing. §9.2.
- `~/agua-gdl` (public): only when Ricardo says so, by path, never `git add .`. §9.3.

## Never

- File, submit or fill a PNT form, or open a composer. Ricardo files.
- Download without the per-batch OK above.
- Raise a source's `read` status without doing the reading.
- Adopt an official's framing or an accusing tone. Write «X said», not «X did», until a record backs it.
- Call a text ready that `check.sh` lists as not reviewed on its current text.
- Put notes in a table cell that code parses (Registro dates, section D's status, the plan table): the builder fails or misreads it. Notes go in the last column.
- Unlock a card that waits on Ricardo's judgment, or keep locked one whose input he has already sent. Never lock the input he needs to unlock it (the folio he searches for its «Seguimiento»).
- Let a court filing of Ricardo's go ahead without first reading DRAFTING-GUIDE «Legal traps» with him.

## Report to Ricardo

Read §11 before you write the report. In short:

- **Corrections first:** quote what you told him that was wrong, from the transcript, and the line that corrects it.
- **Audit yourself first:** list the steps you skipped, the findings you relayed unread, the alternatives you didn't test and the calls you made alone, each with whether it could change the text or the decision.
- Then, briefly: what was drafted or changed (ids, character counts); what each review found and what changed; his steps on the PNT, in Spanish; each term of ours in plain words the first time; deadlines with the legal and the PNT date; new lawyer questions, added to `legal-options.md`; what is committed and pushed in each repo; every claim not checked this session, marked «not checked».

## Keeping this page short

This page grew from 9 KB to 66 KB in under three weeks, about one rule per incident, and rules already on it were still being broken: past a certain length, a rule here is one more line nobody reads. A new lesson goes, in this order:

1. into a check that fails on a planted copy of the mistake, named in the step it guards;
2. if no check can hold it, into WORKING-RULES (or DRAFTING-GUIDE, if it is about drafting), in the section of the step it governs, with its lessons-learned reference;
3. never into this page, which changes only when a step, its order or its governing file changes. The pre-commit hook fails this file over 16 KB.
