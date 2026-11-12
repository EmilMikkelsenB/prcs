"""Queues: named, per-repo sets of work items, stored as plain files in the KB so you can read, edit and add to them.

  queues/<owner__repo>/<queue>/<item>.md              pending (oldest first)
  queues/<owner__repo>/<queue>/in-progress/<item>.md  claimed by a running loop
  queues/<owner__repo>/<queue>/done/<item>.md         finished

Any loop can write a queue (its new files become items) and any loop can read one (it claims the oldest item when it
starts; the item moves to done/ on success or back to pending on failure). The item's text goes into the run's prompt,
because a run's checkout is wiped before every run and can't hold another loop's files."""
import json
import os
import re
import shutil
import threading
import time

import config
import kb

_lock = threading.Lock()
NAME_RE = re.compile(r"^[\w-]{1,40}$")


def _migrate():
    """Pre-queues installs kept a single backlog at backlog/<repo>/; it becomes the 'backlog' queue."""
    old, new = os.path.join(kb.root(), "backlog"), os.path.join(kb.root(), "queues")
    if not os.path.isdir(old):
        return
    for repo in os.listdir(old):
        dest = os.path.join(new, repo, "backlog")
        if not os.path.exists(dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(os.path.join(old, repo), dest)
    shutil.rmtree(old, ignore_errors=True)


def _dir(repo, queue):
    _migrate()
    if not NAME_RE.match(queue or ""):
        raise ValueError("queue names use letters, numbers, - and _ (max 40)")
    return os.path.join(kb.root(), "queues", repo.replace("/", "__"), queue)


def _claims_file():
    return os.path.join(config.DATA_DIR, "claims.json")


def _load_claims():
    try:
        return json.load(open(_claims_file()))
    except (OSError, ValueError):
        return {}


def _save_claims(c):
    os.makedirs(os.path.dirname(_claims_file()), exist_ok=True)
    json.dump(c, open(_claims_file(), "w"))


def add_items(repo, queue, files):
    """files: {path: text} from a run. Returns the number of items written."""
    d = _dir(repo, queue)
    os.makedirs(d, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    n = 0
    for path, text in (files or {}).items():
        name = os.path.basename(path)
        if not os.path.splitext(name)[1]:
            name += ".md"
        out = os.path.join(d, "%s-%s" % (stamp, name))
        i = 1
        while os.path.exists(out):  # same-second duplicates
            i += 1
            out = os.path.join(d, "%s-%d-%s" % (stamp, i, name))
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        n += 1
    return n


def _files(d):
    return sorted(f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f)) and not f.startswith(".")) if os.path.isdir(d) else []


def pending(repo, queue):
    return _files(_dir(repo, queue))


def claim(repo, queue):
    """Move the oldest pending item to in-progress/. Returns {"repo","queue","name","text"} or None."""
    with _lock:
        items = pending(repo, queue)
        if not items:
            return None
        d = _dir(repo, queue)
        os.makedirs(os.path.join(d, "in-progress"), exist_ok=True)
        os.replace(os.path.join(d, items[0]), os.path.join(d, "in-progress", items[0]))
        text = open(os.path.join(d, "in-progress", items[0]), encoding="utf-8", errors="replace").read()
        return {"repo": repo, "queue": queue, "name": items[0], "text": text}


def _move(c, dest):
    d = _dir(c["repo"], c["queue"])
    src = os.path.join(d, "in-progress", c["name"])
    if not os.path.isfile(src):
        return
    target = d if dest is None else os.path.join(d, dest)
    os.makedirs(target, exist_ok=True)
    os.replace(src, os.path.join(target, c["name"]))


def release(c):
    """Put a claimed item back (the run never started)."""
    with _lock:
        _move(c, None)


def record_claim(run_id, c):
    with _lock:
        claims = _load_claims()
        claims[run_id] = {k: c[k] for k in ("repo", "queue", "name")}
        _save_claims(claims)


def settle(run_id, status):
    """A run ended: done -> done/, anything else -> back to pending."""
    with _lock:
        claims = _load_claims()
        c = claims.pop(run_id, None)
        if not c:
            return
        _move(c, "done" if status == "done" else None)
        _save_claims(claims)


def summary():
    """Every queue with item counts, for the Overview."""
    _migrate()
    base, out = os.path.join(kb.root(), "queues"), []
    for repo in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        for q in sorted(os.listdir(os.path.join(base, repo))):
            d = os.path.join(base, repo, q)
            if os.path.isdir(d):
                out.append({"repo": repo.replace("__", "/", 1), "queue": q, "pending": len(_files(d)),
                            "in_progress": len(_files(os.path.join(d, "in-progress"))), "done": len(_files(os.path.join(d, "done")))})
    return out
