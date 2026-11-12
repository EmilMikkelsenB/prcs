"""Turns a rough idea into a loop config by asking Claude (via the runner), grounded in house guidance.
Put your own guidance (e.g. conventions from rotaria-dash) in the KB at notes/loop-guidance.md; it replaces the default."""
import json

import config
import kb
import runner_client

GUIDANCE_PATH = "notes/loop-guidance.md"
DEFAULT_GUIDANCE = """\
- A loop is one scheduled Claude Code job against one GitHub repo. It has:
  permissions: read (look only) | files (write files, never commit/push) | push (commit, push, open a PR; never merge or force-push)
  input: nothing (runs on a schedule or by hand), a queue (it takes the oldest item), or the previous flowpath step
  output: optionally a queue - every NEW file the run creates becomes an item in that queue for another loop to pick up
- Queues are per repo and named (e.g. backlog, bugs, ready-for-review). Typical shapes: a finder loop (files, writes "backlog")
  feeding an implementer loop (push, reads "backlog"); a triage loop that reads one queue and writes another.
- A loop must not read and write the same queue.
- Prompts must be concrete and self-contained: say what to look at, what counts as done, what to skip, and the output format.
- One small, reviewable unit of work per run (one item or one PR). If a loop writes queue items, tell it to write ONE FILE PER ITEM.
  Say what to do when there is nothing to do (exit quietly).
- A loop that reads a queue is given the item's text in its prompt; tell it to work on exactly that item.
- Add a review pass when changes are risky (a second model re-checks the work); skip it for cheap read-only loops.
- Models: haiku for cheap triage/finding, sonnet for most implementation, opus/fable for hard changes or the reviewer."""

MODELS = "claude-haiku-5-5 (cheap, fast), claude-sonnet-5-5 (default), claude-opus-5-5, claude-fable-5-2 (strongest)"

FORMAT = """Reply with ONLY a JSON object, no prose, with these keys:
{"name": short loop name (max 40 chars),
 "permissions": "read" or "files" or "push",
 "input_queue": queue name this loop should take work from, or "" for none,
 "output_queue": queue name this loop's new files should go to, or "" for none,
 "focus_text": the full improved prompt for the loop (plain text, may contain line breaks),
 "model": recommended worker model id,
 "review_enabled": true/false,
 "review_model": recommended reviewer model id (or "" to reuse the worker),
 "tips": [up to 4 short strings: what you changed or what the user should double-check]}"""


def guidance():
    try:
        return kb.read_file(GUIDANCE_PATH)["content"]
    except ValueError:
        return DEFAULT_GUIDANCE


def build_prompt(idea, repo=None, existing_queues=None):
    ctx = "".join(f"\n{k}: {v}" for k, v in (("Target repo", repo), ("Queues that already exist for it", ", ".join(existing_queues or []))) if v)
    return (f"You help configure autonomous Claude Code loops.\n\nHouse guidance:\n{guidance()}\n\nAvailable models: {MODELS}\n"
            f"{ctx}\n\nThe user's rough idea:\n<idea>\n{idea}\n</idea>\n\n"
            f"Rewrite it into a precise loop prompt following the guidance, and choose permissions, input/output queues, "
            f"models and whether a review pass is worthwhile.\n\n{FORMAT}")


def parse(text):
    try:
        out = json.loads(text[text.index("{"):text.rindex("}") + 1])
    except ValueError:
        raise ValueError("Claude's reply wasn't usable - try again")
    if out.get("permissions") not in ("read", "files", "push") or not out.get("focus_text"):
        raise ValueError("Claude's reply was missing permissions or a prompt - try again")
    return {"name": str(out.get("name") or "")[:40], "permissions": out["permissions"], "focus_text": str(out["focus_text"]),
            "input_queue": str(out.get("input_queue") or ""), "output_queue": str(out.get("output_queue") or ""),
            "model": str(out.get("model") or ""), "review_enabled": bool(out.get("review_enabled")),
            "review_model": str(out.get("review_model") or ""), "tips": [str(t) for t in (out.get("tips") or [])][:4]}


def improve(body):
    import queues
    idea = (body.get("idea") or "").strip()
    if not idea or len(idea) > 4000:
        raise ValueError("describe your idea in 1-4000 characters")
    repo = body.get("target_repo")
    existing = sorted({q["queue"] for q in queues.summary() if q["repo"] == repo})
    r = runner_client.improve(build_prompt(idea, repo, existing), config.get("improve_model", "claude-sonnet-5-5"))
    if "error" in r:
        raise ValueError(r["error"])
    return parse(r["text"])
