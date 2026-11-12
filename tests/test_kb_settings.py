import io
import os
import sys
import tarfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "host"))
import config  # noqa: E402
import kb  # noqa: E402
import settings  # noqa: E402


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config, "CONFIG_FILE", str(tmp_path / "config.json"))
    config.set_many({"kb_dir": str(tmp_path / "kb")})
    monkeypatch.setattr(settings, "ENV_FILE", str(tmp_path / ".env"))
    return tmp_path


def test_note_roundtrip_and_search(env):
    kb.write_note("notes/a", "# Hello\nthe quick brown fox")
    assert kb.read_file("notes/a.md")["editable"]
    assert [r["path"] for r in kb.search("quic")] == ["notes/a.md"]
    kb.delete_note("notes/a.md")
    assert kb.search("fox") == []


def test_edit_on_disk_is_indexed(env):
    os.makedirs(env / "kb" / "repos" / "x")
    (env / "kb" / "repos" / "x" / "r.md").write_text("zebra")
    r = kb.search("zebra")
    assert r[0]["path"] == "repos/x/r.md" and not r[0]["editable"]


@pytest.mark.parametrize("bad", ["../x.md", "notes/../../x.md", ".index.db", "/etc/passwd"])
def test_paths_cannot_escape(env, bad):
    with pytest.raises(ValueError):
        kb.read_file(bad)


def test_site_only_writes_notes(env):
    with pytest.raises(ValueError):
        kb.write_note("repos/x/a.md", "no")
    with pytest.raises(ValueError):
        kb.delete_note("repos/x/a.md")


def test_extract_filters(env, tmp_path):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in [("o-r-sha/README.md", b"hi"), ("o-r-sha/a.py", b"x"), ("o-r-sha/../evil.md", b"x"),
                           ("o-r-sha/.hidden/n.md", b"x"), ("o-r-sha/docs/g.md", b"y")]:
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
    dest = tmp_path / "out"
    dest.mkdir()
    assert kb._extract(buf.getvalue(), str(dest), {".md"}) == 2
    assert sorted(os.path.relpath(os.path.join(d, f), dest).replace(os.sep, "/")
                  for d, _, fs in os.walk(dest) for f in fs) == ["README.md", "docs/g.md"]


def test_env_write_preserves_and_quotes(env):
    (env / ".env").write_text("# note\nADMIN_USER=a\nOTHER=1\n")
    settings.write_env({"ADMIN_USER": "bob", "ADMIN_PASSWORD": "p w#1"})
    assert (env / ".env").read_text() == "# note\nADMIN_USER=bob\nOTHER=1\nADMIN_PASSWORD='p w#1'\n"
    assert settings.read_env()["ADMIN_PASSWORD"] == "p w#1"


def test_save_validates_and_flags_restart(env):
    (env / ".env").write_text("ADMIN_USER=a\nADMIN_PASSWORD=secret\n")
    with pytest.raises(ValueError):
        settings.save({"runtime": {"scheduler_tick": 1}})
    out = settings.save({"runtime": {"scheduler_tick": 30}, "env": {"ADMIN_USER": "a", "ADMIN_PASSWORD": "", "KB_PATH": "D:/kb"}})
    assert config.get("scheduler_tick") == 30
    assert out == {"restart_needed": False, "compose_needed": True}
    assert settings.read_env()["ADMIN_PASSWORD"] == "secret"
    assert settings.save({"env": {"ADMIN_USER": "z"}})["restart_needed"] is True
