#!/usr/bin/env python3
"""One line per Claude Code session transcript: turns, tool calls, tokens, est. cost.

Usage: scripts/cost.py [DIR] [-n N]   (default: this repo's transcripts, newest 10)
Prices: Claude Opus 5.5 list, $/MTok (claude-api reference, cached 2026-10-06);
cache write assumes the 5-minute TTL at 1.25x input.
"""
import argparse, glob, json, os

PRICE = {"input": 4.00, "output": 20.00, "cache_read": 0.20, "cache_write": 5.00}
DEFAULT = os.path.expanduser("~/.claude/projects/-Users-ricardoespinoza-agua-gdl")


def session(path):
    seen, date = {}, ""
    tools = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not date and row.get("timestamp"):
                date = row["timestamp"][:10]
            msg = row.get("message") if row.get("type") == "assistant" else None
            if not isinstance(msg, dict):
                continue
            for b in msg.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    tools += 1
            mid = msg.get("id") or row.get("uuid")
            # A message streamed over several lines repeats its usage; keep the last copy.
            seen[mid] = msg.get("usage") or {}
    tot = {k: 0 for k in ("input", "output", "cache_read", "cache_write")}
    for u in seen.values():
        tot["input"] += u.get("input_tokens", 0) or 0
        tot["output"] += u.get("output_tokens", 0) or 0
        tot["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
        tot["cache_write"] += u.get("cache_creation_input_tokens", 0) or 0
    cost = sum(tot[k] * PRICE[k] for k in tot) / 1e6
    return date, len(seen), tools, tot, cost


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", nargs="?", default=DEFAULT)
    ap.add_argument("-n", type=int, default=10)
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.dir, "*.jsonl")), key=os.path.getmtime, reverse=True)[: a.n]
    print(f"{'date':10} {'session':8} {'turns':>5} {'tools':>5} {'cache_rd':>11} {'cache_wr':>10} {'output':>9} {'est.$':>8}")
    for p in files:
        d, turns, tools, t, c = session(p)
        sid = os.path.basename(p)[:8]
        print(f"{d:10} {sid:8} {turns:5} {tools:5} {t['cache_read']:11,} {t['cache_write']:10,} {t['output']:9,} {c:8.2f}")


if __name__ == "__main__":
    main()
