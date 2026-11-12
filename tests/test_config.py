import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "host"))
import config  # noqa: E402


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config, "CONFIG_FILE", str(tmp_path / "config.json"))


def test_auto_configure_adopts_default_when_probe_succeeds(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert config.try_auto_configure(lambda url: True) is True
    assert config.runner_url_configured() is True
    assert config.get_runner_url() == config.DEFAULT_RUNNER_URL


def test_auto_configure_leaves_unconfigured_when_probe_fails(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert config.try_auto_configure(lambda url: False) is False
    assert config.runner_url_configured() is False


def test_auto_configure_does_not_override_explicit_choice(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    config.set_runner_url("http://10.0.0.9:9000")
    assert config.try_auto_configure(lambda url: True) is True
    assert config.get_runner_url() == "http://10.0.0.9:9000"


def test_set_runner_url_rejects_bad_url(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    import pytest
    with pytest.raises(ValueError):
        config.set_runner_url("not a url")
