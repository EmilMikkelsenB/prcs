"""Local knowledge base: a real folder of text files (source of truth, editable
from disk or the site) plus a SQLite FTS5 index at <kb>/.index.db for search.

  repos/<owner__repo>/...  mirror of docs from each loop's target repo (overwritten on sync)
  runs/<loop>/...          one note per finished flowpath run
  notes/...                yours - the only place the site edits/deletes
"""
import io
import json
import os
import re
import shutil
import sqlite3
import tarfile
import threading
import time
import traceback
import urllib.request

import config
import github_oauth
import loops

DEFAULT_DIR = "/app/kb"
MAX_FILE = 512 * 1024
MAX_TARBALL = 100 * 1024 * 1024
MAX_FILES_PER_REPO = 2000
_REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")
_sync_lock = threading.Lock()


def root():
    d = os.path.realpath(config.get("kb_dir", DEFAULT_DIR))
    os.makedirs(d, exist_ok=True)
    return d


def _exts():
    return {"." + e.strip().lstrip(".").lower() for e in config.get("kb_extensions", "md,mdx,txt,rst").split(",") if e.strip()}


def _safe(rel):
    """Absolute path for a KB-relative path; ValueError if it escapes or hits a dotfile."""
    r = root()
    full = os.path.realpath(os.path.join(r, rel))
    if not full.startswith(r + os.sep) or any(p.startswith(".") for p in os.path.relpath(full, r).split(os.sep)):
        raise ValueError("invalid path")
    return full


def _title(text, rel):
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else os.path.basename(rel)


def _db():
    db = sqlite3.connect(os.path.join(root(), ".index.db"))
    db.execute("create table if not exists meta(path text primary key, mtime real)")
    db.execute("create virtual table if not exists fts using fts5(path unindexed, title, body)")
    return db


def reindex():
    """Incremental: only files whose mtime changed. Picks up edits made directly on disk."""
    r, exts = root(), _exts()
    db = _db()
    known = dict(db.execute("select path, mtime from meta"))
    seen = set()
    for dp, dns, fns in os.walk(r):
        dns[:] = [d for d in dns if not d.startswith(".")]
        for fn in fns:
            if fn.startswith(".") or os.path.splitext(fn)[1].lower() not in exts:
                continue
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, r).replace(os.sep, "/")
            seen.add(rel)
            mt = os.path.getmtime(full)
            if known.get(rel) == mt:
                continue
            text = open(full, encoding="utf-8", errors="replace").read(MAX_FILE)
            db.execute("delete from fts where path=?", (rel,))
            db.execute("insert into fts(path,title,body) values(?,?,?)", (rel, _title(text, rel), text))
            db.execute("insert or replace into meta values(?,?)", (rel, mt))
    for rel in set(known) - seen:
        db.execute("delete from fts where path=?", (rel,))
        db.execute("delete from meta where path=?", (rel,))
    db.commit()
    db.close()


def search(q):
    reindex()
    db = _db()
    q = (q or "").strip()
    if q:
        match = " ".join('"%s"*' % t.replace('"', "") for t in q.split())
        rows = db.execute("select path, title, snippet(fts,2,'','','...',14) from fts where fts match ? order by rank limit 50", (match,)).fetchall()
    else:
        rows = db.execute("select f.path, f.title, '' from fts f join meta m on m.path=f.path order by m.mtime desc limit 500").fetchall()
    db.close()
    return [{"path": p, "title": t, "snippet": s, "editable": _editable(p)} for p, t, s in rows]


EDITABLE = ("notes/", "queues/")


def _editable(rel):
    return rel.startswith(EDITABLE)


def read_file(rel):
    full = _safe(rel)
    if not os.path.isfile(full):
        raise ValueError("no such file")
    return {"path": rel, "content": open(full, encoding="utf-8", errors="replace").read(MAX_FILE),
            "editable": _editable(rel)}


