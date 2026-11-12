"""Host container: UI + API. Stdlib http.server, no framework, mirrors
rotaria-dash/server/app.py's routing idiom (regex routes, _json/_static
helpers) with cookie-session auth instead of a shared-secret header.
"""
import json
import os
import re
import sys
import time
import uuid
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auth  # noqa: E402
import config  # noqa: E402
import flowpaths  # noqa: E402
import github_oauth  # noqa: E402
import loops  # noqa: E402
import runner_client  # noqa: E402
import scheduler  # noqa: E402

BIND = os.environ.get("HOST_BIND", "0.0.0.0")
PORT = int(os.environ.get("HOST_PORT", "8088"))
DIST = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
PUBLIC_PATHS = {"/api/health", "/auth/login"}

_oauth_states = {}  # state -> expiry, for the GitHub connect CSRF check


class H(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _user(self):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        tok = cookie["session"].value if "session" in cookie else None
        return auth.verify_session(tok)

    def _auth(self, p):
        if p in PUBLIC_PATHS or p.startswith("/assets/") or not p.startswith(("/api/", "/auth/")):
            return True
        if self._user():
            return True
        self._json({"error": "unauthorized"}, 401)
        return False

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def _set_session_cookie(self, username):
        self.send_header("Set-Cookie", f"session={auth.make_session(username)}; HttpOnly; Path=/; "
                                        f"Max-Age={auth.SESSION_MAX_AGE}; SameSite=Lax")

    # --- GET -------------------------------------------------------------

    def do_GET(self):
        p = urlparse(self.path).path
        q = parse_qs(urlparse(self.path).query)
        if not self._auth(p):
            return
        try:
            if p == "/api/health":
                return self._json({"ok": True, "service": "host"})
            if p == "/api/runner":
                return self._json({"ok": True, "runner": self._runner_health()})
            if p == "/api/config":
                configured = config.try_auto_configure(self._probe_runner)
                return self._json({"runner_url": config.get_runner_url(),
                                    "runner_url_configured": configured})
            if p == "/api/loops/templates":
                return self._json(loops.templates())
            if p == "/api/loops":
                return self._json(loops.list_loops())
            if p == "/api/loops/tuning-keys":
                return self._json(loops.tuning_defaults())
            if p == "/api/flowpaths":
                return self._json(flowpaths.list_flowpaths())
            if p == "/api/github/status":
                return self._json({"connected": github_oauth.connected()})
            if p == "/api/github/repos":
                return self._json(github_oauth.list_repos(github_oauth.load_token()))
            m = re.match(r"^/api/runs/([\w]+)$", p)
            if m:
                return self._json(runner_client.get_run(m.group(1)))
            if p == "/auth/github/start":
                return self._github_start()
            if p == "/auth/github/callback":
                return self._github_callback(q)
        except Exception as e:
            return self._json({"error": str(e)}, 500)
        self._static(p)

    def _runner_health(self):
        import urllib.error
        import urllib.request
        try:
            with urllib.request.urlopen(f"{config.get_runner_url()}/health", timeout=5) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError):
            return {"ok": False}

    def _probe_runner(self, url):
        import urllib.error
        import urllib.request
        try:
            urllib.request.urlopen(f"{url}/health", timeout=1.5)
            return True
        except Exception:
            return False

    # --- POST / DELETE -----------------------------------------------------

    def do_POST(self):
        p = urlparse(self.path).path
        if not self._auth(p):
            return
        body = self._body()
        try:
            if p == "/auth/login":
                if auth.check_login(body.get("username", ""), body.get("password", "")):
                    self.send_response(200)
                    self._set_session_cookie(body["username"])
                    self.send_header("Content-Type", "application/json")
                    b = json.dumps({"ok": True}).encode()
                    self.send_header("Content-Length", str(len(b)))
                    self.end_headers()
                    self.wfile.write(b)
                    return
                return self._json({"error": "invalid username or password"}, 401)
            if p == "/auth/logout":
                self.send_response(200)
                self.send_header("Set-Cookie", "session=; HttpOnly; Path=/; Max-Age=0")
                self.send_header("Content-Type", "application/json")
                b = json.dumps({"ok": True}).encode()
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
                return
            if p == "/api/config":
                return self._json({"runner_url": config.set_runner_url(body.get("runner_url"))})
            if p == "/api/loops":
                return self._json(loops.create(body))
            m = re.match(r"^/api/loops/(\w+)$", p)
            if m:
                return self._json(loops.update(m.group(1), body))
            if p == "/api/flowpaths":
                return self._json(flowpaths.create(body, lambda lid: loops.get(lid) is not None))
            m = re.match(r"^/api/flowpaths/(\w+)$", p)
            if m:
                return self._json(flowpaths.update(m.group(1), body, lambda lid: loops.get(lid) is not None))
            m = re.match(r"^/api/runs/([\w]+)/stop$", p)
            if m:
                return self._json(runner_client.stop_run(m.group(1)))
        except ValueError as e:
            return self._json({"error": str(e)}, 400)
        except Exception as e:
            return self._json({"error": str(e)}, 500)
        self._json({"error": "not found"}, 404)

    def do_DELETE(self):
        p = urlparse(self.path).path
        if not self._auth(p):
            return
        m = re.match(r"^/api/loops/(\w+)$", p)
        if m:
            return self._json({"ok": loops.delete(m.group(1))})
        m = re.match(r"^/api/flowpaths/(\w+)$", p)
        if m:
            flowpaths.delete(m.group(1))
            return self._json({"ok": True})
        self._json({"error": "not found"}, 404)

    # --- GitHub OAuth ------------------------------------------------------

    def _redirect_uri(self):
        return f"http://{self.headers.get('Host')}/auth/github/callback"

    def _github_start(self):
        state = uuid.uuid4().hex
        _oauth_states[state] = time.time() + 600
        url = github_oauth.authorize_url(state, self._redirect_uri())
        self.send_response(302)
        self.send_header("Location", url)
        self.end_headers()

    def _github_callback(self, q):
        state = (q.get("state") or [""])[0]
        code = (q.get("code") or [""])[0]
        if _oauth_states.pop(state, 0) < time.time():
            return self._json({"error": "invalid or expired state"}, 400)
        token = github_oauth.exchange_code(code, self._redirect_uri())
        github_oauth.save_token(token)
        self.send_response(302)
        self.send_header("Location", "/?github=connected")
        self.end_headers()

    # --- static SPA --------------------------------------------------------

    def _static(self, p):
        rel = "index.html" if p in ("/", "") else p.lstrip("/")
        root = os.path.realpath(DIST)
        full = os.path.realpath(os.path.join(root, rel))
        if not full.startswith(root + os.sep) or not os.path.isfile(full):
            full = os.path.join(root, "index.html")  # SPA fallback for client-side routes
            if not os.path.isfile(full):
                return self._json({"error": "not found"}, 404)
        import mimetypes
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        b = open(full, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)


if __name__ == "__main__":
    auth.bootstrap()
    scheduler.start_background()
    ThreadingHTTPServer((BIND, PORT), H).serve_forever()
