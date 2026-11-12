import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "host"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runner"))
import config  # noqa: E402
import queues  # noqa: E402
import run_loop  # noqa: E402
import runs  # noqa: E402


@pytest.fixture(autouse=True)
def iso(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config, "CONFIG_FILE", str(tmp_path / "config.json"))
    config.set_many({"kb_dir": str(tmp_path / "kb")})


def test_claim_settle_roundtrip():
    queues.add_items("a/b", "q", {"x/idea.md": "do thing"})
    c = queues.claim("a/b", "q")
    assert c["text"] == "do thing" and queues.pending("a/b", "q") == []
    queues.record_claim("r1", c)
    queues.settle("r1", "failed")  # failure returns the item
    assert len(queues.pending("a/b", "q")) == 1
    queues.record_claim("r2", queues.claim("a/b", "q"))
    queues.settle("r2", "done")
    assert queues.claim("a/b", "q") is None
    assert queues.summary() == [{"repo": "a/b", "queue": "q", "pending": 0, "in_progress": 0, "done": 1}]


def test_queues_are_separate_per_repo_and_name():
    queues.add_items("a/b", "q1", {"i.md": "1"})
    assert queues.claim("a/b", "q2") is None and queues.claim("c/d", "q1") is None


def test_old_backlog_folder_migrates(tmp_path):
    old = tmp_path / "kb" / "backlog" / "a__b"
    old.mkdir(parents=True)
    (old / "i.md").write_text("old item")
    assert queues.pending("a/b", "backlog") == ["i.md"]


def test_bad_queue_name_rejected():
    with pytest.raises(ValueError):
        queues.add_items("a/b", "../x", {"i.md": "1"})


def test_loop_with_empty_input_queue_refuses(monkeypatch):
    sent = []
    monkeypatch.setattr(runs.runner_client, "start_run", lambda *a: sent.append(a) or {"run_id": "r"})
    loop = {"target_repo": "a/b", "input": {"type": "queue", "queue": "q"}}
    with pytest.raises(ValueError, match="empty"):
        runs.start(loop, "tok")
    assert sent == []
    queues.add_items("a/b", "q", {"i.md": "item"})
    runs.start(loop, "tok")
    assert sent[0][2]["queue"] == "q" and "item" in sent[0][2]["files"].values()


def test_output_queue_filled_on_success_only():
    loop = {"target_repo": "a/b", "name": "P", "output": {"queue": "out"}}
    runs.finished(loop, "r1", {"status": "failed", "output": {"files": {"n.md": "x"}}})
    assert queues.pending("a/b", "out") == []
    runs.finished(loop, "r2", {"status": "done", "output": {"files": {"n.md": "idea"}}})
    assert len(queues.pending("a/b", "out")) == 1


def test_queue_prompt():
    p = run_loop._build_prompt({"focus": {"text": "Implement"}}, {"queue": "q", "files": {"a.md": "BODY"}})
    assert "BODY" in p and "just finished" not in p


def test_terse_flag_added_only_when_set():
    tools = run_loop.TOOLS["files"]
    assert "--append-system-prompt" not in run_loop._cmd("p", "m", tools)
    assert "--append-system-prompt" not in run_loop._cmd("p", "m", tools, "off")
    cmd = run_loop._cmd("p", "m", tools, "ultra")
    assert cmd[cmd.index("--append-system-prompt") + 1] == run_loop.TERSE["ultra"]


def test_terse_setting_validates():
    import settings
    assert settings._coerce("terse_mode", "ultra") == "ultra"
    with pytest.raises(ValueError):
        settings._coerce("terse_mode", "loud")
