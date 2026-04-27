# Models

This folder holds every trained artefact the backend loads at runtime.
All files here are **tracked in Git** (total size ~8 MB), so a fresh
clone of the repo is immediately runnable — no separate model download
step is required.

> The live backend resolves these paths through `configs/paths.py`.
> Never edit those constants — move the file alongside its sibling
> instead so the path stays stable.

## Layout

```
models/
├── stage1/
│   └── histgb_regressor.joblib       Stage 1 — HistGradientBoosting FWI regressor
├── stage2/
│   └── rf_classifier_stacked.joblib  Stage 2 — RandomForest "high-risk" classifier
├── metadata/
│   ├── stage1_metadata.json          Stage 1 train/test metrics (RMSE / MAE / R²)
│   ├── stage2_metadata.json          Stage 2 metrics + tuned probability threshold
│   └── three_way_comparison.json     Regression-only vs old-parallel vs new-stacked
└── fire_detection/
    └── best3.pt                      YOLOv8 fire detector (monitoring layer only)
```

## How each artefact is used

| File | Loaded by | Purpose |
|---|---|---|
| `stage1/histgb_regressor.joblib` | `src/inference/predict.py` (`StackedPredictor._load_models`) | Predicts continuous FWI from the 34 engineered features |
| `stage2/rf_classifier_stacked.joblib` | `src/inference/predict.py` | Stage 2 safety classifier — takes `predicted_fwi` + 3 support features and outputs `high_risk_probability` |
| `metadata/stage2_metadata.json` | `src/inference/predict.py` | Provides the tuned `probability_threshold` (default 0.10) used by the stacked decision rule |
| `metadata/stage1_metadata.json` | `/system/model` endpoint | Surfaced in the dashboard's System tab |
| `metadata/three_way_comparison.json` | `/system/model` endpoint | Powers the model comparison card in the dashboard |
| `fire_detection/best3.pt` | `src/monitoring/yolo_detector.py` | YOLOv8 weights for the monitoring/detection layer (camera + drone). **Strictly separate from the prediction pipeline.** |

## Inference contract

The Stacked v3 inference flow is:

```
34 engineered features
      │
      ▼
Stage 1  HistGradientBoostingRegressor  →  predicted_fwi
      │
      ▼
Stage 2  RandomForestClassifier
         inputs = [predicted_fwi, rh, ws, fuel_drying_rate]
         output = high_risk_probability
      │
      ▼
Stacked decision rule (src/models/decision.py)
      │
      ▼
high_risk_flag (0/1) + decision_reason
```

Concrete thresholds live in `configs/settings.py`:

- `CLASS_THRESHOLD = 35` — direct high-risk if `predicted_fwi ≥ 35`
- `NEAR_THRESHOLD = 28` — lower edge of the grey zone
- `DEFAULT_PROBABILITY_THRESHOLD = 0.10` — Stage 2 cutoff (overridden by `stage2_metadata.json`)

## Regenerating the artefacts

If you need to retrain (e.g. after extending the dataset), run the full
pipeline from the repo root:

```bash
python scripts/train.py
```

This calls `src/pipeline/train_pipeline.run_full_training`, which:

1. Loads `data/processed/Karabuk_FWI_Final_Features_GroupABC.csv`.
2. Walk-forward trains Stage 1 (2012 → 2024) and writes
   `data/oof/stage1_oof_predictions.csv`.
3. Trains Stage 2 on the OOF predictions + support features.
4. Overwrites every artefact in `stage1/`, `stage2/` and `metadata/`.

> ⚠️ `requirements.txt` pins `scikit-learn==1.6.1` deliberately — the
> stacked artefacts are pickled with that exact version. Upgrading
> sklearn without retraining will break `joblib.load`.

## YOLO detector

`fire_detection/best3.pt` is the same YOLOv8 weights file the legacy
detection prototype uses (see `legacy_detection_reference/`). Replacing
it with a re-trained YOLOv8 checkpoint requires no code change —
`src/monitoring/yolo_detector.py` reads the path from
`configs.paths.FIRE_DETECTION_MODEL_PATH`.

## Why these files are committed (and not Git-LFS)

The two `joblib` artefacts plus the YOLO weights are ~8 MB combined.
That is comfortably under GitHub's 100 MB hard limit and the 50 MB
soft warning, so plain Git tracking is the simplest, no-friction
option. If a future retraining run produces materially larger
artefacts (deep models, large gradient boosters), revisit this and
consider Git LFS.
