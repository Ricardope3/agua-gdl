# AGENTS.md

Instructions for AI coding agents working in this repo. Humans: see README.md (Spanish).

This file says how things are now and stays under 10 KB (the pre-commit hook enforces it). History lives in git. Area detail lives in `.claude/rules/`, which Claude Code loads when you read, write or edit a matching file (not on grep); other agents should open the file named below. Put a new fact in the area file it belongs to, and leave out what the code already says.

## What this is

Agua GDL sends free Telegram reminders before each block of cuts of SIAPA's water rotation in Guadalajara (Oct 2026 – Mar 2027): a notice two days before and a reminder the evening before. It also runs the neighbours' report map (/reportes), collects "how did the water come back" answers and publishes advocacy pages (/exige, /promesas, /contamina…). WhatsApp ran until 15 Oct 2026, when Meta closed the account; its code stays, off without `WA_TOKEN`. It's a civic project: no official affiliation, nonpartisan.

## Read before you touch

| Touching | Read first |
|---|---|
| `api/` (bot, reminders, reports, store), `infra/`, `fly.toml` | `.claude/rules/api.md` |
| `web/` pages, `_headers`, `_redirects`, `mapa.js`, `scripts/` | `.claude/rules/web.md` |
| `publicaciones.json`, `promesas.json`, /noticias, /pipas, /exige, advocacy copy | `.claude/rules/evidence.md`, `docs/EDITORIAL.md` |
| `pipelines/`, `api/data/`, a SIAPA or rotation change | `.claude/rules/pipelines.md` |
| `experiments/` | `.claude/rules/experiments.md` |
| Deploy, production, incidents | `docs/OPERATIONS.md`, `docs/RELEASE.md`, `docs/INCIDENT_RESPONSE.md` |
| Sources and private research | `docs/SOURCES.md`; `research/` (gitignored, local only) |
| Project state, open items, decisions | `~/agua-gdl-notes/STATE.md` (private; update it with `/handoff`) |

Layout: `api/` Go module (Go 1.27, pgx v5) on Fly.io with Neon Postgres; `pipelines/` Python, standard library unless noted; `web/` plain HTML, no framework, deployed by Cloudflare Pages; `experiments/` not deployed.

## Commands

```sh
scripts/check.sh          # vet, unit tests and data/web checks; integration tests skip (seconds)
scripts/check.sh --quick  # skip Go
scripts/check.sh --full   # what CI runs (bar govulncheck and the Docker build): race + integration tests on a throwaway Postgres
npm run dev               # preview web/ at http://localhost:7100 (applies _redirects and _headers)
node scripts/shot.mjs /reportes   # screenshots at 390 and 1300 px; the preview must be running
```

Run `scripts/check.sh` and read its result before you push. Search with a path (`grep -rn foo web/reportes.html`) or `grep -rl` first: `web/` holds large generated JSON and maps.

## Rules

