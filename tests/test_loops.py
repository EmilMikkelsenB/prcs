import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "host"))
import loops  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setattr(loops, "LOOPS_DIR", str(tmp_path))


def test_create_rejects_bad_role():
    with pytest.raises(ValueError):
        loops.create({"name": "x", "role": "bogus", "target_repo": "a/b", "focus": {"text": "do x"}})


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


def test_templates_have_valid_role_and_focus():
    for t in loops.templates():
        assert t["role"] in loops.ROLES
        assert t["focus_text"]
