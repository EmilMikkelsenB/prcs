"""Generic producer/consumer executor: one function that runs any loop from
its config, replacing rotaria-dash's two fixed shell scripts (run.sh,
ideas.sh). allowedTools/disallowedTools below mirror those scripts exactly:
producer (ideas-like) may read/write files but not commit/push/open a PR;
consumer (implement-like) may do all of that except force-push or merge.
"""
import claude_auth
import hashlib
import json
import os
import re
import subprocess
import time

PR_URL_RE = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+")
LIMIT_RE = re.compile(r"hit your", re.IGNORECASE)

# Permission presets: read = look only | files = may write files but not commit/push | push = full PR workflow.
_NO_GIT_WRITE = "Bash(git push*),Bash(git commit*),Bash(gh pr create*),Bash(gh pr merge*),Bash(gh issue*)"
TOOLS = {
    "read": {"allowed": "Bash,Read,Glob,Grep,Agent", "disallowed": "Write,Edit,NotebookEdit," + _NO_GIT_WRITE},
    "files": {"allowed": "Bash,Read,Write,Glob,Grep,Agent", "disallowed": _NO_GIT_WRITE},
    "push": {"allowed": "Bash,Read,Write,Edit,Glob,Grep,Agent",
             "disallowed": "Bash(gh pr merge*),Bash(git push --force*),Bash(git push -f*)"},
}


MAX_HANDOFF = 30000  # chars of file content carried to the next link


def _build_prompt(loop_config, upstream_output):
    focus = loop_config.get("focus") or {}
    prompt = focus.get("text", "")
    if upstream_output:
        up = upstream_output
        if not up.get("queue"):
            prompt += "\n\nThe previous step in this flowpath just finished."
        if up.get("pr_url"):
            prompt += "\nIt opened: " + up["pr_url"]
        if up.get("commit"):
            prompt += "\nIt pushed commit " + up["commit"]
        if up.get("queue"):
            prompt += "\nHere is your next work item, from the '" + up["queue"] + "' queue (it comes from the dash, so it is NOT in your checkout). Work on exactly this one:"
            for path, text in up["files"].items():
                prompt += "\n\n=== %s ===\n%s" % (path, text)
        elif up.get("files"):
            # The workspace is reset before every run, so its files are gone: the content is passed here instead.
            prompt += "\nIt wrote these files (their full content is below; the files are NOT in your checkout):"
            for path, text in up["files"].items():
                prompt += "\n\n=== %s ===\n%s" % (path, text)
        elif not (up.get("pr_url") or up.get("commit")):
            prompt += "\nIts output: " + repr(up)
    return prompt


def _collect_files(workspace_dir, paths):
    files, left = {}, MAX_HANDOFF
    for p in paths:
        if left <= 0:
            break
        try:
            text = open(os.path.join(workspace_dir, p), encoding="utf-8").read(left)
        except (OSError, UnicodeDecodeError):
            continue  # binary or vanished
        files[p] = text
        left -= len(text)
    return files


def _head(workspace_dir):
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=workspace_dir, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def _new_files(workspace_dir):
    r = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=workspace_dir, capture_output=True, text=True)
    return sorted(line[3:] for line in r.stdout.splitlines() if line.startswith("??"))


DEFAULT_MODEL = "claude-sonnet-5-5"
NO_TOOLS = "Bash,Read,Write,Edit,Glob,Grep,Agent,WebFetch,WebSearch,NotebookEdit"
REVIEW_PROMPTS = {
    "push": "You are the reviewer. Review the work just done on this branch (git diff against the default branch, and the PR if one was opened) "
                "for bugs, missing tests and anything out of scope. Fix small problems directly, commit and push to the same branch, "
                "then reply with a short verdict: approve, or what still needs a human.",
    "files": "You are the reviewer. Review the files (new/changed files) for duplicates, vagueness and items too large for one PR. "
                "Tighten or delete weak items, then reply with a short verdict.",
}


def _claude(cmd, cwd, env, timeout_secs, cancel_event):
    """Run one claude call; returns (rc, combined output, seconds)."""
    start = time.time()
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = []
    while True:
        try:
            tail = proc.communicate(timeout=1)[0]
            if tail:
                out.append(tail)
            break
        except subprocess.TimeoutExpired:
            note = None
            if cancel_event is not None and cancel_event.is_set():
                note = "\n[stopped by user]"
            elif time.time() - start > timeout_secs:
                note = "\n[timed out]"
            if note:
                proc.kill()
                proc.communicate()
                out.append(note)
                break
    rc = proc.returncode if proc.returncode is not None else -1
    return rc, "".join(out), time.time() - start


