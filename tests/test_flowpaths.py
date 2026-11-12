import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "host"))
import flowpaths  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setattr(flowpaths, "FLOWPATHS_DIR", str(tmp_path))


def trig(mode, **kw):
    base = dict(now=1000, run_in_progress=False, upstream_output_id=None,
                last_consumed_upstream_id=None, last_run_at=None, sleep_secs=1800, is_first_link=False)
    base.update(kw)
    return flowpaths.should_trigger(mode, **base)


def test_once_first_link_runs_exactly_once():
    assert trig("once", is_first_link=True, last_run_at=None)
    assert not trig("once", is_first_link=True, last_run_at=50)


def test_once_chained_link_waits_for_new_upstream_output():
    assert not trig("once", upstream_output_id=None)  # nothing produced yet
    assert trig("once", upstream_output_id="abc", last_consumed_upstream_id=None)  # new -> go
    assert not trig("once", upstream_output_id="abc", last_consumed_upstream_id="abc")  # already handled


def test_never_triggers_while_a_run_is_in_progress():
    assert not trig("once", run_in_progress=True, upstream_output_id="abc")
    assert not trig("continuous", run_in_progress=True, is_first_link=True)


def test_continuous_first_link_follows_its_own_schedule():
    assert trig("continuous", is_first_link=True, last_run_at=None)  # never run -> go
    assert not trig("continuous", is_first_link=True, last_run_at=900, now=1000, sleep_secs=1800)  # too soon
    assert trig("continuous", is_first_link=True, last_run_at=900, now=3000, sleep_secs=1800)  # elapsed


def test_continuous_chained_link_still_gated_on_new_upstream_output():
    assert not trig("continuous", now=3000, last_run_at=900, sleep_secs=1800,
                     upstream_output_id="same", last_consumed_upstream_id="same")
    assert trig("continuous", now=3000, last_run_at=900, sleep_secs=1800,
                upstream_output_id="new", last_consumed_upstream_id="same")


def test_unknown_trigger_mode_rejected():
    with pytest.raises(ValueError):
        trig("bogus")


def test_output_ready_for_downstream():
    assert flowpaths.output_ready_for_downstream("x", None)
    assert flowpaths.output_ready_for_downstream("x", "y")
    assert not flowpaths.output_ready_for_downstream("x", "x")
    assert not flowpaths.output_ready_for_downstream(None, None)


def test_create_validates_links():
    with pytest.raises(ValueError):
        flowpaths.create({"name": "x", "links": []}, loop_exists=lambda lid: True)
    with pytest.raises(ValueError):
        flowpaths.create({"name": "x", "links": [{"loop_id": "nope", "trigger_mode": "once"}]},
                          loop_exists=lambda lid: False)
    with pytest.raises(ValueError):
        flowpaths.create({"name": "x", "links": [{"loop_id": "L1", "trigger_mode": "bogus"}]},
                          loop_exists=lambda lid: True)


def test_create_and_state_roundtrip():
    fp = flowpaths.create({"name": "x", "links": [{"loop_id": "L1", "trigger_mode": "once"}]},
                           loop_exists=lambda lid: True)
    assert fp["id"]
    flowpaths.save_state(fp["id"], {"0": {"last_output_id": "abc"}})
    assert flowpaths.load_state(fp["id"])["0"]["last_output_id"] == "abc"
