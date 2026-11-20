#!/bin/sh
# Regenerate everything derived from api/data/rotation.json after SIAPA changes the
# days, in dependency order, then print the human-only steps that must follow.
# Run from anywhere; no network. For the sources baseline run, separately:
#   python3 pipelines/siapa_watch.py --update
set -e
cd "$(dirname "$0")/.."

(cd api && go run ./cmd/calendars)
python3 pipelines/zonas_json.py
python3 pipelines/simple_page.py
python3 pipelines/colonia_pages.py
python3 pipelines/sitemap.py

cat <<'EOF'
Regenerated. Human-only steps that can't be scripted:
  1. Review the change against SIAPA's official calendar and commit
     api/data/rotation.json on its own, apart from the regeneration churn.
  2. If the sources changed too: python3 pipelines/siapa_watch.py --update
     and commit pipelines/siapa_sources.json.
  3. Notify each zone whose days changed (dry run first, then -send):
     cd api && DATABASE_URL='…' go run ./cmd/notify -zone N -from YYYY-MM-DD
  4. Grep web/, .claude/ and research/ for the old day strings and update
     the copy, calendars and handouts that repeat them.
  5. Deploy the API (fly deploy) and check /version; the site deploys on push.
EOF
