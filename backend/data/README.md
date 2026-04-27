# Data

Runtime data lives here. Some folders are checked into Git (small,
required to run a fresh clone), others are populated at runtime and
gitignored.

## Layout

```
data/
├── camera_mapping.json              ✅ tracked — persistent webcam/PC-camera roles
├── processed/
│   └── Karabuk_FWI_Final_Features_GroupABC.csv   ✅ tracked — engineered training set
├── oof/
│   ├── stage1_oof_predictions.csv   ✅ tracked — walk-forward OOF predictions
│   ├── stage1_test_predictions.csv  ✅ tracked
│   └── stage2_test_predictions.csv  ✅ tracked
├── notifications/                   ⚠️ partially tracked
│   ├── alerts.jsonl                 evidence log (legacy samples tracked, new ones ignored)
│   └── *.jpg                        detection snapshots (legacy samples tracked, new ones ignored)
├── raw/                             🚫 gitignored — rebuild via fetch_weather.py if needed
└── interim/                         🚫 gitignored — intermediate feature-engineering outputs
```

## What each folder is for

| Folder | Purpose |
|---|---|
| `processed/` | The engineered training set (34 features + targets) consumed by `scripts/train.py`. Required to retrain Stage 1 / Stage 2. |
| `oof/` | Out-of-fold predictions from walk-forward training. Stage 2 trains on `stage1_oof_predictions.csv`. The two `*_test_predictions.csv` files are the held-out 2025 evaluation predictions used by the dashboard's three-way comparison card. |
| `notifications/` | Detection layer evidence — written by `src/monitoring/notifications.py` whenever YOLO triggers. **The prediction pipeline never reads or writes here.** |
| `raw/` | Original Open-Meteo / soil moisture downloads. Not committed; regenerate with `python -m src.data.fetch_weather` if you need to rebuild the dataset from scratch. |
| `interim/` | Intermediate artefacts emitted by feature engineering. Not committed. |
| `camera_mapping.json` | Bound logical roles (`pc_camera`, `webcam`) → physical USB device fingerprints, so the operator does not have to re-run auto-detect every boot. See `src/monitoring/camera_mapping.py`. |

## Why notifications are *partially* tracked

A handful of detection snapshots from earlier runs are still in the
repo because they serve as visible demo evidence. Going forward, every
new snapshot is gitignored (`data/notifications/*.jpg`,
`data/notifications/*.jsonl`) so detection events do not dirty the
working tree. If you want to share new evidence with collaborators,
attach it to an issue or a PR instead of committing.

## Operational SQLite database

The backend persists run history and system state in
`outputs/karabuk_fwi.db`. That file is **not** in `data/` and is **not**
committed — it is created automatically on first boot. See
`SQLITE_GUIDE.md` for the schema and migration rules.
