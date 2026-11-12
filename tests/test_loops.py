import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "host"))
import loops  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setattr(loops, "LOOPS_DIR", str(tmp_path))


def test_create_rejects_bad_permissions():
    with pytest.raises(ValueError):
        loops.create({"name": "x", "permissions": "bogus", "target_repo": "a/b", "focus": {"text": "do x"}})


def test_create_rejects_bad_target_repo():
    with pytest.raises(ValueError):
        loops.create({"name": "x", "role": "consumer", "target_repo": "not-a-repo", "focus": {"text": "y"}})


def test_create_fills_tuning_defaults():
    cfg = loops.create({"name": "Idea gen", "role": "producer", "target_repo": "acme/widgets", "focus": {"text": "find bugs"}})
    assert cfg["tuning"]["MAX_RUNS"] == 25
    assert loops.get(cfg["id"])["id"] == cfg["id"]


def test_tuning_out_of_bounds_rejected():
    with pytest.raises(ValueError):
        loops.create({"name": "x", "role": "consumer", "target_repo": "a/b", "focus": {"text": "y"},
                      "tuning": {"MAX_RUNS": 99999}})


def test_custom_focus_requires_text():
    with pytest.raises(ValueError):
        loops.create({"name": "x", "role": "consumer", "target_repo": "a/b", "focus": {"id": "custom", "text": ""}})


def test_update_and_delete_roundtrip():
    cfg = loops.create({"name": "x", "role": "consumer", "target_repo": "a/b", "focus": {"text": "y"}})
    updated = loops.update(cfg["id"], {"name": "renamed"})
    assert updated["name"] == "renamed"
    assert loops.delete(cfg["id"]) is True
    assert loops.get(cfg["id"]) is None


def test_update_unknown_loop_rejected():
    with pytest.raises(ValueError):
        loops.update("does-not-exist", {"name": "y"})


def test_templates_have_valid_config():
    for t in loops.TEMPLATES:
        assert t["permissions"] in loops.PERMISSIONS and t["focus_text"]
        loops._validate({**t, "name": t["name"], "target_repo": "a/b", "focus": {"text": t["focus_text"]}})


def test_old_role_loops_are_converted():
    prod = loops.create({"name": "p", "role": "producer", "target_repo": "a/b", "focus": {"text": "y"}})
    assert prod["permissions"] == "files" and prod["output"] == {"queue": "backlog"} and prod["input"] == {"type": "none"}
    cons = loops.create({"name": "c", "role": "consumer", "target_repo": "a/b", "focus": {"text": "y"}})
    assert cons["permissions"] == "push" and cons["input"]["queue"] == "backlog" and "role" not in cons


def test_queue_validation():
    base = {"name": "x", "permissions": "files", "target_repo": "a/b", "focus": {"text": "y"}}
    with pytest.raises(ValueError, match="itself"):
        loops.create({**base, "input": {"type": "queue", "queue": "q"}, "output": {"queue": "q"}})
    with pytest.raises(ValueError, match="queue names"):
        loops.create({**base, "input": {"type": "none"}, "output": {"queue": "bad name!"}})
