import os
import pytest
from tracechain.config import TraceChainConfig


def test_defaults():
    cfg = TraceChainConfig()
    assert cfg.base_url == "http://localhost:8000"
    assert cfg.enabled is True
    assert cfg.timeout == 5.0


def test_env_base_url(monkeypatch):
    monkeypatch.setenv("TRACECHAIN_BACKEND_URL", "http://myserver:9000/")
    cfg = TraceChainConfig()
    assert cfg.base_url == "http://myserver:9000"  # trailing slash stripped


def test_env_disabled(monkeypatch):
    monkeypatch.setenv("TRACECHAIN_ENABLED", "false")
    cfg = TraceChainConfig()
    assert cfg.enabled is False


def test_env_disabled_case_insensitive(monkeypatch):
    monkeypatch.setenv("TRACECHAIN_ENABLED", "FALSE")
    cfg = TraceChainConfig()
    assert cfg.enabled is False


def test_env_timeout(monkeypatch):
    monkeypatch.setenv("TRACECHAIN_TIMEOUT", "15")
    cfg = TraceChainConfig()
    assert cfg.timeout == 15.0


def test_explicit_override():
    cfg = TraceChainConfig(base_url="http://custom:1234", enabled=False, timeout=2.0)
    assert cfg.base_url == "http://custom:1234"
    assert cfg.enabled is False
    assert cfg.timeout == 2.0


def test_trailing_slash_stripped(monkeypatch):
    monkeypatch.setenv("TRACECHAIN_BACKEND_URL", "http://api.example.com/")
    cfg = TraceChainConfig()
    assert not cfg.base_url.endswith("/")
