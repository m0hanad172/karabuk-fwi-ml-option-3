# Phase 1 Summary — ML Core

## What Was Built

| Module | File | Purpose |
|---|---|---|
| Feature schema | `src/features/feature_schema.py` | 34 locked training features, Stage 2 support set defined |
| Feature engineering | `src/features/build_features.py` | Adapted from old project, `days_since_last_rain` duplicate removed |
| Feature validator | `src/features/feature_validator.py` | Runtime validation for inference |
| Dataset loader | `src/data/load_dataset.py` | Temporal splits, X/y extraction, sample weights |
| Walk-forward CV | `src/evaluation/walk_forward.py` | 9 expanding-window temporal folds, OOF generation |
| Evaluation metrics | `src/evaluation/metrics.py` | Regression, classifier, and decision-level metrics |
| Stage 1 regression | `src/models/stage1_regression.py` | HistGradientBoostingRegressor + walk-forward OOF |
| Stage 2 classifier | `src/models/stage2_classifier.py` | RandomForestClassifier on OOF predictions + support features |
| Decision rule | `src/models/decision.py` | Stacked, regression-only, and parallel decision functions |
| Training pipeline | `src/pipeline/train_pipeline.py` | Full orchestrator (Stage 1 + Stage 2) |
| Entry script | `scripts/train.py` | CLI entry point for training |
| Tests | `tests/` (4 files, 38 tests) | Schema, leakage, decision logic, stacking integrity |

---

## Final Locked Architecture

### Stage 1 — Regression Backbone
- **Model:** HistGradientBoostingRegressor (lr=0.05, depth=6, 250 iterations)
- **Input:** 34 training features (8 raw API + 26 engineered)
- **Output:** `predicted_fwi` (continuous)
- **Sample weights:** FWI >= 35 → 4x, FWI >= 20 → 2x, else 1x
- **OOF generation:** Walk-forward CV, 9 folds (train 2012-2015 → predict 2016, expanding to train 2012-2023 → predict 2024), 1656 OOF rows

### Stage 2 — Safety Support Classifier
- **Model:** RandomForestClassifier (200 trees, balanced class weights)
- **Input:** `predicted_fwi` + `rh` + `ws` + `fuel_drying_rate` (4 features)
- **Output:** `high_risk_probability`
- **Training data:** OOF predictions from Stage 1 (no leakage)

### Final Decision Rule
```
if predicted_fwi >= 35         → High Risk
elif predicted_fwi >= 28 AND
     high_risk_probability >= 0.10 → High Risk  (grey-zone rescue)
else                           → Not High Risk
```

---

## Final Stage 2 Support Features

Locked after empirical ablation on 2024 validation data:

| Candidate set | Recall | Precision | F1 |
|---|---|---|---|
| predicted_fwi alone | 1.000 | 0.286 | 0.444 |
| + rh | 1.000 | 0.250 | 0.400 |
| + temperature, rh | 1.000 | 0.316 | 0.480 |
| **+ rh, ws, fuel_drying_rate** | **1.000** | **0.333** | **0.500** |
| + all 6 candidates | 1.000 | 0.300 | 0.462 |

**Winner:** `rh`, `ws`, `fuel_drying_rate` — best precision at perfect recall, physically meaningful (humidity drives drying, wind drives spread, fuel drying rate is their combined effect).

---

## Key Metrics

### Stage 1 Regression (2025 holdout)
| Metric | Value |
|---|---|
| RMSE | 7.259 |
| MAE | 5.098 |
| R² | 0.819 |

### Three-Way Decision Comparison (2025 holdout, 50 high-risk days out of 184)

| Architecture | Recall | Precision | F1 | Accuracy | Missed days | False alarms |
|---|---|---|---|---|---|---|
| Regression-only | 0.260 | 1.000 | 0.413 | 0.799 | 37 | 0 |
| Old parallel | 0.840 | 0.955 | 0.894 | 0.946 | 8 | 2 |
| **New stacked** | **0.880** | **0.898** | **0.889** | **0.940** | **6** | **5** |

### Grey Zone Analysis
- Days in grey zone (28 <= predicted_fwi < 35): 39
- Rescued by classifier: 36
- Of which truly high-risk: 31

---

## Key Conclusions

1. **Regression alone is not enough.** It misses 37/50 dangerous days — the regressor systematically underestimates in the high-FWI tail. A support layer is essential.

2. **Stacked beats parallel on the safety metric that matters most.** The new stacked design catches 44/50 dangerous days vs 42/50 for old parallel. Two fewer missed dangerous days.

3. **The precision trade-off is acceptable.** 5 false alarms (stacked) vs 2 (parallel) is a worthwhile trade for a safety-first system. Extra checking on 3 safe days is far cheaper than missing 2 truly dangerous days.

4. **Grey-zone rescue is the mechanism.** 31 truly high-risk days were correctly caught by the classifier in the 28–35 band where the regressor underestimated.

5. **Walk-forward OOF is sound.** 38/38 tests pass, including explicit no-leakage verification. The stacking is methodologically clean.

6. **The architecture is academically defensible.** Regression is the scientific core; classifier is a documented safety layer with empirically selected features and a clear decision rule.
