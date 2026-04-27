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
SCHEDULED_RUN_HOURS = [11, 15]
ENABLE_AFTERNOON_RECHECK_DEFAULT = True
DRONE_INTERVAL_MINUTES = 30
MANUAL_CHECK_CAN_TRIGGER_DRONE_DEFAULT = False
HISTORY_WINDOW_DAYS = 40

# --- Live display ---
LIVE_DISPLAY_SOURCE = "open_meteo_current"
LIVE_SCOPE_LABEL = "Karabuk city, Turkey"
DISPLAY_TIMEZONE = "Europe/Istanbul"
