#!/usr/bin/env python3
"""Build the static, offline-tolerant zone calendar consumed when the API is unavailable."""
import argparse
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "api" / "data" / "rotation.json"
OUT = ROOT / "web" / "zones.json"
DAYS = {"sun": "domingo", "mon": "lunes", "tue": "martes", "wed": "miércoles", "thu": "jueves", "fri": "viernes", "sat": "sábado"}
NUMBERS = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}


def build():
    raw = json.loads(SOURCE.read_text())
    dt.date.fromisoformat(raw["checked"])
    zones = []
    for number in sorted(raw["zones"], key=int):
        weekdays = raw["zones"][number]
        zones.append({
            "zone": int(number),
            "days": [DAYS[day] for day in weekdays],
            "weekdays": [NUMBERS[day] for day in weekdays],
            "next": [],
        })
    return json.dumps({
        "zones": zones,
        "checked": raw["checked"],
        "source": raw["source"],
        "start": raw["start"],
        "end": raw.get("end", ""),
        "static": True,
    }, ensure_ascii=False, separators=(",", ":")) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = build()
    if args.check:
        if not OUT.exists() or OUT.read_text() != rendered:
            raise SystemExit("web/zones.json is stale: run python3 pipelines/zonas_json.py")
        print("zones.json: up to date")
    else:
        OUT.write_text(rendered)
        print(OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
