# Models

This folder holds every trained artefact the backend loads at runtime.
The active runtime artefacts are tracked in Git, so a fresh clone of the
repo is immediately runnable with no separate model download step.

The live backend resolves these paths through `configs/paths.py`.

## Layout

```text
models/
  stage1/
    histgb_regressor.joblib       Stage 1 - HistGradientBoosting FWI regressor
  stage2/
    rf_classifier_stacked.joblib  Stage 2 - RandomForest high-risk classifier
  metadata/
    stage1_metadata.json          Stage 1 train/test metrics
    stage2_metadata.json          Stage 2 metrics + probability threshold
    three_way_comparison.json     Regression-only vs old-parallel vs new-stacked
  fire_detection/
    best.pt                       Active YOLO fire/smoke detector
    best3.pt                      Legacy detector weights
    best4.pt                      Legacy detector weights
```

## How Each Artefact Is Used

| File | Loaded by | Purpose |
|---|---|---|
| `stage1/histgb_regressor.joblib` | `src/inference/predict.py` | Predicts continuous FWI from the 34 engineered features. |
| `stage2/rf_classifier_stacked.joblib` | `src/inference/predict.py` | Stage 2 safety classifier; takes `predicted_fwi` plus 3 support features and outputs `high_risk_probability`. |
| `metadata/stage2_metadata.json` | `src/inference/predict.py` | Provides the tuned `probability_threshold` used by the stacked decision rule. |
| `metadata/stage1_metadata.json` | `/system/model` endpoint | Surfaced in the dashboard's System tab. |
| `metadata/three_way_comparison.json` | Dashboard/model docs | Records regression-only vs old-parallel vs new-stacked comparison. |
| `fire_detection/best.pt` | `src/monitoring/yolo_detector.py` | Active YOLO fire/smoke detector for the camera and drone monitoring layer. Strictly separate from the prediction pipeline. |

## Inference Contract

The Stacked v3 inference flow is:

```text
34 engineered features
  -> Stage 1 HistGradientBoostingRegressor
  -> predicted_fwi
  -> Stage 2 RandomForestClassifier
     inputs = [predicted_fwi, rh, ws, fuel_drying_rate]
  -> high_risk_probability
  -> stacked decision rule
  -> high_risk_flag (0/1) + decision_reason
```

Concrete thresholds live in `configs/settings.py`:

- `CLASS_THRESHOLD = 35`: direct high-risk if `predicted_fwi >= 35`
- `NEAR_THRESHOLD = 28`: lower edge of the grey zone
- `DEFAULT_PROBABILITY_THRESHOLD = 0.10`: Stage 2 cutoff, overridden by `stage2_metadata.json` if present

## Regenerating The Artefacts

If you need to retrain the wildfire risk models after extending the
dataset, run the full pipeline from the backend folder:

```bash
python scripts/train.py
```

This calls `src/pipeline/train_pipeline.run_full_training`, which:

1. Loads `data/processed/Karabuk_FWI_Final_Features_GroupABC.csv`.
2. Walk-forward trains Stage 1 and writes `data/oof/stage1_oof_predictions.csv`.
3. Trains Stage 2 on the OOF predictions plus support features.
4. Overwrites artefacts in `stage1/`, `stage2/`, and `metadata/`.

`requirements.txt` pins `scikit-learn==1.6.1` deliberately. The stacked
artefacts are pickled with that exact version; upgrading sklearn without
retraining can break `joblib.load`.

## YOLO Detector

`fire_detection/best.pt` is the official active YOLO fire/smoke
detector. It supports two classes, `fire` and `smoke`. Runtime detection
normalises Fire / fire / flame aliases to `fire`, normalises Smoke /
smoke to `smoke`, and preserves the resulting label in the live overlay,
SQLite alert storage, and Detection Alerts interface.

The active fire/smoke detector is `best.pt`. Older detector weights are
kept only as legacy references.

Replacing the active checkpoint in the future requires updating
`configs.paths.FIRE_DETECTION_MODEL_PATH`.

## Why These Files Are Committed

The two `joblib` artefacts and active YOLO weights are still below
GitHub's hard file-size limit, so plain Git tracking is the simplest
option. If a future retraining run produces materially larger artefacts,
revisit this and consider Git LFS.
