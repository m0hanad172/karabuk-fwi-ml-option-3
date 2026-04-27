"""
Stage 1 — Regression backbone.

Predicts continuous FWI from 34 training features.
Uses HistGradientBoostingRegressor with sample weighting.
Generates OOF predictions via walk-forward CV for Stage 2 training.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from configs.paths import STAGE1_DIR, METADATA_DIR, OOF_DIR, DATASET_PATH
from configs.settings import FINAL_TEST_YEAR
from src.data.load_dataset import (
    load_final_dataset,
    make_regression_xy,
    split_train_test,
    compute_sample_weights,
)
from src.evaluation.walk_forward import generate_temporal_folds, walk_forward_oof_predictions
from src.evaluation.metrics import regression_metrics


def build_stage1_pipeline() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", HistGradientBoostingRegressor(
            learning_rate=0.05,
            max_depth=6,
            max_iter=250,
            min_samples_leaf=10,
            random_state=42,
        )),
    ])


def train_stage1(dataset_path: str | Path = DATASET_PATH) -> dict:
    """
    Full Stage 1 training:
    1. Generate OOF predictions via walk-forward CV (for Stage 2)
    2. Train final model on full training pool
    3. Evaluate on 2025 holdout
    """
    df = load_final_dataset(dataset_path)
    train_df, test_df = split_train_test(df)
    X_train, y_train = make_regression_xy(train_df)
    X_test, y_test = make_regression_xy(test_df)

    # --- Walk-forward OOF predictions ---
    folds = generate_temporal_folds(train_df)
    model_template = build_stage1_pipeline()
    oof_df = walk_forward_oof_predictions(
        model=model_template,
        X=X_train,
        y=y_train,
        folds=folds,
        sample_weight_fn=compute_sample_weights,
    )

    OOF_DIR.mkdir(parents=True, exist_ok=True)
    oof_path = OOF_DIR / "stage1_oof_predictions.csv"
    oof_df.to_csv(oof_path, index=False)
    oof_metrics = regression_metrics(oof_df["y_true"], oof_df["oof_pred"])

    # --- Train final model on full training pool ---
    final_model = build_stage1_pipeline()
    weights = compute_sample_weights(y_train)
    final_model.fit(X_train, y_train, model__sample_weight=weights)

    # --- Evaluate on holdout ---
    test_pred = final_model.predict(X_test)
    test_metrics = regression_metrics(y_test, test_pred)

    # --- Save artifacts ---
    STAGE1_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    model_path = STAGE1_DIR / "histgb_regressor.joblib"
    joblib.dump(final_model, model_path)

    metadata = {
        "model_type": "HistGradientBoostingRegressor",
        "n_train": len(X_train),
        "n_test": len(X_test),
        "n_features": X_train.shape[1],
        "n_oof_folds": len(folds),
        "n_oof_rows": len(oof_df),
        "oof_metrics": oof_metrics,
        "test_metrics": test_metrics,
    }
    meta_path = METADATA_DIR / "stage1_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    # Save test predictions for downstream comparison
    test_pred_df = test_df[["date", "year", "FWI", "target_ge_35"]].copy()
    test_pred_df["predicted_fwi"] = test_pred
    test_pred_df.to_csv(OOF_DIR / "stage1_test_predictions.csv", index=False)

    return {
        "model_path": str(model_path),
        "oof_path": str(oof_path),
        "oof_metrics": oof_metrics,
        "test_metrics": test_metrics,
    }
