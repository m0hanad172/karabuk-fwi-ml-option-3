"""Validate that a feature row has the expected columns and no critical NaN issues."""
from __future__ import annotations

import pandas as pd


def validate_feature_row(df: pd.DataFrame, expected_features: list[str]) -> dict:
    missing = [f for f in expected_features if f not in df.columns]
    present = [f for f in expected_features if f in df.columns]
    nan_cols = [f for f in present if df[f].isna().any()]
    return {
        "is_valid": len(missing) == 0 and len(nan_cols) == 0,
        "missing_features": missing,
        "nan_features": nan_cols,
        "checked": len(expected_features),
    }
