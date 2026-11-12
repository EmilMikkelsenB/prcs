"""Generic producer/consumer executor: one function that runs any loop from
its config, replacing rotaria-dash's two fixed shell scripts (run.sh,
ideas.sh). allowedTools/disallowedTools below mirror those scripts exactly:
producer (ideas-like) may read/write files but not commit/push/open a PR;
consumer (implement-like) may do all of that except force-push or merge.
"""
import hashlib
import json
import re
import subprocess
import time

PR_URL_RE = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+")
LIMIT_RE = re.compile(r"hit your", re.IGNORECASE)

TOOLS = {
    "producer": {
        "allowed": "Bash,Read,Write,Glob,Grep,Agent",
        "disallowed": "Bash(git push*),Bash(git commit*),Bash(gh pr create*),Bash(gh pr merge*),Bash(gh issue*)",
    },
    "consumer": {
        "allowed": "Bash,Read,Write,Edit,Glob,Grep,Agent",
        "disallowed": "Bash(gh pr merge*),Bash(git push --force*),Bash(git push -f*)",
    },
}


def _build_prompt(loop_config, upstream_output):
    focus = loop_config.get("focus") or {}
    prompt = focus.get("text", "")
    if upstream_output:
        prompt += (
            "\n\nThe previous step in this flowpath just finished. Its output:\n"
            + repr(upstream_output)
        )
    return prompt


def _head(workspace_dir):
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=workspace_dir, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def _new_files(workspace_dir):
    r = subprocess.run(["git", "status", "--porcelain"], cwd=workspace_dir, capture_output=True, text=True)
    return sorted(line[3:] for line in r.stdout.splitlines() if line.startswith("??"))


def run(loop_config, workspace_dir, github_token, upstream_output=None, timeout_secs=3600, cancel_event=None):
    role = loop_config["role"]
    tools = TOOLS[role]
    prompt = _build_prompt(loop_config, upstream_output)
    model = loop_config.get("model", "claude-sonnet-5-5")
    cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "json",
           "--allowedTools", tools["allowed"], "--disallowedTools", tools["disallowed"]]
    env = {"GIT_TERMINAL_PROMPT": "0", "GITHUB_TOKEN": github_token, "PATH": "/usr/local/bin:/usr/bin:/bin"}

    before_head = _head(workspace_dir)
    start = time.time()
    proc = subprocess.Popen(cmd, cwd=workspace_dir, env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True)
    out = []
    while True:
        try:
            tail = proc.communicate(timeout=1)[0]
            if tail:
                out.append(tail)
            break
        except subprocess.TimeoutExpired:
            if cancel_event is not None and cancel_event.is_set():
                proc.kill()
                proc.communicate()
                out.append("\n[stopped by user]")
                break
            if time.time() - start > timeout_secs:
                proc.kill()
                proc.communicate()
                out.append("\n[timed out]")
                break
    rc, log = (proc.returncode if proc.returncode is not None else -1), "".join(out)
    secs = time.time() - start
    stats = None
    try:  # --output-format json: one object with the answer text plus cost/token usage
        j = json.loads(log.strip())
        u = j.get("usage") or {}
        stats = {"cost_usd": j.get("total_cost_usd") or 0, "turns": j.get("num_turns") or 0,
                 "input_tokens": u.get("input_tokens", 0), "output_tokens": u.get("output_tokens", 0),
                 "cache_read_tokens": u.get("cache_read_input_tokens", 0),
                 "cache_write_tokens": u.get("cache_creation_input_tokens", 0),
                 "api_ms": j.get("duration_api_ms"), "session_id": j.get("session_id")}
        log = j.get("result") or log
    except (ValueError, AttributeError):
        pass  # timed out / killed / old CLI: keep the raw log, no stats

    limit_hit = bool(LIMIT_RE.search(log))
    pr_match = PR_URL_RE.search(log)
    after_head = _head(workspace_dir)
    new_files = _new_files(workspace_dir)

    output = {"pr_url": pr_match.group(0) if pr_match else None, "new_files": new_files,
              "commit": after_head if after_head != before_head else None}
    output_id = (
        output["commit"]
        or (hashlib.sha256("\n".join(new_files).encode()).hexdigest()[:16] if new_files else None)
    )

    return {
        "status": "limit_hit" if limit_hit else ("done" if rc == 0 else "failed"),
        "rc": rc, "secs": round(secs, 1), "log_tail": log[-4000:],
        "output": output, "output_id": output_id, "stats": stats,
    }
