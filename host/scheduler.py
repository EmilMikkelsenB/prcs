"""Background flowpath scheduler: a polling tick, same spirit as
rotaria-dash's loop-liveness polling, no new infra needed for v1."""
import threading
import time
import traceback

import config
import flowpaths
import github_oauth
import runs
import loops
import manual
import queues
import runner_client

def finish_manual():
    for run_id, loop_id in manual.pending().items():
        status = runner_client.get_run(run_id)
        if status.get("status") in ("done", "failed", "limit_hit") or "error" in status:
            loop = loops.get(loop_id)
            if "error" in status:  # runner forgot it (restart): nothing to record, but hand a claimed item back
                queues.settle(run_id, "failed")
            else:
                runs.finished(loop, run_id, status)
            if status.get("status") != "done" and loop:
                manual.set_cooldown(loop_id, time.time() + loop["tuning"].get("RETRY_SLEEP", 900))
            manual.remove(run_id)


def watch_queues():
    """Loops outside any flowpath whose input is a queue with "auto" on start as soon as an item is waiting."""
    token = github_oauth.load_token()
    if not token:
        return
    in_flowpath = {l["loop_id"] for fp in flowpaths.list_flowpaths() for l in fp["links"]}
    busy = set(manual.pending().values())
    for loop in loops.list_loops():
        inp = loop["input"]
        if (inp.get("type") != "queue" or not inp.get("auto") or loop["id"] in in_flowpath or loop["id"] in busy
                or manual.cooldown_until(loop["id"]) > time.time() or not queues.pending(loop["target_repo"], inp["queue"])):
            continue
        try:
            r = runs.start(loop, token)
        except ValueError:
            continue
        if "run_id" in r:
            manual.add(r["run_id"], loop["id"])


def tick():
    finish_manual()
    watch_queues()
    for fp in flowpaths.list_flowpaths():
        state = flowpaths.load_state(fp["id"])
        changed = False
        for i, link in enumerate(fp["links"]):
            link_state = state.get(str(i), {})
            run_id = link_state.get("current_run_id")
            run_in_progress = False
            if run_id:
                status = runner_client.get_run(run_id)
                if status.get("status") == "running":
                    run_in_progress = True
                elif status.get("status") in ("done", "failed", "limit_hit"):
                    link_state["last_output_id"] = status.get("output_id")
                    link_state["last_output"] = status.get("output")
                    link_state["last_run_at"] = time.time()
                    link_state["last_status"] = status.get("status")
                    link_state["current_run_id"] = None
                    changed = True
                    runs.finished(loops.get(link["loop_id"]), run_id, status)

            is_first = i == 0
            prev_state = state.get(str(i - 1), {}) if not is_first else {}
            upstream_output_id = prev_state.get("last_output_id")
            upstream_output = prev_state.get("last_output")

            loop_cfg = loops.get(link["loop_id"])
            if not loop_cfg:
                continue
            sleep_secs = loop_cfg["tuning"].get("FULL_SLEEP", 1800)

            inp = loop_cfg["input"]
            if inp.get("type") == "queue":  # driven by the queue, not by upstream output or a schedule
                retry_ok = link_state.get("last_status") in (None, "done") or (
                    time.time() - link_state.get("last_run_at", 0) >= loop_cfg["tuning"].get("RETRY_SLEEP", 900))
                go = not run_in_progress and retry_ok and bool(queues.pending(loop_cfg["target_repo"], inp["queue"]))
            else:
                go = not run_in_progress and flowpaths.should_trigger(
                    link["trigger_mode"], time.time(), run_in_progress, upstream_output_id,
                    link_state.get("last_consumed_upstream_id"), link_state.get("last_run_at"),
                    sleep_secs, is_first,
                )
            if go:
                token = github_oauth.load_token()
                if token:
                    try:
                        resp = runs.start(loop_cfg, token, upstream_output)
                    except ValueError:
                        resp = {}  # consumer with an empty backlog: wait, try again next tick
                    if "run_id" in resp:
                        link_state["current_run_id"] = resp["run_id"]
                        link_state["last_consumed_upstream_id"] = upstream_output_id
                        changed = True

            state[str(i)] = link_state
        if changed:
            flowpaths.save_state(fp["id"], state)


def start_background():
    def loop():
        while True:
            try:
                tick()
            except Exception:
                traceback.print_exc()
            time.sleep(config.get("scheduler_tick", 10))
    threading.Thread(target=loop, daemon=True).start()
