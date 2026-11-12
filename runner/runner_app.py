"""Runner container's internal API: start/stop/query a loop run.
Only reachable from the host over the private compose network."""
import json
import os
import subprocess
import sys
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_loop  # noqa: E402
import workspace  # noqa: E402

BIND = os.environ.get("RUNNER_BIND", "0.0.0.0")
PORT = int(os.environ.get("RUNNER_PORT", "8089"))

_lock = threading.Lock()
_runs = {}  # run_id -> {"status", "rc", "secs", "log_tail", "output", "output_id", "cancel": Event}


def _execute(run_id, loop_config, github_token, upstream_output):
    cancel = _runs[run_id]["cancel"]
    try:
        ws = workspace.ensure_workspace(loop_config["target_repo"], github_token)
        result = run_loop.run(loop_config, ws, github_token, upstream_output, cancel_event=cancel)
    except Exception:
        result = {"status": "failed", "rc": -1, "secs": 0, "log_tail": traceback.format_exc(),
                   "output": {}, "output_id": None}
    with _lock:
        _runs[run_id].update(result, finished_at=time.time())


_ver = []


def _claude_version():
    if not _ver:  # cached: spawning node every health poll is wasteful
        try:
            _ver.append(subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=20).stdout.strip() or None)
        except Exception:
            _ver.append(None)
    return _ver[0]


class H(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        if self.path == "/health":
            return self._json({"ok": True, "service": "runner", "claude_version": _claude_version(),
                               "logged_in": os.path.isfile(os.path.expanduser("~/.claude/.credentials.json"))})
        if self.path == "/runs":
            with _lock:  # list view omits log_tail; fetch /runs/<id> for it
                rows = [{k: v for k, v in dict(r, id=i).items() if k not in ("cancel", "log_tail")} for i, r in _runs.items()]
            return self._json(sorted(rows, key=lambda r: r["started_at"], reverse=True)[:50])
        if self.path.startswith("/runs/"):
            run_id = self.path.split("/")[2]
            with _lock:
                r = _runs.get(run_id)
            if not r:
                return self._json({"error": "unknown run"}, 404)
            return self._json({k: v for k, v in r.items() if k != "cancel"})
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path == "/runs":
            body = self._body()
            run_id = uuid.uuid4().hex[:12]
            with _lock:
                _runs[run_id] = {"status": "running", "rc": None, "secs": None,
                                  "log_tail": "", "output": {}, "output_id": None,
                                  "started_at": time.time(), "cancel": threading.Event(),
                                  "loop": {k: body["loop_config"].get(k) for k in ("id", "name", "role", "target_repo")}}
            t = threading.Thread(target=_execute, args=(
                run_id, body["loop_config"], body["github_token"], body.get("upstream_output")), daemon=True)
            t.start()
            return self._json({"run_id": run_id})
        if self.path.endswith("/stop"):
            run_id = self.path.split("/")[2]
            with _lock:
                r = _runs.get(run_id)
                if r:
                    r["cancel"].set()
            return self._json({"ok": bool(r)})
        self._json({"error": "not found"}, 404)

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer((BIND, PORT), H).serve_forever()
