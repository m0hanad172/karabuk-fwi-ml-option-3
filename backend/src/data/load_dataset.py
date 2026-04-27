"""Dataset loading and temporal splitting for Karabuk FWI ML Option 3."""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

from src.features.feature_schema import TRAINING_FEATURES
from configs.settings import (
    TARGET_REGRESSION,
    TARGET_CLASSIFICATION,
    CLASS_THRESHOLD,
    FINAL_TEST_YEAR,
    WEIGHT_HIGH,
    WEIGHT_MID,
    WEIGHT_LOW,
)


def load_final_dataset(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"] = df["date"].dt.day
    if TARGET_CLASSIFICATION not in df.columns and TARGET_REGRESSION in df.columns:
        df[TARGET_CLASSIFICATION] = (df[TARGET_REGRESSION] >= CLASS_THRESHOLD).astype(int)
    return df


def validate_training_schema(df: pd.DataFrame) -> None:
    missing = [f for f in TRAINING_FEATURES if f not in df.columns]
    if missing:
        raise ValueError(f"Missing training features: {missing}")


def make_regression_xy(df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    validate_training_schema(df)
    X = df[TRAINING_FEATURES].copy()
    y = df[TARGET_REGRESSION].values.astype(float)
    return X, y


def make_classifier_xy(df: pd.DataFrame, features: list[str] | None = None) -> tuple[pd.DataFrame, np.ndarray]:
    features = features or TRAINING_FEATURES
    missing = [f for f in features if f not in df.columns]
    if missing:
        raise ValueError(f"Missing features for classifier: {missing}")
    X = df[features].copy()
    y = df[TARGET_CLASSIFICATION].values.astype(int)
    return X, y


def compute_sample_weights(y: np.ndarray) -> np.ndarray:
    return np.where(
        y >= CLASS_THRESHOLD, WEIGHT_HIGH,
        np.where(y >= 20, WEIGHT_MID, WEIGHT_LOW),
    )


def split_train_test(df: pd.DataFrame, test_year: int = FINAL_TEST_YEAR) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["year"] < test_year].copy()
    test = df[df["year"] == test_year].copy()
    return train, test
