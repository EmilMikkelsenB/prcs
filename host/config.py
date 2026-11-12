"""Host-side setup config: where the runner lives. Stored as a portable JSON
file (same style as loops/flowpaths), not baked into the image, so it
survives moving this install between machines without rebuilding."""
import json
import os
import re

DATA_DIR = os.environ.get("DASH_DATA", "/app/data")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

DEFAULT_RUNNER_URL = os.environ.get("RUNNER_URL", "http://172.28.0.10:8089")
_URL_RE = re.compile(r"^https?://[^\s/]+$")


def _load():
    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def _save(cfg):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f)


def get_runner_url():
    return _load().get("runner_url") or DEFAULT_RUNNER_URL


def runner_url_configured():
    return "runner_url" in _load()


def set_runner_url(url):
    url = (url or "").strip().rstrip("/")
    if not _URL_RE.match(url):
        raise ValueError("runner_url must look like http://host:port")
    cfg = _load()
    cfg["runner_url"] = url
    _save(cfg)
    return url


def try_auto_configure(probe_fn):
    """If not yet configured, silently adopt the default runner URL when
    `probe_fn(url) -> bool` says it's reachable — skips the setup prompt for
    the common case (standard compose, default static IP). `probe_fn` is
    injected so this stays testable without real network access."""
    if runner_url_configured():
        return True
    if probe_fn(DEFAULT_RUNNER_URL):
        set_runner_url(DEFAULT_RUNNER_URL)
        return True
    return False
