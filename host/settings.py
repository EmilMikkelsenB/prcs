"""Settings page backend. Two kinds of values:
- runtime: stored in data/config.json, read at use time, apply instantly.
- env: keys in the project's .env (mounted at ENV_FILE). Keys marked "process"
  are re-read on host restart (loaded into os.environ at startup); "compose"
  keys (published port, KB folder) only change on `docker compose up -d`.
"""
import os
import re

import config

ENV_FILE = os.environ.get("ENV_FILE", "/app/.env")

# key: (type, default, min, max, label, help)
RUNTIME = {
    "runner_url": ("url", config.DEFAULT_RUNNER_URL, None, None, "Runner URL", "Where the runner (git + gh + claude) is reachable."),
    "scheduler_tick": ("int", 10, 2, 3600, "Scheduler tick (seconds)", "How often flowpaths are checked."),
    "kb_dir": ("str", "/app/kb", None, None, "KB folder (inside the container)", "Leave as /app/kb unless you mounted elsewhere; the real folder on your machine is KB_PATH below."),
    "kb_sync_interval": ("int", 3600, 0, 86400, "KB repo sync interval (seconds, 0 = manual only)", "Pulls docs from each loop's target repo."),
    "improve_model": ("str", "claude-sonnet-5-5", None, None, "Model for Improve (loop form)", "Used when you press Improve on a loop idea."),
    "terse_mode": ("choice", "on", ["off", "on", "ultra"], None, "Terse output (caveman style)", "Tells Claude to write fewer output tokens: shorter answers, same code and files. Lowers cost; run notes read more tersely. ultra = shortest."),
    "kb_extensions": ("str", "md,mdx,txt,rst", None, None, "KB file types to sync", "Comma-separated extensions."),
}

# key: (label, secret, restart, help)
ENV = {
    "ADMIN_USER": ("Admin username", False, "process", "Only used to create the account on first boot."),
    "ADMIN_PASSWORD": ("Admin password", True, "process", "Only used on first boot; ignored once data/users.json exists."),
    "GITHUB_OAUTH_CLIENT_ID": ("GitHub OAuth client ID", False, "process", ""),
    "GITHUB_OAUTH_CLIENT_SECRET": ("GitHub OAuth client secret", True, "process", ""),
    "HOST_PORT": ("Dash port on this machine", False, "compose", "Needs `docker compose up -d` on the machine."),
    "KB_PATH": ("KB folder on this machine", False, "compose", "Real folder (e.g. ./kb or D:/notes/kb). Needs `docker compose up -d`."),
}

_BARE = re.compile(r"^[\w./:@+-]*$")


def _fmt(v):
    if _BARE.match(v):
        return v
    if "'" in v or "\n" in v or "\r" in v:
        raise ValueError("values may not contain quotes or newlines")
    return "'" + v + "'"


def read_env():
    out = {}
    if os.path.isfile(ENV_FILE):
        for line in open(ENV_FILE, encoding="utf-8"):
            m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)=(.*?)\s*$", line)
            if m:
                v = m.group(2)
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
                    v = v[1:-1]
                out[m.group(1)] = v
    return out


def write_env(updates):
    if os.path.isdir(ENV_FILE):
        raise ValueError(".env is a directory - create the .env file next to docker-compose.yml and recreate the stack")
    lines = open(ENV_FILE, encoding="utf-8").read().splitlines() if os.path.isfile(ENV_FILE) else []
    left = dict(updates)
    for i, line in enumerate(lines):
        m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)=", line)
        if m and m.group(1) in left:
            lines[i] = m.group(1) + "=" + _fmt(left.pop(m.group(1)))
    lines += [k + "=" + _fmt(v) for k, v in left.items()]
    with open(ENV_FILE, "w", encoding="utf-8", newline="\n") as f:  # in place: it's a bind-mounted file
        f.write("\n".join(lines) + "\n")


def load_env_into_os():
    for k, v in read_env().items():
        if k in ENV and ENV[k][2] == "process":
            os.environ[k] = v


def _coerce(key, val):
    typ, _, lo, hi, label, _h = RUNTIME[key]
    if typ == "choice":
        if val not in lo:
            raise ValueError("%s must be one of %s" % (label, ", ".join(lo)))
        return val
    if typ == "int":
        try:
            val = int(val)
        except (TypeError, ValueError):
            raise ValueError(label + " must be a number")
        if not lo <= val <= hi:
            raise ValueError("%s must be between %s and %s" % (label, lo, hi))
        return val
    val = str(val or "").strip()
    if typ == "url":
        val = val.rstrip("/")
        if not config._URL_RE.match(val):
            raise ValueError("Runner URL must look like http://host:port")
    elif not val:
        raise ValueError(label + " can't be empty")
    return val


def get_all():
    env = read_env()
    return {
        "runtime": [{"key": k, "type": t, "value": config.get_runner_url() if k == "runner_url" else config.get(k, d),
                     "label": l, "help": h, "min": None if t == "choice" else lo, "max": hi,
                     "options": lo if t == "choice" else None}
                    for k, (t, d, lo, hi, l, h) in RUNTIME.items()],
        "env": [{"key": k, "label": l, "secret": s, "restart": r, "help": h,
                 "value": "" if s else env.get(k, ""), "set": k in env}
                for k, (l, s, r, h) in ENV.items()],
    }


def save(body):
    rt = {k: _coerce(k, v) for k, v in (body.get("runtime") or {}).items() if k in RUNTIME}
    cur = read_env()
    # blank secret = keep current; unchanged values aren't "changes"
    env = {k: str(v) for k, v in (body.get("env") or {}).items()
           if k in ENV and not (ENV[k][1] and v == "") and str(v) != cur.get(k, "")}
    for v in env.values():
        _fmt(v)  # validate before writing anything
    if rt:
        config.set_many(rt)
    if env:
        write_env(env)
    return {"restart_needed": any(ENV[k][2] == "process" for k in env),
            "compose_needed": any(ENV[k][2] == "compose" for k in env)}
