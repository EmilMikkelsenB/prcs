"""Flowpath CRUD + the pure scheduling decisions a flowpath runs on.

A flowpath is an ordered list of links: [{loop_id, trigger_mode}, ...].
`trigger_mode` is "once" (this link runs exactly once per new upstream
output, then hands off) or "continuous" (this link keeps its own sleep/retry
schedule, gated on the previous link's output being new). Mode is per link.

State per flowpath (data/flowpaths/<id>.state.json) tracks, per link index:
last_run_id, last_run_at, last_output_id (what this link's last run produced)
and last_consumed_upstream_id (the upstream output_id this link last reacted
to). The decision functions below are pure so they're unit-testable without
a runner or clock mocking beyond passing `now` explicitly.
"""
import json
import os
import time
import uuid

DATA_DIR = os.environ.get("DASH_DATA", "/app/data")
FLOWPATHS_DIR = os.path.join(DATA_DIR, "flowpaths")
TRIGGER_MODES = {"once", "continuous"}


def _path(flowpath_id):
    return os.path.join(FLOWPATHS_DIR, f"{flowpath_id}.json")


def _state_path(flowpath_id):
    return os.path.join(FLOWPATHS_DIR, f"{flowpath_id}.state.json")


def _validate(cfg, loop_exists):
    links = cfg.get("links")
    if not links or not isinstance(links, list):
        raise ValueError("links must be a non-empty list")
    for link in links:
        if link.get("trigger_mode") not in TRIGGER_MODES:
            raise ValueError(f"trigger_mode must be one of {sorted(TRIGGER_MODES)}")
        if not loop_exists(link.get("loop_id")):
            raise ValueError(f"unknown loop_id {link.get('loop_id')}")
    if not cfg.get("name"):
        raise ValueError("name is required")


def list_flowpaths():
    os.makedirs(FLOWPATHS_DIR, exist_ok=True)
    out = []
    for fn in sorted(os.listdir(FLOWPATHS_DIR)):
        if fn.endswith(".json") and not fn.endswith(".state.json"):
            out.append(json.load(open(os.path.join(FLOWPATHS_DIR, fn))))
    return out


def get(flowpath_id):
    try:
        return json.load(open(_path(flowpath_id)))
    except OSError:
        return None


def create(cfg, loop_exists):
    _validate(cfg, loop_exists)
    cfg = dict(cfg)
    cfg["id"] = uuid.uuid4().hex[:12]
    cfg["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    os.makedirs(FLOWPATHS_DIR, exist_ok=True)
    json.dump(cfg, open(_path(cfg["id"]), "w"), indent=2)
    return cfg


def update(flowpath_id, cfg, loop_exists):
    existing = get(flowpath_id)
    if not existing:
        raise ValueError("unknown flowpath")
    merged = {**existing, **cfg, "id": flowpath_id}
    _validate(merged, loop_exists)
    json.dump(merged, open(_path(flowpath_id), "w"), indent=2)
    return merged


def delete(flowpath_id):
    for p in (_path(flowpath_id), _state_path(flowpath_id)):
        try:
            os.remove(p)
        except OSError:
            pass


def load_state(flowpath_id):
    try:
        return json.load(open(_state_path(flowpath_id)))
    except OSError:
        return {}


def save_state(flowpath_id, state):
    os.makedirs(FLOWPATHS_DIR, exist_ok=True)
    tmp = _state_path(flowpath_id) + ".tmp"
    json.dump(state, open(tmp, "w"), indent=2)
    os.replace(tmp, _state_path(flowpath_id))


# --- pure scheduling decisions -------------------------------------------

def should_trigger(trigger_mode, now, run_in_progress, upstream_output_id,
                    last_consumed_upstream_id, last_run_at, sleep_secs, is_first_link):
    """Should this link start a new run right now?"""
    if trigger_mode not in TRIGGER_MODES:
        raise ValueError(f"unknown trigger_mode {trigger_mode}")
    if run_in_progress:
        return False
    if trigger_mode == "once":
        if is_first_link:
            return last_run_at is None  # a first-link "once" link just runs once, ever
        if upstream_output_id is None:
            return False
        return upstream_output_id != last_consumed_upstream_id
    # continuous: keeps its own schedule; if chained, still gated on new upstream output.
    if not is_first_link and upstream_output_id is not None and upstream_output_id == last_consumed_upstream_id:
        return False
    if last_run_at is None:
        return True
    return (now - last_run_at) >= sleep_secs


def output_ready_for_downstream(output_id, last_consumed_by_downstream_id):
    """Has this link produced output the next link hasn't reacted to yet?"""
    return output_id is not None and output_id != last_consumed_by_downstream_id
