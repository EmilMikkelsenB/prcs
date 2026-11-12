"""Starting and finishing runs - one place, used by the scheduler, Run now and Retry."""
import traceback

import queues
import kb
import runner_client
import usage


def start(loop, token, upstream=None):
    """Start a run. A loop with a queue input claims the queue's oldest item, falling back to the previous
    flowpath step's output. With neither it raises ValueError instead of running with nothing to do."""
    claimed = None
    inp = loop.get("input") or {}
    if inp.get("type") == "queue":
        claimed = queues.claim(loop["target_repo"], inp["queue"])
        if claimed:
            upstream = {"queue": claimed["queue"], "files": {claimed["name"]: claimed["text"]}}
        elif not upstream:
            raise ValueError('The "%s" queue for %s is empty. Run a loop that writes to it first, or add an item '
                             "under queues/ in the knowledge base." % (inp["queue"], loop["target_repo"]))
    resp = runner_client.start_run(loop, token, upstream)
    if claimed:
        if "run_id" in resp:
            queues.record_claim(resp["run_id"], claimed)
        else:
            queues.release(claimed)
    return resp


def finished(loop, run_id, status):
    """A run ended: write the KB note, record usage, settle its queue item, and bank new files into its output queue."""
    out_queue = ((loop or {}).get("output") or {}).get("queue")
    for step in (
        lambda: kb.save_run(loop, run_id, status),
        lambda: usage.record(loop, run_id, status),
        lambda: queues.settle(run_id, status.get("status")),
        lambda: out_queue and status.get("status") == "done"
        and queues.add_items(loop["target_repo"], out_queue, (status.get("output") or {}).get("files")),
    ):
        try:
            step()
        except Exception:
            traceback.print_exc()  # bookkeeping must never break the scheduler
