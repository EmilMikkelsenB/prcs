"""Runs started outside a flowpath (Run now, Retry, queue watchers). The scheduler's tick finishes them the same
way as flowpath runs (KB note + usage ledger + queues), so they're tracked here until they end.
Also a per-loop cooldown so a failing auto-started loop doesn't retry (and spend money) every tick."""
import json
import os
import threading

DATA_DIR = os.environ.get("DASH_DATA", "/app/data")
_lock = threading.Lock()


def _path(name):
    return os.path.join(DATA_DIR, name)


def _load(name):
    try:
        return json.load(open(_path(name)))
    except (OSError, ValueError):
        return {}


def _save(name, d):
    os.makedirs(DATA_DIR, exist_ok=True)
    json.dump(d, open(_path(name), "w"))


def add(run_id, loop_id):
    with _lock:
        d = _load("manual_runs.json")
        d[run_id] = loop_id
        _save("manual_runs.json", d)


def pending():
    return _load("manual_runs.json")


def remove(run_id):
    with _lock:
        d = _load("manual_runs.json")
        d.pop(run_id, None)
        _save("manual_runs.json", d)


def set_cooldown(loop_id, until):
    with _lock:
        d = _load("cooldown.json")
        d[loop_id] = until
        _save("cooldown.json", d)


def cooldown_until(loop_id):
    return _load("cooldown.json").get(loop_id, 0)
