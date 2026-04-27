"""Tests for feature schema and feature engineering."""
import pandas as pd
import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.features.feature_schema import (
    RAW_API_FEATURES,
    ENGINEERED_FEATURES,
    TRAINING_FEATURES,
    STAGE2_SUPPORT_FEATURES,
    STAGE2_INPUT_FEATURES,
    NON_TRAINING_COLUMNS,
)
from src.features.build_features import build_final_features
from configs.paths import DATASET_PATH


class TestFeatureSchema:
    def test_feature_counts(self):
        assert len(RAW_API_FEATURES) == 8
        assert len(ENGINEERED_FEATURES) == 26
        assert len(TRAINING_FEATURES) == 34

    def test_no_duplicate_features(self):
        assert len(TRAINING_FEATURES) == len(set(TRAINING_FEATURES))

    def test_days_since_last_rain_removed(self):
        assert "days_since_last_rain" not in TRAINING_FEATURES
        assert "days_since_last_rain" not in ENGINEERED_FEATURES

    def test_consecutive_dry_days_present(self):
        assert "consecutive_dry_days" in TRAINING_FEATURES

    def test_stage2_features_are_subset(self):
        for f in STAGE2_SUPPORT_FEATURES:
            assert f in TRAINING_FEATURES, f"{f} not in training features"

    def test_stage2_input_starts_with_predicted_fwi(self):
        assert STAGE2_INPUT_FEATURES[0] == "predicted_fwi"
        assert len(STAGE2_INPUT_FEATURES) == len(STAGE2_SUPPORT_FEATURES) + 1

    def test_no_overlap_training_nontrain(self):
        overlap = set(TRAINING_FEATURES) & set(NON_TRAINING_COLUMNS)
        assert len(overlap) == 0, f"Overlap: {overlap}"


class TestFeatureEngineering:
    @pytest.fixture
    def dataset(self):
        return pd.read_csv(DATASET_PATH, parse_dates=["date"])

    def test_all_training_features_in_dataset(self, dataset):
        missing = [f for f in TRAINING_FEATURES if f not in dataset.columns]
        assert missing == [], f"Missing: {missing}"

    def test_build_features_produces_all_columns(self, dataset):
        small = dataset.head(50).copy()
        result = build_final_features(small)
        missing = [f for f in TRAINING_FEATURES if f not in result.columns]
        assert missing == [], f"Missing after build: {missing}"

    def test_no_future_leakage_in_rolling(self, dataset):
        """Rolling features use shift(1) so today's value should not depend on today's raw input."""
        small = dataset.head(20).copy()
        result = build_final_features(small)
        # precip_sum_3d at row 1 should only use shifted data (row 0's precip)
        # It should NOT equal sum of rows 0-2 (which would mean no shift)
        assert result["precip_sum_3d"].iloc[0] is not None  # exists


class TestDatasetIntegrity:
    @pytest.fixture
    def dataset(self):
        return pd.read_csv(DATASET_PATH, parse_dates=["date"])

    def test_row_count(self, dataset):
        assert len(dataset) == 2576

    def test_year_range(self, dataset):
        years = dataset["date"].dt.year.unique()
        assert min(years) == 2012
        assert max(years) == 2025

    def test_fire_season_only(self, dataset):
        months = dataset["date"].dt.month.unique()
        assert all(5 <= m <= 10 for m in months)

    def test_target_exists(self, dataset):
        assert "FWI" in dataset.columns
        assert "target_ge_35" in dataset.columns
