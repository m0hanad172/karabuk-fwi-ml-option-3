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
├── notifications/                   🚫 gitignored — runtime detection evidence
│   ├── alerts.jsonl                 JSONL evidence log (written by monitoring layer)
│   └── *.jpg                        detection snapshots (written by monitoring layer)
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

## Why notifications are gitignored

`backend/data/notifications/` is runtime evidence written by the
monitoring layer every time YOLO triggers — it is not part of the
project source. The `.gitignore` rules are:

```
backend/data/notifications/*.jsonl
backend/data/notifications/*.jpg
backend/data/notifications/*.jpeg
backend/data/notifications/*.png
```

This keeps detection events out of the working tree (so a busy
demo afternoon doesn't generate dozens of "untracked" entries) and
keeps the repository small. The directory itself stays in the repo
because the monitoring code creates files inside it on first run; if
the directory ever ends up empty in your clone, the backend will
recreate it automatically. If you need to share specific evidence
frames with collaborators, attach them to an issue or PR rather than
committing them.

## Operational SQLite database

The backend persists run history and system state in
`backend/outputs/karabuk_fwi.db`. That file is **not** in `data/`
and is **not** committed — it is created automatically on first boot.
See [`../../docs/SQLITE_GUIDE.md`](../../docs/SQLITE_GUIDE.md) for the
schema and migration rules.
