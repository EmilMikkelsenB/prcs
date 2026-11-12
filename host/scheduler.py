"""Background flowpath scheduler: a polling tick, same spirit as
rotaria-dash's loop-liveness polling, no new infra needed for v1."""
import threading
import time
import traceback

import flowpaths
import github_oauth
import loops
import runner_client

TICK_SECONDS = 10


def tick():
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
                    link_state["current_run_id"] = None
                    changed = True

            is_first = i == 0
            prev_state = state.get(str(i - 1), {}) if not is_first else {}
            upstream_output_id = prev_state.get("last_output_id")
            upstream_output = prev_state.get("last_output")

            loop_cfg = loops.get(link["loop_id"])
            if not loop_cfg:
                continue
            sleep_secs = loop_cfg["tuning"].get("FULL_SLEEP", 1800)

            if not run_in_progress and flowpaths.should_trigger(
                link["trigger_mode"], time.time(), run_in_progress, upstream_output_id,
                link_state.get("last_consumed_upstream_id"), link_state.get("last_run_at"),
                sleep_secs, is_first,
            ):
                token = github_oauth.load_token()
                if token:
                    resp = runner_client.start_run(loop_cfg, token, upstream_output)
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
            time.sleep(TICK_SECONDS)
    threading.Thread(target=loop, daemon=True).start()
