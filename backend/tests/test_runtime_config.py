"""Tests for env-driven runtime configuration helpers."""
from __future__ import annotations

from src.api import runtime_config


def test_cors_default_allows_local_frontend(monkeypatch):
    monkeypatch.delenv("BACKEND_ENV", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert runtime_config.resolve_cors_origins() == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_production_never_uses_wildcard_cors(monkeypatch):
    monkeypatch.setenv("BACKEND_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    assert runtime_config.resolve_cors_origins() == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_development_can_explicitly_request_wildcard_cors(monkeypatch):
    monkeypatch.setenv("BACKEND_ENV", "development")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    assert runtime_config.resolve_cors_origins() == ["*"]
