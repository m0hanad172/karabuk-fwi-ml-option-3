import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# --- Targets ---
TARGET_REGRESSION = "FWI"
TARGET_CLASSIFICATION = "target_ge_35"

# --- Thresholds ---
CLASS_THRESHOLD = 35
NEAR_THRESHOLD = 28  # lower edge of the "grey zone" for stacked decision
DEFAULT_PROBABILITY_THRESHOLD = 0.10  # Stage 2 probability cutoff (tuned later)

# --- Temporal splits ---
WALK_FORWARD_START_TRAIN_END = 2015  # first fold trains 2012-2015, predicts 2016
VAL_YEAR = 2024
FINAL_TEST_YEAR = 2025

# --- Sample weights for regression ---
WEIGHT_HIGH = 4.0   # FWI >= 35
WEIGHT_MID = 2.0    # FWI >= 20
WEIGHT_LOW = 1.0    # FWI < 20

# --- Location ---
LATITUDE = 41.2061
LONGITUDE = 32.6204
TIMEZONE = "auto"

# --- Operational ---
LIVE_REFRESH_MINUTES = 5
SCHEDULED_RUN_HOURS = [9, 11, 15]
ENABLE_AFTERNOON_RECHECK_DEFAULT = True
DRONE_INTERVAL_MINUTES = 30
MANUAL_CHECK_CAN_TRIGGER_DRONE_DEFAULT = False
HISTORY_WINDOW_DAYS = 40

# --- Drone-ready hardware adapter ---
DRONE_MODE = os.getenv("DRONE_MODE", "mock").strip().lower()
if DRONE_MODE not in {"mock", "tello"}:
    DRONE_MODE = "mock"
DRONE_AUTO_CONNECT = _env_bool("DRONE_AUTO_CONNECT", False)
DRONE_VIDEO_ENABLED = _env_bool("DRONE_VIDEO_ENABLED", True)
DRONE_ALLOW_MANUAL_CONTROL = _env_bool("DRONE_ALLOW_MANUAL_CONTROL", False)
DRONE_ALLOW_AUTO_TAKEOFF = _env_bool("DRONE_ALLOW_AUTO_TAKEOFF", False)
DRONE_ALLOW_DEMO_PATROL = _env_bool("DRONE_ALLOW_DEMO_PATROL", False)
DRONE_REQUIRE_OPERATOR_CONFIRMATION = _env_bool(
    "DRONE_REQUIRE_OPERATOR_CONFIRMATION", True
)
DRONE_BATTERY_MIN_PERCENT = _env_int("DRONE_BATTERY_MIN_PERCENT", 25)
DRONE_COMMAND_TIMEOUT_SECONDS = _env_int("DRONE_COMMAND_TIMEOUT_SECONDS", 5)
DRONE_PATROL_SLOT_MINUTES = _env_int("DRONE_PATROL_SLOT_MINUTES", 30)
DRONE_AFTERNOON_CUTOFF_HOUR = _env_int("DRONE_AFTERNOON_CUTOFF_HOUR", 17)
DRONE_DEFAULT_STATION_ID = os.getenv("DRONE_DEFAULT_STATION_ID", "station_1")
DRONE_YOLO_CONF = _env_float("DRONE_YOLO_CONF", 0.4)
DRONE_DEMO_MOVE_CM = _env_int("DRONE_DEMO_MOVE_CM", 100)
DRONE_DEMO_UP_CM = _env_int("DRONE_DEMO_UP_CM", 50)
DRONE_DEMO_COMMAND_DELAY_SECONDS = _env_float(
    "DRONE_DEMO_COMMAND_DELAY_SECONDS", 1.0
)

# DJI Tello network defaults. These are configuration only; the app does
# not connect to real hardware unless DRONE_MODE=tello and an operator
# explicitly calls the connect/stream endpoint.
TELLO_IP = os.getenv("TELLO_IP", "192.168.10.1")
TELLO_COMMAND_PORT = _env_int("TELLO_COMMAND_PORT", 8889)
TELLO_VIDEO_PORT = _env_int("TELLO_VIDEO_PORT", 11111)

# --- Live display ---
LIVE_DISPLAY_SOURCE = "open_meteo_current"
LIVE_SCOPE_LABEL = "Karabuk city, Turkey"
DISPLAY_TIMEZONE = "Europe/Istanbul"
