from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Data
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
OOF_DIR = DATA_DIR / "oof"

DATASET_PATH = PROCESSED_DATA_DIR / "Karabuk_FWI_Final_Features_GroupABC.csv"

# Model artifacts
MODELS_DIR = PROJECT_ROOT / "models"
STAGE1_DIR = MODELS_DIR / "stage1"
STAGE2_DIR = MODELS_DIR / "stage2"
METADATA_DIR = MODELS_DIR / "metadata"

# Outputs
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# Monitoring / detection (separate from the Stacked v3 prediction layer)
FIRE_DETECTION_DIR = MODELS_DIR / "fire_detection"
FIRE_DETECTION_MODEL_PATH = FIRE_DETECTION_DIR / "best4.pt"
NOTIFICATIONS_DIR = DATA_DIR / "notifications"

# Persistent camera mapping — survives backend restarts so the operator
# doesn't have to re-run auto-detect every boot. See
# src/monitoring/camera_mapping.py.
CAMERA_MAPPING_PATH = DATA_DIR / "camera_mapping.json"
