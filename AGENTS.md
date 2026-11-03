# AGENTS.md

Instructions for AI coding agents working in this repo. Humans: see README.md (Spanish).

This file says how things are now and stays under 10 KB (the pre-commit hook enforces it). History lives in git. Area detail lives in `.claude/rules/`, which Claude Code loads when you read or edit a matching file; other agents should open the file named below. Put a new fact in the area file it belongs to, and leave out what the code already says.

## What this is

Agua GDL sends free Telegram reminders before each block of cuts of SIAPA's water rotation in Guadalajara (Oct 2026 – Mar 2027): a notice two days before and a reminder the evening before. It also runs the neighbours' report map (/reportes), collects "how did the water come back" answers and publishes advocacy pages (/exige, /promesas, /contamina…). WhatsApp ran until 15 Oct 2026, when Meta closed the account; its code stays, off without `WA_TOKEN`. It's a civic project: no official affiliation, nonpartisan.

## Read before you touch

| Touching | Read first |
|---|---|
| `api/` (bot, reminders, reports, store), `infra/`, `fly.toml` | `.claude/rules/api.md` |
| `web/` pages, `_headers`, `_redirects`, `mapa.js`, `scripts/` | `.claude/rules/web.md` |
| `publicaciones.json`, `promesas.json`, /noticias, /pipas, /exige, advocacy copy | `.claude/rules/evidence.md`, `docs/EDITORIAL.md` |
| `pipelines/`, `api/data/`, a SIAPA or rotation change | `.claude/rules/pipelines.md` |
| `experiments/`, /c6…/c8 | `.claude/rules/experiments.md` |
| Deploy, production, incidents | `docs/OPERATIONS.md`, `docs/RELEASE.md`, `docs/INCIDENT_RESPONSE.md` |
| Sources and private research | `docs/SOURCES.md`; `research/` (gitignored, local only) |
| Project state, open items, decisions | `~/agua-gdl-notes/STATE.md` (private; update it with `/handoff`) |

Layout: `api/` Go module (Go 1.27, pgx v5) on Fly.io with Neon Postgres; `pipelines/` Python, standard library unless noted; `web/` plain HTML, no framework, deployed by Cloudflare Pages; `experiments/` not deployed.

## Commands

```sh
scripts/check.sh          # everything CI checks except govulncheck and the Docker build (seconds)
scripts/check.sh --quick  # skip Go
scripts/check.sh --full   # with a throwaway Postgres for the integration tests
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
- `web/reportes.html` and `web/index.html` are edited directly. Generated files: `web/promesas.html` (`pipelines/promesas.py`), `web/simple.html` (`simple_page.py`), `web/zones.json` (`zonas_json.py`), `web/videos.json` (`videos.py`), `web/colonias_siapa.topo.json` and its `api/data` copy (`siapa_mapa.py`), `web/calendario/*.ics` (`cmd/calendars`), `web/c6…c8.html` (`experiments/reportes/videos.py`). Edit the source, then regenerate.
- Migrations: add new numbered files; never edit applied ones. Tests use a fixed `Now`, never the wall clock.
- Keep code comments sparse and match the surrounding style. User-facing copy in plain Mexican Spanish (the bot's in `api/internal/bot/messages.go`).
- Commits: author `soporte@aguagdl.com`, no AI attribution trailer, English messages with a subject of at most 72 characters and the details in the body. `.githooks/` enforces this (`git config core.hooksPath .githooks`).
- Don't force-push. The maintainer may be editing in parallel: check `git status` before you edit or commit.
- For evidence work, use the `verificador` (checks) and `buscador` (finds) subagents in `.claude/agents/`; keep Bash output small by writing long results to a file and printing counts.
