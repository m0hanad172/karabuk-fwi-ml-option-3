"""
Walk-forward temporal cross-validation engine.

Generates out-of-fold (OOF) predictions with strict temporal ordering:
  Fold 1: train 2012–2015, predict 2016
  Fold 2: train 2012–2016, predict 2017
  ...
  Fold N: train 2012–2023, predict 2024

No future data ever leaks into training.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, clone


@dataclass
class WalkForwardFold:
    fold_id: int
    train_years: list[int]
    predict_year: int
    train_idx: np.ndarray
    predict_idx: np.ndarray


def generate_temporal_folds(
    df: pd.DataFrame,
    first_train_end: int = 2015,
    last_predict_year: int = 2024,
) -> list[WalkForwardFold]:
    """Generate expanding-window temporal folds."""
    years = sorted(df["year"].unique())
    min_year = min(years)
    folds = []
    fold_id = 0
    for predict_year in range(first_train_end + 1, last_predict_year + 1):
        if predict_year not in years:
            continue
        train_years = [y for y in years if min_year <= y <= predict_year - 1]
        train_mask = df["year"].isin(train_years)
        predict_mask = df["year"] == predict_year
        if train_mask.sum() == 0 or predict_mask.sum() == 0:
            continue
        folds.append(WalkForwardFold(
            fold_id=fold_id,
            train_years=train_years,
            predict_year=predict_year,
            train_idx=np.where(train_mask)[0],
            predict_idx=np.where(predict_mask)[0],
        ))
        fold_id += 1
    return folds


def walk_forward_oof_predictions(
    model: BaseEstimator,
    X: pd.DataFrame,
    y: np.ndarray,
    folds: list[WalkForwardFold],
    sample_weight_fn=None,
) -> pd.DataFrame:
    """
    Run walk-forward CV and return OOF predictions for all predict folds.

    Returns DataFrame with columns: [index, year, y_true, oof_pred]
    """
    records = []
    for fold in folds:
        m = clone(model)
        X_train = X.iloc[fold.train_idx]
        y_train = y[fold.train_idx]
        X_pred = X.iloc[fold.predict_idx]
        y_pred_true = y[fold.predict_idx]

        fit_params = {}
        if sample_weight_fn is not None:
            weights = sample_weight_fn(y_train)
            fit_params["model__sample_weight"] = weights

        m.fit(X_train, y_train, **fit_params)
        preds = m.predict(X_pred)

        for idx, true_val, pred_val in zip(
            fold.predict_idx, y_pred_true, preds
        ):
            records.append({
                "index": int(idx),
                "year": fold.predict_year,
                "y_true": float(true_val),
                "oof_pred": float(pred_val),
            })

    return pd.DataFrame(records)
