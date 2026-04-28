"""
Project-wide pytest fixtures.

Isolates the test SQLite DB from the production ``outputs/karabuk_fwi.db``
so that test fixtures (seeded `run_type="test"` rows, etc.) can never
pollute the live operational dashboard. The redirect is installed via
the ``KARABUK_DB_PATH`` environment variable, which ``src.api.db.database``
reads at call time.
"""
from __future__ import annotations

import os
import shutil
import sys
import uuid
from pathlib import Path

import pytest

# Make `src/` importable for every test without duplicating sys.path hacks.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEST_TMP_ROOT = _REPO_ROOT / ".tmp" / "pytest-runtime"


def _make_test_dir(label: str) -> Path:
    """Create a repo-local temp dir.

    Some Windows environments deny access to the default OS temp tree
    from sandboxed subprocesses. Keeping test runtime files under the
    ignored workspace .tmp directory avoids that without touching the
    operational SQLite DB or detection evidence log.
    """
    _TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = _TEST_TMP_ROOT / f"{label}-{os.getpid()}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _best_effort_rmtree(path: Path) -> None:
    try:
        shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass


@pytest.fixture(scope="session", autouse=True)
def _isolated_test_db():
    """Redirect every DB write in the test session to a temp file."""
    tmp_dir = _make_test_dir("db")
    tmp_db = tmp_dir / "karabuk_fwi_test.db"
    prev = os.environ.get("KARABUK_DB_PATH")
    os.environ["KARABUK_DB_PATH"] = str(tmp_db)
    try:
        yield tmp_db
    finally:
        if prev is None:
            os.environ.pop("KARABUK_DB_PATH", None)
        else:
            os.environ["KARABUK_DB_PATH"] = prev
        _best_effort_rmtree(tmp_dir)


@pytest.fixture(autouse=True)
def _reset_test_db():
    """
    Wipe run_history + system_state between tests so fixtures don't
    cross-contaminate. The DB file itself is re-used for speed.
    """
    # Import lazily so the env var above is already set.
    from src.api.db.database import get_connection, init_db

    init_db()
    conn = get_connection()
    conn.execute("DELETE FROM run_history")
    conn.execute("DELETE FROM system_state")
    conn.commit()
    conn.close()
    yield


@pytest.fixture(scope="session", autouse=True)
def _isolated_notifications_dir():
    """
    Redirect the monitoring notifications directory (and the JSONL
    evidence log inside it) to a temp path for the duration of the test
    session. Without this, ``test_monitoring`` would write alert frames
    and an ``alerts.jsonl`` file into the real ``data/notifications/``
    directory — polluting the operational evidence log and making the
    Detection Alerts tab show ghost test entries in dev.
    """
    tmp_dir = _make_test_dir("notifications")

    # Patch the module-level constants in src.monitoring.notifications.
    # `NOTIFICATIONS_DIR` is used by ``_ensure_dir`` / ``save_snapshot``;
    # ``ALERTS_LOG_PATH`` is the JSONL evidence log path; and
    # ``ALERTS_READ_STATE_PATH`` is the sidecar JSON used for the
    # Detection Alerts read/unread feature.
    from src.monitoring import notifications as notif

    orig_dir = notif.NOTIFICATIONS_DIR
    orig_log = notif.ALERTS_LOG_PATH
    orig_state = notif.ALERTS_READ_STATE_PATH
    notif.NOTIFICATIONS_DIR = tmp_dir
    notif.ALERTS_LOG_PATH = tmp_dir / "alerts.jsonl"
    notif.ALERTS_READ_STATE_PATH = tmp_dir / "alerts_read_state.json"
    try:
        yield tmp_dir
    finally:
        notif.NOTIFICATIONS_DIR = orig_dir
        notif.ALERTS_LOG_PATH = orig_log
        notif.ALERTS_READ_STATE_PATH = orig_state
        _best_effort_rmtree(tmp_dir)
