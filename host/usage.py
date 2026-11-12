"""Per-run Claude usage ledger (data/usage.jsonl), appended when a run finishes.
The runner only keeps runs in memory, so this is what survives restarts."""
import json
import os
import time

DATA_DIR = os.environ.get("DASH_DATA", "/app/data")
FIELDS = ("cost_usd", "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "turns")


def _file():
    return os.path.join(DATA_DIR, "usage.jsonl")


def record(loop, run_id, run):
    st = run.get("stats") or {}
    row = {"ts": time.time(), "run_id": run_id, "loop": (loop or {}).get("name"), "status": run.get("status"),
           "secs": run.get("secs"), **{k: st.get(k, 0) for k in FIELDS}}
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_file(), "a") as f:
        f.write(json.dumps(row) + "\n")


def summary(now=None):
    now = now or time.time()
    rows = []
    if os.path.isfile(_file()):
        for line in open(_file()):
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass  # torn write
    def total(rs):
        t = {k: sum(r.get(k) or 0 for r in rs) for k in FIELDS}
        t["runs"], t["failed"] = len(rs), sum(1 for r in rs if r.get("status") != "done")
        t["cost_usd"] = round(t["cost_usd"], 4)
        return t
    by_loop = {}
    for r in rows:
        by_loop.setdefault(r.get("loop") or "?", []).append(r)
    return {"today": total([r for r in rows if r["ts"] >= now - 86400]),
            "week": total([r for r in rows if r["ts"] >= now - 7 * 86400]),
            "all": total(rows),
            "by_loop": sorted(({"loop": k, **total(v)} for k, v in by_loop.items()), key=lambda x: -x["cost_usd"]),
            "recent": rows[-20:][::-1]}
