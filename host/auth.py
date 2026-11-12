"""Single-user login: password hash + signed session cookie.

Replaces rotaria-dash's shared X-Dash-Secret header. One user account,
bootstrapped from ADMIN_USER/ADMIN_PASSWORD env vars on first boot.
"""
import hashlib
import hmac
import json
import os
import time

DATA_DIR = os.environ.get("DASH_DATA", "/app/data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
SECRET_FILE = os.environ.get("SESSION_SECRET_FILE", os.path.join(DATA_DIR, "session_secret"))
SESSION_MAX_AGE = 30 * 86400
PBKDF2_ITERS = 200_000


def _secret():
    try:
        return open(SECRET_FILE, "rb").read()
    except OSError:
        os.makedirs(os.path.dirname(SECRET_FILE), exist_ok=True)
        key = os.urandom(32)
        fd = os.open(SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(key)
        return key


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERS)
    return f"pbkdf2_sha256${PBKDF2_ITERS}${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        algo, iters, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
    return hmac.compare_digest(digest.hex(), digest_hex)


def _load_users():
    try:
        return json.load(open(USERS_FILE))
    except (OSError, ValueError):
        return None


def bootstrap():
    """Create the single user account from env vars if none exists yet."""
    if _load_users() is not None:
        return
    user = os.environ.get("ADMIN_USER")
    pw = os.environ.get("ADMIN_PASSWORD")
    if not user or not pw:
        return  # no account yet; /auth/login will fail until one is bootstrapped
    os.makedirs(DATA_DIR, exist_ok=True)
    json.dump({"username": user, "password_hash": hash_password(pw)}, open(USERS_FILE, "w"))


def check_login(username, password):
    users = _load_users()
    if not users or users["username"] != username:
        return False
    return verify_password(password, users["password_hash"])


def make_session(username):
    expiry = int(time.time()) + SESSION_MAX_AGE
    payload = f"{username}.{expiry}"
    sig = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_session(token):
    if not token:
        return None
    try:
        username, expiry_s, sig = token.split(".")
        expiry = int(expiry_s)
    except ValueError:
        return None
    payload = f"{username}.{expiry_s}"
    want = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, want):
        return None
    if expiry < time.time():
        return None
    return username
