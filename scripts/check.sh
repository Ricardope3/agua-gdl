#!/usr/bin/env bash
# Runs the checks CI runs. Usage: scripts/check.sh [--quick | --full]
#   --quick  skip Go
#   --full   go test -race with integration tests, against TEST_DATABASE_URL or a throwaway Postgres,
#            and scripts/smoke.sh (headless Chrome; SKIPs when Chrome is missing)
set -euo pipefail

mode=default
case "${1:-}" in
  "") ;;
  --quick) mode=quick ;;
  --full) mode=full ;;
  *) echo "usage: $0 [--quick|--full]" >&2; exit 2 ;;
esac

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
tmp="$(mktemp -d)"
cleanup() {
  if [[ -n "${pgdata:-}" ]]; then pg_ctl -D "$pgdata" -m immediate stop >/dev/null 2>&1 || true; fi
  if [[ -n "${pgcontainer:-}" ]]; then docker rm -f "$pgcontainer" >/dev/null 2>&1 || true; fi
  rm -rf "$tmp"
}
trap cleanup EXIT

failed=()
passed=0
start=$SECONDS
step() {
  local name="$1"; shift
  local t=$SECONDS
  if "$@" >"$tmp/out" 2>&1; then
    passed=$((passed + 1))
    printf 'PASS  %-34s %3ss%s\n' "$name" $((SECONDS - t)) "${note:+  ($note)}"
  else
    failed+=("$name")
    printf 'FAIL  %-34s %3ss%s\n' "$name" $((SECONDS - t)) "${note:+  ($note)}"
    tail -n 300 "$tmp/out" | sed 's/^/      /'
  fi
  note=
}
note=

gotest() {
  (cd api && go test -v "$@" ./...) >"$tmp/go" 2>&1 && rc=0 || rc=$?
  local skips; skips=$(grep -c -- '--- SKIP' "$tmp/go" || true)
  note="$skips skipped"
  [[ -z "${TEST_DATABASE_URL:-}" ]] && note="$skips skipped: TEST_DATABASE_URL unset, integration tests did not run; use --full"
  if ((rc)); then
    # Everything but the passing-test chatter, so race reports and panics reach the CI log.
    grep -vE -- '^(=== (RUN|PAUSE|CONT|NAME)|[[:space:]]*--- (PASS|SKIP)|PASS$|ok[[:space:]])' "$tmp/go" | head -n 300 || true
  fi
  return $rc
}

startpg() {
  local port=$((20000 + RANDOM % 20000))
  if command -v initdb >/dev/null && command -v pg_ctl >/dev/null; then
    pgdata="$tmp/pg"
    initdb -D "$pgdata" -U aguagdl_test --auth=trust >/dev/null &&
      pg_ctl -D "$pgdata" -w -l "$tmp/pg.log" -o "-p $port -c unix_socket_directories='' -c listen_addresses=localhost -c fsync=off" start >/dev/null &&
      createdb -h localhost -p "$port" -U aguagdl_test aguagdl_test || { cat "$tmp/pg.log" 2>/dev/null; return 1; }
  elif command -v docker >/dev/null; then
    pgcontainer="aguagdl-check-$$"
    docker run -d --rm --name "$pgcontainer" -e POSTGRES_USER=aguagdl_test -e POSTGRES_PASSWORD=test \
      -e POSTGRES_DB=aguagdl_test -p "127.0.0.1:$port:5432" postgres:17-alpine >/dev/null
    for _ in $(seq 60); do docker exec "$pgcontainer" pg_isready -U aguagdl_test -h 127.0.0.1 >/dev/null 2>&1 && break; sleep 0.5; done
    docker exec "$pgcontainer" pg_isready -U aguagdl_test -h 127.0.0.1 >/dev/null
  else
    echo "--full needs initdb/pg_ctl or docker"; return 1
  fi
  export TEST_DATABASE_URL="postgres://aguagdl_test:test@localhost:$port/aguagdl_test?sslmode=disable"
}

if [[ $mode != quick ]]; then
  step "go vet" bash -c 'cd api && go vet ./...'
  if [[ $mode == full ]]; then
    if [[ -z "${TEST_DATABASE_URL:-}" ]]; then step "postgres (throwaway)" startpg; fi
    if [[ -n "${TEST_DATABASE_URL:-}" ]]; then step "go test -race (integration)" gotest -race; fi
  else
    step "go test" gotest
  fi
fi
step "status_test.mjs" node --test experiments/reportes/status_test.mjs
step "python unittest" python3 -m unittest discover -s pipelines -p 'test_*.py'
for p in mapa_colonias promesas publicaciones zonas_json simple_page videos colonia_pages; do
  step "$p.py --check" python3 "pipelines/$p.py" --check
done
step "check_web.mjs" node scripts/check_web.mjs
step "lint_copy.py" python3 scripts/lint_copy.py
step "check_docs.py" python3 scripts/check_docs.py
if [[ $mode == full ]]; then
  if bash scripts/smoke.sh >"$tmp/smoke" 2>&1 || grep -q "^SKIP" "$tmp/smoke"; then
    grep "^SKIP" "$tmp/smoke" || step "smoke.sh (headless Chrome)" true
  else
    step "smoke.sh (headless Chrome)" bash -c 'grep -v "^[^[:space:]]*\.png$" "$1"; exit 1' _ "$tmp/smoke"
  fi
fi

echo "----"
if ((${#failed[@]})); then
  echo "FAIL: ${#failed[@]} failed (${failed[*]}), $passed passed in $((SECONDS - start))s"
  exit 1
fi
echo "PASS: all $passed checks in $((SECONDS - start))s ($mode)"
