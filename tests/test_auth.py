import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "host"))
import auth  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(auth, "USERS_FILE", str(tmp_path / "users.json"))
    monkeypatch.setattr(auth, "SECRET_FILE", str(tmp_path / "session_secret"))


def test_password_hash_roundtrip():
    h = auth.hash_password("correct horse")
    assert auth.verify_password("correct horse", h)
    assert not auth.verify_password("wrong", h)


def test_bootstrap_creates_single_user(monkeypatch):
    monkeypatch.setenv("ADMIN_USER", "owner")
    monkeypatch.setenv("ADMIN_PASSWORD", "swordfish")
    auth.bootstrap()
    assert auth.check_login("owner", "swordfish")
    assert not auth.check_login("owner", "wrong")
    assert not auth.check_login("nobody", "swordfish")


def test_bootstrap_is_idempotent(monkeypatch):
    monkeypatch.setenv("ADMIN_USER", "owner")
    monkeypatch.setenv("ADMIN_PASSWORD", "first")
    auth.bootstrap()
    monkeypatch.setenv("ADMIN_PASSWORD", "second")
    auth.bootstrap()  # must not overwrite the existing account
    assert auth.check_login("owner", "first")


def test_session_roundtrip_and_tamper_detection():
    token = auth.make_session("owner")
    assert auth.verify_session(token) == "owner"
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    assert auth.verify_session(tampered) is None
    assert auth.verify_session("") is None
    assert auth.verify_session("garbage") is None


def test_expired_session_rejected(monkeypatch):
    monkeypatch.setattr(auth, "SESSION_MAX_AGE", -1)
    token = auth.make_session("owner")
    assert auth.verify_session(token) is None
