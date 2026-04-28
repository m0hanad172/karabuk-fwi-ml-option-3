"""Tests for the FastAPI backend endpoints (offline-safe)."""
import pytest

from fastapi.testclient import TestClient

from src.api.db.database import save_run
from src.api.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def _make_run(**overrides) -> dict:
    run = {
        "run_id": "test123abc",
        "run_type": "manual",
        "run_timestamp": "2025-07-15T11:00:00",
        "target_date": "2025-07-15",
        "predicted_fwi": 32.5,
        "high_risk_probability": 0.45,
        "high_risk_flag": 1,
        "decision_reason": "Grey-zone rescue",
        "drone_state": {"active_alert_window": False},
        "raw_inputs": {"temperature": 35.0},
        "feature_values": {"temperature": 35.0},
        "validation": {"is_valid": True},
        "thresholds": {"high_threshold": 35},
    }
    run.update(overrides)
    return run


@pytest.fixture
def seed_run():
    """Insert a sample OPERATIONAL run for history/detail tests."""
    run = _make_run()
    save_run(run)
    return run


class TestRootEndpoint:
    def test_root(self, client):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["architecture"].startswith("Option 3")


class TestSystemEndpoints:
    def test_health(self, client):
        r = client.get("/system/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("healthy", "degraded")
        assert "stage1_model_loaded" in data
        assert "stage2_model_loaded" in data
        assert "database_ok" in data

    def test_model_info(self, client):
        r = client.get("/system/model")
        assert r.status_code == 200
        data = r.json()
        assert data["n_training_features"] == 34
        assert "predicted_fwi" in data["stage2_input_features"]
        assert data["thresholds"]["high_threshold"] == 35

    def test_scheduler_status(self, client):
        r = client.get("/system/scheduler")
        assert r.status_code == 200

    def test_public_runtime_config_is_safe(self, client, monkeypatch):
        monkeypatch.setenv("BACKEND_ENV", "production")
        monkeypatch.delenv("DEMO_ALERTS_ENABLED", raising=False)
        r = client.get("/system/config")
        assert r.status_code == 200
        data = r.json()
        assert data == {
            "backend_env": "production",
            "service_mode": "production",
            "demo_alerts_enabled": False,
            "version": "2.0.0",
        }
        assert "KARABUK_DB_PATH" not in data
        assert "CORS_ORIGINS" not in data


class TestHistoryEndpoints:
    def test_run_history_empty(self, client):
        r = client.get("/history/runs")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_run_history_with_data(self, client, seed_run):
        r = client.get("/history/runs")
        assert r.status_code == 200
        runs = r.json()
        assert any(run["run_id"] == "test123abc" for run in runs)

    def test_run_detail(self, client, seed_run):
        r = client.get("/history/runs/test123abc")
        assert r.status_code == 200
        data = r.json()
        assert data["run_id"] == "test123abc"
        assert data["predicted_fwi"] == 32.5

    def test_run_detail_not_found(self, client):
        r = client.get("/history/runs/nonexistent")
        assert r.status_code == 404


class TestRiskEndpoints:
    def test_latest_no_data(self, client):
        """With an empty DB, /risk/latest must 404 (no operational runs)."""
        r = client.get("/risk/latest")
        assert r.status_code == 404

    def test_latest_with_operational_run(self, client, seed_run):
        r = client.get("/risk/latest")
        assert r.status_code == 200
        data = r.json()
        assert data["run_id"] == "test123abc"
        assert data["run_type"] == "manual"

    def test_latest_ignores_evaluation_runs(self, client):
        """
        A 'test' or 'evaluation' row must NEVER appear as the live latest
        operational result — this is the architectural guard that keeps
        benchmark artifacts out of the dashboard.
        """
        save_run(
            _make_run(
                run_id="eval_001",
                run_type="evaluation",
                run_timestamp="2099-01-01T00:00:00",
                target_date="2099-01-01",
                predicted_fwi=99.9,
            )
        )
        save_run(
            _make_run(
                run_id="test_001",
                run_type="test",
                run_timestamp="2098-12-31T23:59:59",
                target_date="2098-12-31",
                predicted_fwi=88.8,
            )
        )
        r = client.get("/risk/latest")
        # No operational runs exist, only test/evaluation — must 404.
        assert r.status_code == 404

    def test_latest_prefers_scheduled_over_evaluation(self, client):
        """An older scheduled run must win over a newer evaluation run."""
        save_run(
            _make_run(
                run_id="eval_future",
                run_type="evaluation",
                run_timestamp="2099-01-01T00:00:00",
                predicted_fwi=99.9,
            )
        )
        save_run(
            _make_run(
                run_id="sched_today",
                run_type="scheduled",
                run_timestamp="2026-04-14T11:00:00",
                predicted_fwi=22.1,
            )
        )
        r = client.get("/risk/latest")
        assert r.status_code == 200
        data = r.json()
        assert data["run_id"] == "sched_today"
        assert data["run_type"] == "scheduled"


class TestDroneEndpoint:
    def test_drone_state_default(self, client):
        r = client.get("/drone/state")
        assert r.status_code == 200
        data = r.json()
        assert "drone_status" in data


class TestDatabasePersistence:
    def test_save_and_retrieve(self):
        run = {
            "run_id": "dbtest001",
            "run_type": "test",
            "run_timestamp": "2025-07-15T12:00:00",
            "target_date": "2025-07-15",
            "predicted_fwi": 41.2,
            "high_risk_probability": 0.88,
            "high_risk_flag": 1,
            "decision_reason": "Above threshold",
            "drone_state": {"active_alert_window": True},
            "raw_inputs": {},
            "feature_values": {},
            "validation": {"is_valid": True},
            "thresholds": {},
        }
        save_run(run)
        from src.api.db.database import get_run_by_id
        retrieved = get_run_by_id("dbtest001")
        assert retrieved is not None
        assert retrieved["predicted_fwi"] == 41.2
        assert retrieved["high_risk_flag"] == 1

    def test_system_state(self):
        from src.api.db.database import set_system_state, get_system_state
        set_system_state("test_key", {"foo": "bar"})
        result = get_system_state("test_key")
        assert result == {"foo": "bar"}


class TestJsonSafeEncoding:
    """Guards for Issue 1: Timestamp / numpy scalars must never crash /risk/check."""

    def test_to_json_safe_handles_timestamp(self):
        import json
        import numpy as np
        import pandas as pd

        from src.api.json_safe import to_json_safe

        raw = {
            "date": pd.Timestamp("2025-07-15"),
            "temperature": np.float64(35.4),
            "rh": np.int64(42),
            "flag": np.bool_(True),
            "nested": {"ts": pd.Timestamp("2025-07-15T12:30:00")},
            "nan": float("nan"),
            "inf": float("inf"),
        }
        safe = to_json_safe(raw)
        # Must round-trip through json.dumps without a default= encoder.
        json.dumps(safe)
        assert safe["date"] == "2025-07-15T00:00:00"
        assert safe["temperature"] == pytest.approx(35.4)
        assert safe["rh"] == 42
        assert safe["flag"] is True
        assert safe["nested"]["ts"] == "2025-07-15T12:30:00"
        assert safe["nan"] is None
        assert safe["inf"] is None


class TestRunTypeTaxonomy:
    """Guards for Issue 2: run_type separation must be enforced end-to-end."""

    def test_normalize_collapses_legacy_values(self):
        from src.api.run_types import (
            RUN_TYPE_EVALUATION,
            RUN_TYPE_SCHEDULED,
            normalize_run_type,
        )

        assert normalize_run_type("scheduled_morning") == RUN_TYPE_SCHEDULED
        assert normalize_run_type("scheduled_afternoon") == RUN_TYPE_SCHEDULED
        assert normalize_run_type("SCHEDULED") == RUN_TYPE_SCHEDULED
        assert normalize_run_type("unknown_value") == RUN_TYPE_EVALUATION
        assert normalize_run_type(None) == RUN_TYPE_EVALUATION

    def test_operational_vs_evaluation_classification(self):
        from src.api.run_types import is_evaluation, is_operational

        assert is_operational("manual") is True
        assert is_operational("scheduled") is True
        assert is_operational("test") is False
        assert is_operational("evaluation") is False
        assert is_evaluation("test") is True
        assert is_evaluation("evaluation") is True
        assert is_evaluation("manual") is False

    def test_save_run_normalizes_legacy_scheduled_value(self):
        """Legacy `scheduled_morning` must collapse to `scheduled` on save."""
        from src.api.db.database import get_run_by_id

        save_run(
            _make_run(
                run_id="legacy_sched",
                run_type="scheduled_morning",
                run_timestamp="2026-04-14T11:00:00",
            )
        )
        row = get_run_by_id("legacy_sched")
        assert row is not None
        assert row["run_type"] == "scheduled"


class TestAnalyticsEndpoint:
    def test_analytics_returns_data(self, client):
        r = client.get("/history/analytics")
        assert r.status_code == 200
        data = r.json()
        assert "dataset_range" in data
        assert "yearly_stats" in data
        assert "seasonal_profile" in data
        assert "year_over_year" in data
        assert "monthly_series" in data
        assert data["total_records"] > 0
        assert len(data["yearly_stats"]) >= 10  # 2012-2025 = 14 years

    def test_analytics_yearly_structure(self, client):
        r = client.get("/history/analytics")
        data = r.json()
        year = data["yearly_stats"][0]
        assert "year" in year
        assert "mean_fwi" in year
        assert "max_fwi" in year
        assert "high_risk_days" in year
        assert "total_days" in year
