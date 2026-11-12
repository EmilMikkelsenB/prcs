"""Claude credentials entered from the dash site, kept in the persisted ~/.claude volume.
`oauth_token` comes from `claude setup-token` (uses a Claude subscription); `api_key` is an Anthropic API key.
Either way it reaches the CLI as an env var, so no interactive `claude login` is needed."""
import json
import os

ENV_NAMES = {"oauth_token": "CLAUDE_CODE_OAUTH_TOKEN", "api_key": "ANTHROPIC_API_KEY"}


def _file():
    return os.path.join(os.path.expanduser("~"), ".claude", "dash_auth.json")


def save(kind, value):
    value = (value or "").strip()
    if kind not in ENV_NAMES or not value or any(c.isspace() for c in value):
        raise ValueError("pick a type and paste a single token or key")
    os.makedirs(os.path.dirname(_file()), exist_ok=True)
    fd = os.open(_file(), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"kind": kind, "value": value}, f)


def clear():
    if os.path.isfile(_file()):
        os.remove(_file())


def _load():
    try:
        return json.load(open(_file()))
    except (OSError, ValueError):
        return None


def env():
    a = _load()
    return {ENV_NAMES[a["kind"]]: a["value"]} if a and a.get("kind") in ENV_NAMES else {}


def status():
    a = _load()
    if a:
        return {"logged_in": True, "source": a["kind"]}
    if os.path.isfile(os.path.join(os.path.expanduser("~"), ".claude", ".credentials.json")):
        return {"logged_in": True, "source": "login"}
    return {"logged_in": False, "source": None}