- Never send real WhatsApp or Telegram messages from tests or local runs. `REMINDERS_ENABLED` and `TG_REMINDERS_ENABLED` stay false unless the maintainer turns them on in production.
- Don't relax the safety rails: idempotent sends per (subscriber, cut date), daily and monthly caps, the heartbeat, never resending an attempt that may have been accepted, and the webhook signature check. A duplicate or missed reminder is the worst bug here.
- Privacy: store only the channel user ID, optional WhatsApp phone, zone memberships and consent/update times. BAJA must delete the subscriber; reports stay anonymous and never carry an IP, a location or a subscriber. Never log phone numbers, Telegram IDs, coordinates, colonia searches or WhatsApp message IDs. No secrets in the repo. Never use resident data for political targeting, campaigns, advertising or propaganda.
- Public endpoints serve from memory, and what they read from Postgres refreshes at most every 15–30 minutes (Neon's free hours). Keep the rate limits and `no-store` rules when you add endpoints.
- Evidence: every factual claim links its source; quotes appear as written; never a private person's name; a source's claim is presented as its claim; silence never means the water returned; pages never claim representativeness, causation or laboratory water quality. Never state that an Israeli company is part of the Jalisco aqueduct APP unless a source shows it. A passing `--check` validates shape, not truth.
- Everything in `web/` is public and deploys on push to `main`: keep notes, drafts, unused data and agent docs out of it.
- `web/reportes.html` and `web/index.html` are edited directly. Generated files: `web/promesas.html` (`pipelines/promesas.py`), `web/simple.html` (`simple_page.py`), `web/zones.json` (`zonas_json.py`), `web/videos.json` (`videos.py`), `web/colonias_siapa.topo.json` and its `api/data` copy (`siapa_mapa.py`), `web/calendario/*.ics` (`cmd/calendars`), `api/data/colonias_mapa.json` (`mapa_colonias.py`), the `SECCIONES` string in `web/exige.html` (`secciones_escribe.py`), `web/semana/` and `web/informes.html` (`cmd/informe`), `web/cisternas.json` (`cisternas.py`). Edit the source, then regenerate.
- Migrations: add new numbered files; never edit applied ones. Tests use a fixed `Now`, never the wall clock.
- Keep code comments sparse and match the surrounding style. User-facing copy in plain Mexican Spanish (the bot's in `api/internal/bot/messages.go`).
- Commits: author `soporte@aguagdl.com`, no AI attribution trailer, English messages with a subject of at most 72 characters and the details in the body. `.githooks/` checks the configured email, the trailer and the subject length (`git config core.hooksPath .githooks`); the rest is on you.
- Don't force-push. The maintainer may be editing in parallel: check `git status` before you edit or commit.
- Subagents: `recolector` (Haiku) gathers, `buscador` (Sonnet) finds sources, `verificador` (Opus) judges evidence, `auditor` (Sonnet) reviews changes. Don't spawn general-purpose agents for these jobs. Keep Bash output small by writing long results to a file and printing counts.
- Skills: `/barrido-noticias`, `/post-social`, `/oficio` (drafts only), `/lesson` (turn a correction into a rule), `/handoff`. Read `.claude/rules/vetos.md` before proposing designs or copy.
- For a long or multi-file task while other sessions may be editing, work in a worktree, not in `main`'s checkout. Commit work in progress instead of stashing.
- `scripts/live.sh` says what is live: the API's commit from `/version` and whether the site matches `main`.

## How to change this repo

Lessons from mistakes agents made here; each one shipped once.

- Verify before you state. A claim in docs, copy or a report needs its source in the code, the data or a cited page; say "not verified" otherwise. A source's claim stays its claim (SIAPA says the cuts aren't total; neighbours report early loss and late return).
- When you move or restructure a file, run a lost-lines check: every line of the old file is in a new file or deliberately dropped. List what you dropped.
- When you delete or rename anything, grep for every name and check every generator that writes there, so nothing links to it or writes it back.
- After a multi-file change, run an adversarial review before committing: one read-only reviewer per area, briefed to assume mistakes exist. Fix what it finds, then commit.
- Fix the claim, not the list. A review names files; the claim also lives in generators, bot copy, `.ics`, data, `llms.txt` and `~/agua-gdl/research/` (absent in worktrees). Grep every form of it everywhere and add a `KNOWN_ERRORS` entry in the same commit. Fact-check #5 was fixed on the pages it named and stayed on the landing's h1, the Telegram reminder, every calendar and 2,238 colonia pages.
- When a source changes, sweep its copies. SIAPA's 3 Nov days left «de 2 a 3 racionamientos» on four pages and «lunes y viernes» in a printed handout; the 28 Oct federal announcement left six pages arguing the old APP figures. Grep for the old days, counts and amounts in `web/`, `api/`, `.claude/` and `~/agua-gdl/research/`, and have handouts read `web/zones.json`, never literal days.
- Compute dates and times; don't reason them out. Then assert them against the other surface that promises the same moment: a 1 Nov "fix" made the calendar's «En dos días» alarm fire three days early, and its test pinned the wrong value. Dates are Guadalajara's day, not UTC's.
- A sweep that must reach `research/` or other gitignored files uses `command grep -r`: in Claude Code's shell `grep` is ugrep with `--ignore-files`, so `grep -r … ~/agua-gdl` silently skips them (5 Nov). Plain `grep` on a tracked path is fine.
- Quote a scanned document from its page image, not its OCR, accents and capitals included. `refs.py check` matches a quote against the archived text of any cited source, OCR included, so an OCR error copied into a quote passes; it also ignores capitals: R3's «si pueda» (image: «sí»), copied from the OCR in the 4 Nov rewrite, passed it.
- Get counts, rows and line or page pins from code, and read the output uncut: on 5 Nov a truncated dump nearly reported 12 samples where the file has 13, and four guessed pins in one ledger were wrong (listed in its README).
- Start Agua GDL sessions in `~/agua-gdl`: `recolector`, `buscador`, `verificador` and `auditor` load only then. Outside it, put the agent file's rules into the prompt.
- No overstatement. Every factual claim you write or tell Ricardo was checked against its source in this session, or says «not checked». A subagent's report, a summary or a status file is a lead, not a fact; when Ricardo asks «is that accurate?», re-check the source instead of defending the claim (5 Nov: a reviewer's date was relayed unchecked).
- Legal work runs at high reasoning effort or above: transparency requests and appeals, amparos, legal options and anything citing a law. Pass that effort to every subagent doing it.
- Don't trust git config: check the author of every commit you make (`git log -1 --format=%ae`).
- End each task by stating what's committed, what's pushed, what's live (the API needs a Fly deploy; the site deploys on push) and what isn't verified.
