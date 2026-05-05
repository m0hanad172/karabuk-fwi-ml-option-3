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


class TestSchedulerPersistence:
    def test_scheduler_configuration(self):
        from configs.settings import SCHEDULED_RUN_HOURS
        from src.api.time_utils import ISTANBUL_TZ

        assert SCHEDULED_RUN_HOURS == [9, 11, 15]
        assert getattr(ISTANBUL_TZ, "key", None) == "Europe/Istanbul"

    def test_start_scheduler_registers_all_slots(self):
        from src.api.services import scheduler

        scheduler.stop_scheduler()
        try:
            scheduler.start_scheduler()
            status = scheduler.get_scheduler_status()
            assert status["running"] is True
            assert len(status["jobs"]) == 3
            assert {job["id"] for job in status["jobs"]} == {
                "scheduled_early_morning_run",
                "scheduled_morning_run",
                "scheduled_afternoon_run",
            }
        finally:
            scheduler.stop_scheduler()

    def test_scheduled_run_persists_run_history(self, monkeypatch):
        from src.api.db.database import get_connection, get_run_by_id
        from src.api.services import risk_service, scheduler

        run_id = "sched_direct_001"

        def fake_run_risk_check(
            target_date=None,
            run_type="manual",
            allow_drone_trigger=None,
        ):
            return _make_run(
                run_id=run_id,
                run_type=run_type,
                run_timestamp="2026-05-03T09:00:00+03:00",
                target_date=target_date or "2026-05-03",
                predicted_fwi=24.5,
                high_risk_probability=0.12,
                high_risk_flag=0,
                drone_state={"active_alert_window": False},
            )

        monkeypatch.setattr(risk_service, "run_risk_check", fake_run_risk_check)
        monkeypatch.setattr(scheduler, "execute_risk_check", risk_service.execute_risk_check)

        result = scheduler._scheduled_run(hour=9, slot="early_morning")
        assert result["run_id"] == run_id
        assert result["run_type"] == "scheduled"

        row = get_run_by_id(run_id)
        assert row is not None
        assert row["run_type"] == "scheduled"

        conn = get_connection()
        try:
            persisted = conn.execute(
                "SELECT run_type FROM run_history WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        finally:
            conn.close()

        assert persisted is not None
        assert persisted["run_type"] == "scheduled"


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


class _FakeTelloController:
    mode = "tello"

    def __init__(self, battery: int | None, connected: bool):
        self.battery = battery
        self.connected = connected
        self.demo_called = False

    def get_status(self):
        from src.drone.models import DroneStatus

        return DroneStatus(
            mode="tello",
            connected=self.connected,
            stream_active=False,
            hardware_available=True,
            battery=self.battery,
            emergency_stopped=False,
        )

    def demo_patrol(self, move_cm: int, up_cm: int, delay_seconds: float):
        self.demo_called = True
        return [
            "takeoff",
            f"move_up {up_cm}cm",
            f"move_forward {move_cm}cm",
            "land",
        ]


def _install_fake_tello_service(monkeypatch, fake: _FakeTelloController) -> None:
    from configs import settings
    from src.drone.service import get_drone_service, reset_drone_service_for_tests

    monkeypatch.setattr(settings, "DRONE_MODE", "tello")
    monkeypatch.setattr(settings, "DRONE_ALLOW_DEMO_PATROL", True)
    monkeypatch.setattr(settings, "DRONE_ALLOW_AUTO_TAKEOFF", True)
    monkeypatch.setattr(settings, "DRONE_REQUIRE_OPERATOR_CONFIRMATION", True)
    monkeypatch.setattr(settings, "DRONE_BATTERY_MIN_PERCENT", 25)
    reset_drone_service_for_tests()
    service = get_drone_service()
    service.controller = fake


class TestOperatorDroneLayer:
    @pytest.fixture(autouse=True)
    def _reset_drone(self):
        from src.drone.service import reset_drone_service_for_tests

        reset_drone_service_for_tests()
        yield
        reset_drone_service_for_tests()

    def test_app_starts_without_real_drone(self, client):
        r = client.get("/drone/status")
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "mock"
        assert data["connected"] is False
        assert data["stream_active"] is False

    def test_mock_connect_disconnect(self, client):
        connected = client.post("/drone/connect")
        assert connected.status_code == 200
        assert connected.json()["connected"] is True

        disconnected = client.post("/drone/disconnect")
        assert disconnected.status_code == 200
        assert disconnected.json()["connected"] is False

    def test_mock_start_stop_stream(self, client):
        started = client.post("/drone/stream/start")
        assert started.status_code == 200
        assert started.json()["mode"] == "mock"
        assert started.json()["stream_active"] is True
        assert started.json()["connected"] is True

        stopped = client.post("/drone/stream/stop")
        assert stopped.status_code == 200
        assert stopped.json()["stream_active"] is False

    def test_demo_patrol_endpoint_mock_succeeds(self, client):
        r = client.post(
            "/drone/demo-patrol",
            json={"mode": "mock", "operator_confirmed": True},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["mode"] == "mock"
        assert data["status"] == "completed"
        assert "Mock demo patrol completed" in data["message"]
        assert data["route"] == [
            "takeoff",
            "up 50",
            "forward 100",
            "right 100",
            "back 100",
            "left 100",
            "land",
        ]

    def test_demo_patrol_tello_blocked_by_default(self, client, monkeypatch):
        from configs import settings
        from src.drone.service import reset_drone_service_for_tests

        monkeypatch.setattr(settings, "DRONE_MODE", "tello")
        monkeypatch.setattr(settings, "DRONE_ALLOW_DEMO_PATROL", False)
        reset_drone_service_for_tests()

        r = client.post(
            "/drone/demo-patrol",
            json={"mode": "tello", "operator_confirmed": True},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is False
        assert data["status"] == "blocked"
        assert "DRONE_ALLOW_DEMO_PATROL" in data["message"]

    def test_demo_patrol_missing_operator_confirmation_blocks_real_route(
        self, client, monkeypatch
    ):
        from configs import settings

        fake = _FakeTelloController(battery=80, connected=True)
        _install_fake_tello_service(monkeypatch, fake)

        r = client.post(
            "/drone/demo-patrol",
            json={"mode": "tello", "operator_confirmed": False},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is False
        assert "Operator confirmation" in data["message"]
        assert fake.demo_called is False
        assert settings.CLASS_THRESHOLD == 35

    def test_demo_patrol_low_battery_blocks_real_route(self, client, monkeypatch):
        fake = _FakeTelloController(battery=10, connected=True)
        _install_fake_tello_service(monkeypatch, fake)

        r = client.post(
            "/drone/demo-patrol",
            json={"mode": "tello", "operator_confirmed": True},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is False
        assert "battery" in data["message"].lower()
        assert fake.demo_called is False

    def test_demo_patrol_does_not_write_run_history_or_change_threshold(
        self, client
    ):
        from configs import settings
        from src.api.db.database import get_run_history

        before = len(get_run_history(limit=500))
        r = client.post(
            "/drone/demo-patrol",
            json={"mode": "mock", "operator_confirmed": True},
        )
        after = len(get_run_history(limit=500))

        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert after == before
        assert settings.CLASS_THRESHOLD == 35

    def test_manual_command_blocked_when_disabled(self, client):
        r = client.post("/drone/manual-command", json={"command": "forward"})
        assert r.status_code == 403

    def test_manual_command_accepted_in_mock_when_enabled(self, client, monkeypatch):
        from configs import settings
        from src.drone.service import reset_drone_service_for_tests

        monkeypatch.setattr(settings, "DRONE_ALLOW_MANUAL_CONTROL", True)
        reset_drone_service_for_tests()

        r = client.post("/drone/manual-command", json={"command": "forward"})
        assert r.status_code == 200
        assert r.json()["mode"] == "mock"

    def test_auto_takeoff_requires_extra_safety_flags(self, client, monkeypatch):
        from configs import settings
        from src.drone.service import reset_drone_service_for_tests

        monkeypatch.setattr(settings, "DRONE_ALLOW_MANUAL_CONTROL", True)
        monkeypatch.setattr(settings, "DRONE_ALLOW_AUTO_TAKEOFF", False)
        reset_drone_service_for_tests()

        r = client.post("/drone/manual-command", json={"command": "takeoff"})
        assert r.status_code == 403

    def test_tello_controller_not_instantiated_in_mock_mode(self, client, monkeypatch):
        import sys

        from configs import settings
        from src.drone.service import reset_drone_service_for_tests

        sys.modules.pop("src.drone.tello_controller", None)
        monkeypatch.setattr(settings, "DRONE_MODE", "mock")
        reset_drone_service_for_tests()

        r = client.get("/drone/status")
        assert r.status_code == 200
        assert r.json()["mode"] == "mock"
        assert "src.drone.tello_controller" not in sys.modules

    def test_high_risk_patrol_recommendation_does_not_launch(self, client):
        from src.api.db.database import set_system_state

        set_system_state(
            "latest_drone_state",
            {
                "active_alert_window": True,
                "drone_status": "ACTIVE_CYCLE",
                "drone_interval_minutes": 30,
                "next_launch_time": "2026-05-04T09:30:00+03:00",
                "reason": "High-risk flag active",
            },
        )

        patrol = client.get("/drone/patrol/state")
        assert patrol.status_code == 200
        assert patrol.json()["patrol_recommended"] is True
        assert patrol.json()["physical_launch_allowed"] is False

        status = client.get("/drone/status").json()
        assert status["connected"] is False
        assert status["stream_active"] is False

    def test_emergency_stop_is_idempotent(self, client):
        first = client.post("/drone/emergency-stop")
        second = client.post("/drone/emergency-stop")

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["emergency_stopped"] is True
        assert second.json()["emergency_stopped"] is True


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
