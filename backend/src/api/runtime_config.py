"""Runtime configuration helpers shared by API routes.

Only expose values here that are safe for public frontend consumption.
Secrets, local filesystem paths, and private deployment details must stay
out of this module's response helpers.
"""
from __future__ import annotations

import os

APP_VERSION = "2.0.0"
LOCAL_FRONTEND_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)
PRODUCTION_ENVS = {"production", "prod", "docker"}
DEVELOPMENT_ENVS = {"", "development", "dev", "local"}


def backend_env() -> str:
    """Return the normalized backend environment name."""
    return os.environ.get("BACKEND_ENV", "development").strip().lower()


def is_production_like() -> bool:
    """Whether the process is running in a production-like mode."""
    return backend_env() in PRODUCTION_ENVS


def service_mode() -> str:
    """Coarse public service mode used by the frontend and smoke checks."""
    return "production" if is_production_like() else "development"


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def demo_alerts_enabled() -> bool:
    """Whether the synthetic demo alert endpoint should be exposed."""
    raw = os.environ.get("DEMO_ALERTS_ENABLED")
    if raw is not None:
        return _truthy(raw)
    return not is_production_like()


def public_runtime_config() -> dict[str, str | bool]:
    """Small safe config object returned by GET /system/config."""
    return {
        "backend_env": backend_env(),
        "service_mode": service_mode(),
        "demo_alerts_enabled": demo_alerts_enabled(),
        "version": APP_VERSION,
    }


def resolve_cors_origins() -> list[str]:
    """Resolve a safe CORS allow-list.

    Development defaults to the local Next.js dashboard origins. A wider
    wildcard can still be requested explicitly for local experiments, but
    production-like modes never return ["*"], even if CORS_ORIGINS is
    misconfigured that way.
    """
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if raw:
        if raw == "*":
            if is_production_like():
                return list(LOCAL_FRONTEND_ORIGINS)
            return ["*"]
        origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
        return origins or list(LOCAL_FRONTEND_ORIGINS)
    return list(LOCAL_FRONTEND_ORIGINS)
