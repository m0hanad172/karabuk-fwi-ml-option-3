"""
Stage 2 — Safety support classifier.

Input: predicted_fwi (from Stage 1 OOF) + support features (rh, ws, fuel_drying_rate)
Output: high_risk_probability
Target: target_ge_35

Trained on OOF predictions from walk-forward CV (no leakage).
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from configs.paths import STAGE2_DIR, METADATA_DIR, OOF_DIR, DATASET_PATH
from configs.settings import CLASS_THRESHOLD, DEFAULT_PROBABILITY_THRESHOLD, FINAL_TEST_YEAR
from src.data.load_dataset import load_final_dataset
from src.features.feature_schema import STAGE2_SUPPORT_FEATURES, STAGE2_INPUT_FEATURES
from src.evaluation.metrics import classifier_metrics


def build_stage2_pipeline() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", RandomForestClassifier(
            n_estimators=200,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )),
    ])


def train_stage2(dataset_path: str | Path = DATASET_PATH) -> dict:
    """
    Train Stage 2 classifier on OOF predictions from Stage 1.

    Training data: rows with OOF predictions (2016-2024)
    Test evaluation: 2025 holdout using Stage 1's actual predictions
    """
    df = load_final_dataset(dataset_path)
    oof = pd.read_csv(OOF_DIR / "stage1_oof_predictions.csv")
    test_preds = pd.read_csv(OOF_DIR / "stage1_test_predictions.csv", parse_dates=["date"])

    # Build Stage 2 training set from OOF predictions
    train_df = df[df["year"] < FINAL_TEST_YEAR].copy().reset_index(drop=True)
    oof_rows = train_df.iloc[oof["index"].values].copy()
    oof_rows["predicted_fwi"] = oof["oof_pred"].values
    oof_rows["target_ge_35"] = (oof_rows["FWI"] >= CLASS_THRESHOLD).astype(int)

    X_train = oof_rows[STAGE2_INPUT_FEATURES].copy()
    y_train = oof_rows["target_ge_35"].values

    # Build Stage 2 test set from actual Stage 1 predictions on 2025
    test_df = df[df["year"] == FINAL_TEST_YEAR].copy().reset_index(drop=True)
    test_df["predicted_fwi"] = test_preds["predicted_fwi"].values
    X_test = test_df[STAGE2_INPUT_FEATURES].copy()
    y_test = test_df["target_ge_35"].values

    # Train
    model = build_stage2_pipeline()
    model.fit(X_train, y_train)

    # Evaluate
    prob_test = model.predict_proba(X_test)[:, 1]
    test_metrics = classifier_metrics(y_test, prob_test, DEFAULT_PROBABILITY_THRESHOLD)

    # Save artifacts
    STAGE2_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    model_path = STAGE2_DIR / "rf_classifier_stacked.joblib"
    joblib.dump(model, model_path)

    metadata = {
        "model_type": "RandomForestClassifier",
        "input_features": STAGE2_INPUT_FEATURES,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "probability_threshold": DEFAULT_PROBABILITY_THRESHOLD,
        "test_metrics": test_metrics,
    }
    meta_path = METADATA_DIR / "stage2_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    # Save test probabilities for downstream comparison
    test_pred_df = test_preds.copy()
    test_pred_df["high_risk_probability"] = prob_test
    test_pred_df.to_csv(OOF_DIR / "stage2_test_predictions.csv", index=False)

    return {
        "model_path": str(model_path),
        "test_metrics": test_metrics,
    }
