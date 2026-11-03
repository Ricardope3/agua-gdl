---
name: post-social
description: Draft social media posts (X, Facebook, Instagram, Telegram) about the water crisis from Agua GDL's own data, with sources. Drafts only; Ricardo posts.
disable-model-invocation: true
---

Arguments: the topic or event, and the platforms.

1. Take facts only from the repo's data (`publicaciones.json` via `publicaciones.py q`, `promesas.json`, `api/data/rotation.json`, `/v1/reportes`) and `~/agua-gdl-notes/STATE.md`. No fact without a link to its source; quotes as written; never a private person's name; a source's claim stays its claim; silence never means the water returned.
2. Read `.claude/rules/vetos.md` and `docs/GLOSARIO.md` first.
3. One draft per platform, within its length, in plain Mexican Spanish, ending with the relevant aguagdl.com link (/reportes, /exige, /avisos or a /colonia page).
4. Under each draft, list every source used.
5. Never post, schedule or open a composer: return the drafts.
