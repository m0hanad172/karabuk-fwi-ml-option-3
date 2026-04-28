"""Tests for the /monitoring/* endpoints.

These tests verify the detection layer is wired correctly and — most
importantly — that it is strictly separated from the Option 3 prediction
pipeline. They must NOT require any actual camera hardware, YOLO weights,
or djitellopy installation to pass.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from src.api.main import app
from src.monitoring import cameras as cams
from src.monitoring import notifications as notif


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset_state():
    """Ensure no background threads or notifications leak between tests."""
    for cam_id in list(cams.CAMERAS.keys()):
        cams.stop_camera(cam_id)
    notif.clear_notifications()
    yield
    for cam_id in list(cams.CAMERAS.keys()):
        cams.stop_camera(cam_id)
    notif.clear_notifications()


class TestCameraEndpoints:
    def test_list_cameras(self, client):
        r = client.get("/monitoring/cameras")
        assert r.status_code == 200
        data = r.json()
        assert "cameras" in data
        cam_ids = {c["cam_id"] for c in data["cameras"]}
        assert "pc_camera" in cam_ids
        assert "webcam" in cam_ids

    def test_camera_status_unknown(self, client):
        r = client.get("/monitoring/cameras/does_not_exist/status")
        assert r.status_code == 404

    def test_camera_status_known(self, client):
        r = client.get("/monitoring/cameras/pc_camera/status")
        assert r.status_code == 200
        data = r.json()
        assert data["exists"] is True
        assert data["cam_id"] == "pc_camera"
        assert "running" in data

    def test_camera_stop_unknown(self, client):
        r = client.post("/monitoring/cameras/nope/stop")
        assert r.status_code == 404


class TestDroneEndpoints:
    def test_drone_status_default(self, client):
        r = client.get("/monitoring/drone/status")
        assert r.status_code == 200
        data = r.json()
        # We assert on schema presence only — hardware availability varies.
        assert "running" in data
        assert "connected" in data
        assert "hardware_available" in data
        assert "detection_count" in data

    def test_drone_stop_idempotent(self, client):
        r = client.post("/monitoring/drone/stop")
        assert r.status_code == 200
        data = r.json()
        assert data["running"] is False


class TestNotifications:
    def test_empty_notifications(self, client):
        r = client.get("/monitoring/notifications")
        assert r.status_code == 200
        data = r.json()
        assert data == {"notifications": []}

    def test_add_notification_appears(self, client):
        notif.add_notification("pc_camera", [{"confidence": 0.92, "bbox": [0, 0, 10, 10]}])
        r = client.get("/monitoring/notifications")
        data = r.json()
        assert len(data["notifications"]) == 1
        entry = data["notifications"][0]
        assert entry["source"] == "pc_camera"
        assert entry["detection_count"] == 1
        assert entry["max_confidence"] == pytest.approx(0.92)

    def test_throttle(self):
        assert notif.should_notify("drone") is True
        notif.add_notification("drone", [{"confidence": 0.5, "bbox": [0, 0, 1, 1]}])
        # Immediately after, the throttle must block.
        assert notif.should_notify("drone") is False


class TestDetectionAlerts:
    """Durable detection evidence log — powers the Detection Alerts tab."""

    def test_alerts_empty_summary(self, client):
        r = client.get("/monitoring/alerts/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["by_source"] == {}
        assert data["max_confidence"] is None
        assert data["last_time_str"] is None

    def test_add_notification_persists_to_alerts(self, client):
        notif.add_notification(
            "drone",
            [
                {"label": "fire", "confidence": 0.91, "bbox": [10, 20, 50, 90]},
                {"label": "fire", "confidence": 0.72, "bbox": [100, 110, 130, 150]},
            ],
            image_path="/static/notifications/drone_x.jpg",
        )
        r = client.get("/monitoring/alerts")
        assert r.status_code == 200
        data = r.json()
        assert len(data["alerts"]) == 1
        alert = data["alerts"][0]
        assert alert["source"] == "drone"
        assert alert["detection_count"] == 2
        assert alert["max_confidence"] == pytest.approx(0.91)
        assert alert["image"] == "/static/notifications/drone_x.jpg"
        # Full detection list must survive in the evidence log.
        assert len(alert["detections"]) == 2
        assert alert["detections"][0]["bbox"] == [10.0, 20.0, 50.0, 90.0]
        assert alert["detections"][0]["label"] == "fire"

    def test_alerts_source_filter(self, client):
        notif.add_notification(
            "drone", [{"confidence": 0.5, "bbox": [0, 0, 1, 1]}]
        )
        notif.add_notification(
            "webcam", [{"confidence": 0.6, "bbox": [0, 0, 1, 1]}]
        )
        notif.add_notification(
            "pc_camera", [{"confidence": 0.7, "bbox": [0, 0, 1, 1]}]
        )
        r = client.get("/monitoring/alerts?source=webcam")
        data = r.json()
        assert len(data["alerts"]) == 1
        assert data["alerts"][0]["source"] == "webcam"

    def test_alert_detail_lookup(self, client):
        entry = notif.add_notification(
            "pc_camera",
            [{"label": "fire", "confidence": 0.88, "bbox": [1, 2, 3, 4]}],
        )
        r = client.get(f"/monitoring/alerts/{entry['id']}")
        assert r.status_code == 200
        alert = r.json()
        assert alert["id"] == entry["id"]
        assert alert["source"] == "pc_camera"
        assert alert["detections"][0]["bbox"] == [1.0, 2.0, 3.0, 4.0]

    def test_alert_detail_not_found(self, client):
        r = client.get("/monitoring/alerts/does-not-exist")
        assert r.status_code == 404

    def test_alerts_summary_aggregates(self, client):
        notif.add_notification(
            "drone", [{"confidence": 0.4, "bbox": [0, 0, 1, 1]}]
        )
        notif.add_notification(
            "drone", [{"confidence": 0.95, "bbox": [0, 0, 1, 1]}]
        )
        notif.add_notification(
            "webcam", [{"confidence": 0.6, "bbox": [0, 0, 1, 1]}]
        )
        r = client.get("/monitoring/alerts/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert data["by_source"] == {"drone": 2, "webcam": 1}
        assert data["max_confidence"] == pytest.approx(0.95)
        assert data["last_time_str"] is not None
        # Last alert was the webcam one (added last).
        assert data["last_source"] == "webcam"


class TestSeparationFromPrediction:
    """Architectural guard: monitoring must not touch the prediction path."""

    def test_monitoring_does_not_import_inference(self):
        """If this ever fails, the separation rule was violated."""
        import src.monitoring.cameras as cam_mod
        import src.monitoring.drone as drone_mod
        import src.monitoring.notifications as notif_mod
        import src.monitoring.yolo_detector as yolo_mod

        for mod in (cam_mod, drone_mod, notif_mod, yolo_mod):
            source = Path(mod.__file__).read_text(encoding="utf-8")
            for forbidden in (
                "src.inference",
                "src.pipeline.live_inference",
                "src.pipeline.train_pipeline",
                "src.models.stage1",
                "src.models.stage2",
                "src.api.db.database",
            ):
                assert forbidden not in source, (
                    f"monitoring module {mod.__name__} imports forbidden prediction "
                    f"dependency '{forbidden}'"
                )

    def test_notifications_stored_in_memory_not_run_history(self, client):
        """A monitoring notification must not create a run_history entry."""
        from src.api.db.database import get_run_history

        before = len(get_run_history(limit=500))
        notif.add_notification("webcam", [{"confidence": 0.8, "bbox": [0, 0, 1, 1]}])
        after = len(get_run_history(limit=500))
        assert after == before, "monitoring leaked into run_history"


class TestDetectionAlertsLatestAndTest:
    """Coverage for the ``/alerts/latest`` convenience endpoint and the
    ``/alerts/test`` demo endpoint that lets the dashboard be exercised
    end-to-end without camera/drone hardware. Both back the in-app
    banner (latest) and the "Test alert" button (test) added in the
    Detection Alerts tab."""

    def test_latest_returns_null_when_log_empty(self, client):
        notif.clear_notifications()
        r = client.get("/monitoring/alerts/latest")
        assert r.status_code == 200
        assert r.json() == {"alert": None}

    def test_latest_tracks_most_recent(self, client):
        notif.clear_notifications()
        notif.add_notification(
            "pc_camera",
            [{"label": "fire", "confidence": 0.5, "bbox": [0, 0, 1, 1]}],
        )
        first = client.get("/monitoring/alerts/latest").json()["alert"]
        assert first is not None
        assert first["source"] == "pc_camera"

        # Second alert — /alerts/latest must update to point at it.
        notif.add_notification(
            "webcam",
            [{"label": "fire", "confidence": 0.6, "bbox": [1, 1, 2, 2]}],
        )
        second = client.get("/monitoring/alerts/latest").json()["alert"]
        assert second is not None
        assert second["source"] == "webcam"
        assert second["id"] != first["id"]

    def test_post_test_alert_persists_through_evidence_log(self, client):
        notif.clear_notifications()
        before = client.get("/monitoring/alerts/summary").json()
        assert before["total"] == 0

        r = client.post(
            "/monitoring/alerts/test",
            params={"label": "smoke", "confidence": 0.91, "source": "demo"},
        )
        assert r.status_code == 200
        created = r.json()
        assert created["source"] == "demo"
        assert created["max_confidence"] == 0.91

        # Lands in summary, list, and latest — all three reading from
        # the same JSONL evidence log, so they must agree on the count
        # and the most-recent id.
        after = client.get("/monitoring/alerts/summary").json()
        assert after["total"] == 1
        assert after["by_source"].get("demo") == 1

        listing = client.get("/monitoring/alerts").json()["alerts"]
        assert len(listing) == 1
        assert listing[0]["id"] == created["id"]
        assert listing[0]["detections"][0]["label"] == "smoke"

        latest = client.get("/monitoring/alerts/latest").json()["alert"]
        assert latest is not None
        assert latest["id"] == created["id"]

    def test_post_test_alert_collapses_unknown_label_to_fire(self, client):
        notif.clear_notifications()
        r = client.post(
            "/monitoring/alerts/test",
            params={"label": "rainbow", "confidence": 0.5},
        )
        assert r.status_code == 200
        latest = client.get("/monitoring/alerts/latest").json()["alert"]
        assert latest["detections"][0]["label"] == "fire"

    def test_post_test_alert_does_not_leak_into_run_history(self, client):
        """The /alerts/test endpoint goes through the monitoring layer
        only — it must never write into the prediction audit log."""
        from src.api.db.database import get_run_history

        notif.clear_notifications()
        before = len(get_run_history(limit=500))
        client.post("/monitoring/alerts/test")
        after = len(get_run_history(limit=500))
        assert after == before, "demo alert leaked into run_history"

    def test_alerts_latest_does_not_shadow_alert_id_route(self, client):
        """Ensure ``/alerts/{id}`` still resolves a real id even though
        the literal slug ``"latest"`` superficially fits the
        ``{alert_id}`` slot — i.e. confirm route order in the router."""
        notif.clear_notifications()
        created = client.post("/monitoring/alerts/test").json()
        rid = created["id"]
        r = client.get(f"/monitoring/alerts/{rid}")
        assert r.status_code == 200
        assert r.json()["id"] == rid


class TestDemoAlertGating:
    """The ``/alerts/test`` demo endpoint must be hideable in
    production. The frontend's Test alert button reads the flag from
    ``GET /system/config``, so the two surfaces enable/disable
    together."""

    def test_demo_endpoint_returns_404_when_disabled(self, client, monkeypatch):
        monkeypatch.setenv("DEMO_ALERTS_ENABLED", "false")
        r = client.post("/monitoring/alerts/test")
        assert r.status_code == 404
        assert "disabled" in r.json()["detail"].lower()

    def test_demo_endpoint_disabled_under_production_env(self, client, monkeypatch):
        # Production default: off, even without an explicit
        # DEMO_ALERTS_ENABLED override.
        monkeypatch.setenv("BACKEND_ENV", "production")
        monkeypatch.delenv("DEMO_ALERTS_ENABLED", raising=False)
        r = client.post("/monitoring/alerts/test")
        assert r.status_code == 404

    def test_demo_endpoint_enabled_when_flag_explicitly_true(
        self, client, monkeypatch
    ):
        # Explicit override beats the env default.
        monkeypatch.setenv("BACKEND_ENV", "production")
        monkeypatch.setenv("DEMO_ALERTS_ENABLED", "true")
        notif.clear_notifications()
        r = client.post("/monitoring/alerts/test")
        assert r.status_code == 200

    def test_system_config_reports_flag(self, client, monkeypatch):
        # Development default: enabled.
        monkeypatch.setenv("BACKEND_ENV", "development")
        monkeypatch.delenv("DEMO_ALERTS_ENABLED", raising=False)
        cfg = client.get("/system/config").json()
        assert cfg["backend_env"] == "development"
        assert cfg["service_mode"] == "development"
        assert cfg["demo_alerts_enabled"] is True
        assert cfg["version"] == "2.0.0"

        # Production default: disabled.
        monkeypatch.setenv("BACKEND_ENV", "production")
        monkeypatch.delenv("DEMO_ALERTS_ENABLED", raising=False)
        cfg = client.get("/system/config").json()
        assert cfg["demo_alerts_enabled"] is False
        assert cfg["backend_env"] == "production"
        assert cfg["service_mode"] == "production"