def write_note(rel, content):
    rel = rel.strip().lstrip("/")
    if not _editable(rel) or rel.endswith("/"):
        raise ValueError("the site only edits files under notes/ and queues/")
    if not os.path.splitext(rel)[1]:
        rel += ".md"
    if len(content.encode()) > MAX_FILE:
        raise ValueError("note too large")
    full = _safe(rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    return {"path": rel}


def delete_note(rel):
    if not _editable(rel):
        raise ValueError("the site only deletes files under notes/ and queues/")
    full = _safe(rel)
    if os.path.isfile(full):
        os.remove(full)


def _slug(s):
    return re.sub(r"[^\w.-]+", "-", s or "unnamed").strip("-")[:60] or "unnamed"


def save_run(loop, run_id, run):
    if not loop:
        return
    d = os.path.join(root(), "runs", _slug(loop.get("name")))
    os.makedirs(d, exist_ok=True)
    st = run.get("stats") or {}
    # Claude's answer first (the part you want to read); bookkeeping after the rule.
    body = ("# %s - %s\n\n%s\n\n---\n\n## Run details\n\n- repo: %s\n- permissions: %s\n- exit code: %s, %ss\n"
            "- cost: $%.4f, %s in / %s out tokens\n\n```json\n%s\n```\n" % (
        loop.get("name"), run.get("status"), (run.get("log_tail") or "_No output._").strip(),
        loop.get("target_repo"), loop.get("permissions"), run.get("rc"), run.get("secs"),
        st.get("cost_usd") or 0, st.get("input_tokens", 0), st.get("output_tokens", 0),
        json.dumps(dict(run.get("output") or {}, files=list((run.get("output") or {}).get("files") or {})), indent=2)))
    name = "%s-%s.md" % (time.strftime("%Y%m%d-%H%M%S"), run_id)
    with open(os.path.join(d, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(body)


def _extract(tar_bytes, dest, exts):
    """Write matching text files from a GitHub tarball into dest (fresh dir). Returns file count."""
    n = 0
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tf:
        for m in tf:
            parts = m.name.split("/")[1:]  # drop the "<owner>-<repo>-<sha>/" prefix
            if (not m.isfile() or not parts or m.size > MAX_FILE or ".." in parts
                    or any(p.startswith(".") or not p for p in parts)
                    or os.path.splitext(parts[-1])[1].lower() not in exts):
                continue
            if n >= MAX_FILES_PER_REPO:
                break
            out = os.path.join(dest, *parts)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "wb") as f:
                f.write(tf.extractfile(m).read())
            n += 1
    return n


def _sync_repo(repo, token, exts):
    if not _REPO_RE.match(repo):
        raise ValueError("bad repo name")
    req = urllib.request.Request("https://api.github.com/repos/%s/tarball" % repo, headers={
        "Authorization": "Bearer " + token, "User-Agent": github_oauth.USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read(MAX_TARBALL + 1)
    if len(data) > MAX_TARBALL:
        raise ValueError("repo tarball too large")
    base = os.path.join(root(), "repos")
    name = repo.replace("/", "__")
    dest, tmp = os.path.join(base, name), os.path.join(base, name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    n = _extract(data, tmp, exts)
    shutil.rmtree(dest, ignore_errors=True)
    os.rename(tmp, dest)
    return n


def sync_repos():
    token = github_oauth.load_token()
    if not token:
        raise ValueError("connect GitHub first")
    if not _sync_lock.acquire(blocking=False):
        raise ValueError("a sync is already running")
    try:
        results = {}
        for repo in sorted({l["target_repo"] for l in loops.list_loops()}):
            try:
                results[repo] = _sync_repo(repo, token, _exts())
            except Exception as e:
                results[repo] = "error: %s" % e
        reindex()
        config.set_many({"kb_last_sync": time.time()})
        return {"results": results}
    finally:
        _sync_lock.release()


def status():
    return {"dir": config.get("kb_dir", DEFAULT_DIR), "last_sync": config.get("kb_last_sync"),
            "interval": config.get("kb_sync_interval", 3600)}


def start_background():
    def loop():
        while True:
            time.sleep(30)
            try:
                iv = config.get("kb_sync_interval", 3600)
                if iv and time.time() - (config.get("kb_last_sync") or 0) >= iv and github_oauth.load_token():
                    sync_repos()
            except Exception:
                traceback.print_exc()
    threading.Thread(target=loop, daemon=True).start()