def _parse(log):
    """--output-format json gives one object: answer text plus cost/token usage. Returns (text, stats|None)."""
    try:
        j = json.loads(log.strip())
        u = j.get("usage") or {}
        return (j.get("result") or log), {
            "cost_usd": j.get("total_cost_usd") or 0, "turns": j.get("num_turns") or 0,
            "input_tokens": u.get("input_tokens", 0), "output_tokens": u.get("output_tokens", 0),
            "cache_read_tokens": u.get("cache_read_input_tokens", 0),
            "cache_write_tokens": u.get("cache_creation_input_tokens", 0),
            "api_ms": j.get("duration_api_ms"), "session_id": j.get("session_id")}
    except (ValueError, AttributeError):
        return log, None  # timed out / killed / old CLI: keep the raw log, no stats


def _env(github_token):
    return {"GIT_TERMINAL_PROMPT": "0", "GITHUB_TOKEN": github_token, "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": os.path.expanduser("~"), **claude_auth.env()}


# Terse ("caveman") style, appended to the system prompt of every run. Output tokens are the expensive ones; this
# is ~120 tokens of prompt-cached input, versus ~1-1.5k per turn for the caveman plugin's hooks, with no install step.
# Idea from JuliusBrussee/caveman (Apache-2.0); the wording here is our own.
TERSE = {
    "on": ("Terse mode: output tokens cost money, so use as few as possible without losing meaning. Answer first. Short sentences; "
           "drop filler, pleasantries, hedging and recaps; no narration between tool calls. Keep exact: code, commands, file paths, "
           "error messages, numbers, units, and the words not/never/no/only. Commit messages and PR text: short and clear. "
           "Use full sentences for security warnings and irreversible actions. Files you create for other loops or people to read "
           "must still be complete and clear - never terse."),
}
TERSE["ultra"] = TERSE["on"] + " Go further: abbreviate common words (fn, cfg, impl, req, repo), use arrows for cause/effect, one line per point."


def _cmd(prompt, model, tools, terse=None):
    cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "json",
           "--allowedTools", tools["allowed"], "--disallowedTools", tools["disallowed"]]
    return cmd + ["--append-system-prompt", TERSE[terse]] if terse in TERSE else cmd


def _sum(a, b):
    if not a or not b:
        return a or b
    return {k: (a.get(k) or 0) + (b.get(k) or 0) if isinstance(a.get(k), (int, float)) else a.get(k) for k in a}


def ask(prompt, model=DEFAULT_MODEL, timeout_secs=180):
    """One-shot, tool-less question (used by the loop form's Improve button). Returns (text, stats)."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "json", "--disallowedTools", NO_TOOLS]
        rc, log, _ = _claude(cmd, d, _env(""), timeout_secs, None)
    text, stats = _parse(log)
    if rc != 0:
        raise RuntimeError(text[-500:] or "claude failed")
    return text, stats


def run(loop_config, workspace_dir, github_token, upstream_output=None, timeout_secs=3600, cancel_event=None):
    perm = loop_config.get("permissions") or ("push" if loop_config.get("role") == "consumer" else "files")
    tools = TOOLS[perm]
    model = loop_config.get("model") or DEFAULT_MODEL
    env = _env(github_token)

    before_head = _head(workspace_dir)
    rc, raw, secs = _claude(_cmd(_build_prompt(loop_config, upstream_output), model, tools, loop_config.get("terse")), workspace_dir, env, timeout_secs, cancel_event)
    log, stats = _parse(raw)

    review = loop_config.get("review") or {}
    if review.get("enabled") and rc == 0 and not LIMIT_RE.search(log) and not (cancel_event and cancel_event.is_set()):
        rprompt = review.get("prompt") or REVIEW_PROMPTS["push" if perm == "push" else "files"]
        rrc, rraw, rsecs = _claude(_cmd(rprompt, review.get("model") or model, tools, loop_config.get("terse")), workspace_dir, env, timeout_secs, cancel_event)
        rlog, rstats = _parse(rraw)
        log += "\n\n--- review (%s) ---\n%s" % (review.get("model") or model, rlog)
        stats, secs = _sum(stats, rstats), secs + rsecs
        if rrc != 0:
            rc = rrc

    limit_hit = bool(LIMIT_RE.search(log))
    pr_match = PR_URL_RE.search(log)
    after_head = _head(workspace_dir)
    new_files = _new_files(workspace_dir)

    output = {"pr_url": pr_match.group(0) if pr_match else None, "new_files": new_files,
              "commit": after_head if after_head != before_head else None,
              "files": _collect_files(workspace_dir, new_files)}
    output_id = (
        output["commit"]
        or (hashlib.sha256("\n".join(new_files).encode()).hexdigest()[:16] if new_files else None)
    )

    return {
        "status": "limit_hit" if limit_hit else ("done" if rc == 0 else "failed"),
        "rc": rc, "secs": round(secs, 1), "log_tail": log[-4000:],
        "output": output, "output_id": output_id, "stats": stats,
    }
