"""Loop CRUD: generic config replacing rotaria-dash's two hardcoded shell scripts.

A loop = target repo + prompt + model/review + permissions (what it may do) + input (where its work comes
from: nothing, a queue, or the previous flowpath step) + output (which queue its new files go to) + tuning knobs.
Stored one JSON file per loop under data/loops/<id>.json — portable: copying
that file to another install's data/loops/ brings the loop with it.
"""
import json
import os
import re
import time
import uuid

DATA_DIR = os.environ.get("DASH_DATA", "/app/data")
LOOPS_DIR = os.path.join(DATA_DIR, "loops")
PERMISSIONS = {"read", "files", "push"}  # read-only | write files, no git | commit, push and open PRs
INPUT_TYPES = {"none", "queue", "previous"}
_QUEUE_RE = re.compile(r"^[\w-]{1,40}$")

# Same shape as rotaria-dash's server/tuning.py: {key: (default, min, max, label, help)}.
TUNING_KEYS = {
    "MAX_RUNS": (25, 1, 500, "Stop after this many runs", "A guard against a run that never finishes (consumer loops)."),
    "FULL_SLEEP": (1800, 60, 86400, "Wait when there's nothing to do (seconds)", "How long a producer loop sleeps when its backlog is full."),
    "RETRY_SLEEP": (900, 60, 86400, "Wait after a failed or very short run (seconds)", "Usually a usage limit or an error."),
}


def tuning_defaults():
    return {k: {"default": d[0], "min": d[1], "max": d[2], "label": d[3], "help": d[4]} for k, d in TUNING_KEYS.items()}


# Starting points for the loop form, not full configs (no target_repo).
def _t(id, name, permissions, text, reads="", writes=""):
    return {"id": id, "name": name, "permissions": permissions, "focus_text": text,
            "input": {"type": "queue", "queue": reads, "auto": True} if reads else {"type": "none"},
            "output": {"queue": writes}}


TEMPLATES = [
    _t("bug-triage", "Bug triage", "files", "Scan open issues and recent error reports. Write one file per real, reproducible bug - skip feature requests and vague reports.", writes="backlog"),
    _t("feature-ideas", "Feature ideas", "files", "Propose small, self-contained user-facing improvements. Write one file per idea, each small enough to implement and review in a single PR.", writes="backlog"),
    _t("implement-backlog", "Implement backlog item", "push", "Implement the item you were given fully, run the project's checks, and open a PR.", reads="backlog"),
    _t("dependency-bump", "Dependency updates", "push", "Check for outdated dependencies with available patch/minor updates. Bump them, run the project's checks, and open a PR per logical group of updates."),
]


def templates():
    return TEMPLATES


def _path(loop_id):
    return os.path.join(LOOPS_DIR, f"{loop_id}.json")


def normalize(cfg):
    """Fill in permissions/input/output; converts old loops that only have a producer/consumer role."""
    out = dict(cfg)
    role = out.pop("role", None)
    out.setdefault("permissions", "push" if role == "consumer" else "files")
    if not out.get("input"):
        out["input"] = {"type": "queue", "queue": "backlog", "auto": False} if role == "consumer" else {"type": "none"}
    if out.get("output") is None:
        out["output"] = {"queue": "backlog" if role == "producer" else ""}
    return out


def _validate(cfg):
    if cfg.get("permissions") not in PERMISSIONS:
        raise ValueError(f"permissions must be one of {sorted(PERMISSIONS)}")
    inp, outp = cfg.get("input") or {}, cfg.get("output") or {}
    if inp.get("type") not in INPUT_TYPES:
        raise ValueError(f"input type must be one of {sorted(INPUT_TYPES)}")
    for q in ([inp.get("queue")] if inp.get("type") == "queue" else []) + ([outp["queue"]] if outp.get("queue") else []):
        if not isinstance(q, str) or not _QUEUE_RE.match(q):
            raise ValueError("queue names use letters, numbers, - and _ (max 40)")
    if inp.get("type") == "queue" and inp.get("queue") == outp.get("queue"):
        raise ValueError("a loop can't read and write the same queue - it would feed itself forever")
    if not cfg.get("name") or not isinstance(cfg["name"], str):
        raise ValueError("name is required")
    if not cfg.get("target_repo") or not isinstance(cfg["target_repo"], str):
        raise ValueError("target_repo is required")
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", cfg["target_repo"]):
        raise ValueError("target_repo must look like owner/repo")
    focus = cfg.get("focus") or {}
    if focus.get("id") == "custom":
        if not focus.get("text") or len(focus["text"]) > 4000:
            raise ValueError("custom focus text must be 1-4000 chars")
    elif not focus.get("text"):
        raise ValueError("focus.text is required")
    if not isinstance(cfg.get("model", ""), str) or len(cfg.get("model", "")) > 80:
        raise ValueError("model must be a short model id")
    review = cfg.get("review") or {}
    if not isinstance(review, dict) or not isinstance(review.get("model", ""), str) or len(review.get("prompt", "")) > 2000:
        raise ValueError("review settings are invalid")
    tuning = cfg.get("tuning") or {}
    for k, v in tuning.items():
        if k not in TUNING_KEYS:
            raise ValueError(f"unknown tuning key {k}")
        _, lo, hi, *_ = TUNING_KEYS[k]
        if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
            raise ValueError(f"{k} must be a whole number from {lo} to {hi}")


def _with_defaults(cfg):
    out = dict(cfg)
    out["tuning"] = {k: out.get("tuning", {}).get(k, d[0]) for k, d in TUNING_KEYS.items()}
    return out


def list_loops():
    os.makedirs(LOOPS_DIR, exist_ok=True)
    out = []
    for fn in sorted(os.listdir(LOOPS_DIR)):
        if fn.endswith(".json"):
            out.append(normalize(json.load(open(os.path.join(LOOPS_DIR, fn)))))
    return out


def get(loop_id):
    try:
        return normalize(json.load(open(_path(loop_id))))
    except OSError:
        return None


def create(cfg):
    cfg = normalize(cfg)
    _validate(cfg)
    cfg = _with_defaults(cfg)
    cfg["id"] = uuid.uuid4().hex[:12]
    cfg["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    os.makedirs(LOOPS_DIR, exist_ok=True)
    json.dump(cfg, open(_path(cfg["id"]), "w"), indent=2)
    return cfg


def update(loop_id, cfg):
    existing = get(loop_id)
    if not existing:
        raise ValueError("unknown loop")
    merged = {**existing, **cfg, "id": loop_id}
    _validate(merged)
    merged = _with_defaults(merged)
    json.dump(merged, open(_path(loop_id), "w"), indent=2)
    return merged


def delete(loop_id):
    try:
        os.remove(_path(loop_id))
        return True
    except OSError:
        return False
