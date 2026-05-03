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
        cams.CAMERAS[cam_id].last_error = None
    notif.clear_notifications()
    yield
    for cam_id in list(cams.CAMERAS.keys()):
        cams.stop_camera(cam_id)
        cams.CAMERAS[cam_id].last_error = None
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

    def test_camera_start_reports_unavailable_immediately(
        self, client, monkeypatch
    ):
        error = cams.CameraError(
            code="device_not_found",
            message=cams.CAMERA_UNAVAILABLE_MESSAGE,
        )
        monkeypatch.setattr(cams, "_open_capture", lambda index: (None, error))

        r = client.post("/monitoring/cameras/webcam/start")
        assert r.status_code == 200
        data = r.json()
        assert data["started"] is False
        assert data["running"] is False
        assert data["last_error"]["code"] == "device_not_found"
        assert "Camera is unavailable" in data["last_error"]["message"]

        status = client.get("/monitoring/cameras/webcam/status").json()
        assert status["running"] is False
        assert status["last_error"]["code"] == "device_not_found"

        feed = client.get("/monitoring/cameras/webcam/feed")
        assert feed.status_code == 503
        assert feed.json()["detail"]["code"] == "device_not_found"

    def test_camera_feed_stopped_returns_clear_status(self, client):
        r = client.get("/monitoring/cameras/webcam/feed")
        assert r.status_code == 409
        assert "Start the camera" in r.json()["detail"]


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
        """If this ever fails, the separation rule was violated.

        After the approved migration of Detection Alerts from JSONL
        into SQLite, monitoring legitimately shares the same DB
        *file* as the prediction layer — but only the
        ``detection_alerts`` table. The architectural invariants are:

        - monitoring must not import inference / pipeline /
          stage-trainer modules; and
        - monitoring source code must not reference the
          prediction-side tables (``run_history`` / ``system_state``)
          in *executable code*. Prose mentions inside docstrings or
          ``#`` comments are fine — they are how we *document* the
          separation rule.

        We tokenise the source rather than substring-grep so a
        comment like "strictly separated from run_history" can stay
        in the module header without tripping the guard.
        """
        import io
        import tokenize

        import src.monitoring.cameras as cam_mod
        import src.monitoring.drone as drone_mod
        import src.monitoring.notifications as notif_mod
        import src.monitoring.yolo_detector as yolo_mod

        forbidden = {
            "src.inference",
            "src.pipeline.live_inference",
            "src.pipeline.train_pipeline",
            "src.models.stage1",
            "src.models.stage2",
            "run_history",
            "system_state",
        }

        def _executable_tokens(path: Path) -> list[str]:
            with path.open("rb") as fh:
                tokens = list(tokenize.tokenize(fh.readline))
            return [
                t.string
                for t in tokens
                if t.type
                not in (tokenize.COMMENT, tokenize.STRING, tokenize.ENCODING)
            ]

        for mod in (cam_mod, drone_mod, notif_mod, yolo_mod):
            tokens_text = " ".join(
                _executable_tokens(Path(mod.__file__))
            )
            for needle in forbidden:
                assert needle not in tokens_text, (
                    f"monitoring module {mod.__name__} touches forbidden "
                    f"prediction dependency '{needle}'"
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
        # the same SQLite table, so they must agree on the count
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


class TestDetectionAlertsReadState:
    """Coverage for SQLite read/unread persistence.

    Each alert is unread by default; ``mark-read`` flips a single
    alert; ``mark-all-read`` flips every currently-unread alert in
    one shot. State survives backend restarts because it lives in the
    ``detection_alerts`` table."""

    def test_new_alert_is_unread_by_default(self, client):
        notif.clear_notifications()
        a = client.post("/monitoring/alerts/test").json()
        assert a["read"] is False
        assert a["is_read"] == 0
        assert a["read_at"] is None

    def test_summary_reports_unread_and_read_counts(self, client):
        notif.clear_notifications()
        a1 = client.post("/monitoring/alerts/test").json()
        client.post("/monitoring/alerts/test")
        client.post("/monitoring/alerts/test")
        s = client.get("/monitoring/alerts/summary").json()
        assert s["total"] == 3
        assert s["unread_count"] == 3
        assert s["read_count"] == 0
        assert s["latest_alert"] is not None
        assert s["latest_alert"]["read"] is False
        # mark one read → counts shift
        r = client.post(f"/monitoring/alerts/{a1['id']}/read")
        assert r.status_code == 200
        assert r.json()["read"] is True
        assert r.json()["is_read"] == 1
        s2 = client.get("/monitoring/alerts/summary").json()
        assert s2["unread_count"] == 2
        assert s2["read_count"] == 1

    def test_filter_unread_and_read(self, client):
        notif.clear_notifications()
        a1 = client.post("/monitoring/alerts/test").json()
        client.post("/monitoring/alerts/test")
        client.post(f"/monitoring/alerts/{a1['id']}/read")
        unread = client.get(
            "/monitoring/alerts?filter=unread"
        ).json()["alerts"]
        read = client.get(
            "/monitoring/alerts?filter=read"
        ).json()["alerts"]
        assert len(unread) == 1
        assert all(a["read"] is False for a in unread)
        assert len(read) == 1
        assert all(a["read"] is True for a in read)
        assert {a["id"] for a in unread}.isdisjoint({a["id"] for a in read})

    def test_mark_all_read_flips_only_unread(self, client):
        notif.clear_notifications()
        a1 = client.post("/monitoring/alerts/test").json()
        client.post("/monitoring/alerts/test")
        client.post("/monitoring/alerts/test")
        # Pre-read one so mark-all-read should flip exactly two.
        client.post(f"/monitoring/alerts/{a1['id']}/read")
        r = client.post("/monitoring/alerts/mark-all-read")
        assert r.status_code == 200
        assert r.json()["flipped"] == 2
        s = client.get("/monitoring/alerts/summary").json()
        assert s["unread_count"] == 0
        assert s["read_count"] == s["total"]

    def test_mark_unread_reverts(self, client):
        notif.clear_notifications()
        a = client.post("/monitoring/alerts/test").json()
        client.post(f"/monitoring/alerts/{a['id']}/read")
        client.post(f"/monitoring/alerts/{a['id']}/unread")
        s = client.get("/monitoring/alerts/summary").json()
        assert s["unread_count"] == 1
        assert s["read_count"] == 0

    def test_mark_read_404_for_unknown_id(self, client):
        notif.clear_notifications()
        r = client.post("/monitoring/alerts/does-not-exist/read")
        assert r.status_code == 404

    def test_mark_read_is_idempotent(self, client):
        notif.clear_notifications()
        a = client.post("/monitoring/alerts/test").json()
        first = client.post(f"/monitoring/alerts/{a['id']}/read")
        second = client.post(f"/monitoring/alerts/{a['id']}/read")
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["read"] is True
        assert second.json()["read"] is True
        assert first.json()["read_at"] == second.json()["read_at"]

    def test_read_state_persists_across_module_lookups(self, client):
        # Simulates a backend restart: the in-memory ring buffer can be
        # empty, and the API still answers correctly because it reads
        # SQLite on every call.
        notif.clear_notifications()
        a = client.post("/monitoring/alerts/test").json()
        client.post(f"/monitoring/alerts/{a['id']}/read")
        # Force an in-memory wipe; SQLite remains the source of truth.
        notif._notifications.clear()
        s = client.get("/monitoring/alerts/summary").json()
        assert s["read_count"] == 1
        again = client.get(f"/monitoring/alerts/{a['id']}").json()
        assert again["read"] is True
        assert again["is_read"] == 1
        assert again["read_at"]

    def test_read_state_survives_new_db_connection(self, client):
        from src.api.db.database import get_connection

        notif.clear_notifications()
        a = client.post("/monitoring/alerts/test").json()
        client.post(f"/monitoring/alerts/{a['id']}/read")

        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT is_read, read_at FROM detection_alerts WHERE alert_id = ?",
                (a["id"],),
            ).fetchone()
        finally:
            conn.close()

        assert row is not None
        assert row["is_read"] == 1
        assert row["read_at"]

    def test_snapshot_status_reports_missing_and_ready(self, client):
        notif.clear_notifications()
        missing = notif.add_notification(
            "webcam",
            [{"label": "fire", "confidence": 0.7, "bbox": [0, 0, 1, 1]}],
            image_path="/static/notifications/not-written-yet.jpg",
        )
        assert missing["snapshot_ready"] is False

        ready_file = notif.NOTIFICATIONS_DIR / "ready.jpg"
        ready_file.parent.mkdir(parents=True, exist_ok=True)
        ready_file.write_bytes(b"fake-jpeg")
        ready = notif.add_notification(
            "webcam",
            [{"label": "fire", "confidence": 0.8, "bbox": [0, 0, 1, 1]}],
            image_path="/static/notifications/ready.jpg",
        )
        assert ready["snapshot_ready"] is True
        assert ready["snapshot_version"] is not None

        rows = client.get("/monitoring/alerts").json()["alerts"]
        by_id = {a["id"]: a for a in rows}
        assert by_id[missing["id"]]["snapshot_ready"] is False
        assert by_id[ready["id"]]["snapshot_ready"] is True

    def test_imported_legacy_alerts_default_unread_without_sidecar(self, client):
        notif.clear_notifications()
        notif.ALERTS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        notif.ALERTS_LOG_PATH.write_text(
            '{"id":"legacy-1","source":"webcam","timestamp":1,'
            '"time_str":"2026-04-28 10:00:00","detection_count":1,'
            '"max_confidence":0.5,"image":null,'
            '"detections":[{"label":"smoke","confidence":0.5,"bbox":[0,0,1,1]}]}'
            "\n",
            encoding="utf-8",
        )
        assert notif.import_legacy_jsonl() == 1
        alert = client.get("/monitoring/alerts/legacy-1").json()
        assert alert["read"] is False
        assert alert["is_read"] == 0
        assert alert["read_at"] is None


class TestMonitoringRuntime:
    """``/monitoring/runtime`` is what the Monitoring tab uses to render
    the right unavailable-camera copy. We can't toggle in-Docker for a
    pytest run on the host, but we can pin the env-driven hint."""

    def test_runtime_endpoint_shape(self, client):
        r = client.get("/monitoring/runtime")
        assert r.status_code == 200
        data = r.json()
        assert set(data.keys()) >= {
            "in_docker",
            "host_os",
            "camera_passthrough_supported",
        }
        assert isinstance(data["in_docker"], bool)
        assert data["host_os"] in {"windows", "posix"}

    def test_production_env_marks_in_docker_true(self, client, monkeypatch):
        monkeypatch.setenv("BACKEND_ENV", "production")
        data = client.get("/monitoring/runtime").json()
        assert data["in_docker"] is True
        # On Windows host this is False (the actual hint shown to
        # the user); on Linux it's True.
        if data["host_os"] == "windows":
            assert data["camera_passthrough_supported"] is False
