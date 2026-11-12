"""Host-side client for the internal host<->runner API. The runner's
address is user-set (see config.py / the first-run setup prompt), not
hardcoded, so this install can point at a runner anywhere reachable."""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402


def _request(method, path, body=None, timeout=15):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{config.get_runner_url()}{path}", data=data, method=method,
                                  headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": json.loads(e.read() or b"{}").get("error", str(e))}
    except urllib.error.URLError as e:
        return {"error": str(e)}


def start_run(loop_config, github_token, upstream_output=None):
    return _request("POST", "/runs", {
        "loop_config": {**loop_config, "terse": config.get("terse_mode", "on")}, "github_token": github_token, "upstream_output": upstream_output,
    })


def get_run(run_id):
    return _request("GET", f"/runs/{run_id}")


def stop_run(run_id):
    return _request("POST", f"/runs/{run_id}/stop")


def list_runs():
    return _request("GET", "/runs")


def set_claude_auth(body):
    return _request("POST", "/auth", body)


def improve(prompt, model):
    return _request("POST", "/improve", {"prompt": prompt, "model": model}, timeout=200)
