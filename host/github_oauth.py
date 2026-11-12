"""GitHub OAuth App integration: connect flow, token storage, repo listing.

One-time setup (README): register a GitHub OAuth App in your own GitHub
settings (Settings -> Developer settings -> OAuth Apps), set its callback
URL to this host's /auth/github/callback, and put the client id/secret in
GITHUB_OAUTH_CLIENT_ID / GITHUB_OAUTH_CLIENT_SECRET.

The resulting user token is used both to list repos for the target-repo
picker and, per run, handed to the runner container as GITHUB_TOKEN (for
`git push` over HTTPS and `gh pr create`).
"""
import hashlib
import hmac
import json
import os
import urllib.parse
import urllib.request

import auth

DATA_DIR = os.environ.get("DASH_DATA", "/app/data")
TOKEN_FILE = os.path.join(DATA_DIR, "github_token.enc")
CLIENT_ID = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET", "")
AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
API_BASE = "https://api.github.com"
USER_AGENT = "wellqon-cadence"


def authorize_url(state, redirect_uri):
    qs = urllib.parse.urlencode({
        "client_id": CLIENT_ID, "redirect_uri": redirect_uri,
        "scope": "repo", "state": state,
    })
    return f"{AUTHORIZE_URL}?{qs}"


def exchange_code(code, redirect_uri):
    body = urllib.parse.urlencode({
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "code": code, "redirect_uri": redirect_uri,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    if "access_token" not in data:
        raise ValueError(data.get("error_description", "GitHub did not return a token"))
    return data["access_token"]


def list_repos(token):
    req = urllib.request.Request(
        f"{API_BASE}/user/repos?per_page=100&sort=updated",
        headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    return [{"full_name": r["full_name"], "private": r["private"]} for r in data]


# shortcut: hand-rolled HMAC-SHA256 keystream cipher, not a peer-reviewed AEAD.
# Fine for a self-hosted single-user token at rest behind the session secret;
# swap for cryptography.Fernet if this ever stores more than one secret.
def _keystream(key, nonce, length):
    out, counter = b"", 0
    while len(out) < length:
        out += hmac.new(key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        counter += 1
    return out[:length]


def _xor(data, key):
    nonce = os.urandom(16)
    return nonce + bytes(a ^ b for a, b in zip(data, _keystream(key, nonce, len(data))))


def _unxor(blob, key):
    nonce, enc = blob[:16], blob[16:]
    return bytes(a ^ b for a, b in zip(enc, _keystream(key, nonce, len(enc))))


def save_token(token):
    os.makedirs(DATA_DIR, exist_ok=True)
    blob = _xor(token.encode(), auth._secret())
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(blob)


def load_token():
    try:
        blob = open(TOKEN_FILE, "rb").read()
    except OSError:
        return None
    return _unxor(blob, auth._secret()).decode()


def connected():
    return load_token() is not None
