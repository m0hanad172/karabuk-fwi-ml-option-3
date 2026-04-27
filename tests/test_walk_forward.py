"""Tests for walk-forward CV engine — no leakage guarantee."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluation.walk_forward import generate_temporal_folds, walk_forward_oof_predictions
from src.data.load_dataset import load_final_dataset, split_train_test, make_regression_xy
from configs.paths import DATASET_PATH


@pytest.fixture
def train_data():
    df = load_final_dataset(DATASET_PATH)
    train, _ = split_train_test(df)
    return train


class TestFoldGeneration:
    def test_correct_number_of_folds(self, train_data):
        folds = generate_temporal_folds(train_data)
        # 2016 through 2024 = 9 folds
        assert len(folds) == 9

    def test_no_temporal_leakage(self, train_data):
        """Train years must always be strictly before predict year."""
        folds = generate_temporal_folds(train_data)
        for fold in folds:
            assert all(y < fold.predict_year for y in fold.train_years), (
                f"Fold {fold.fold_id}: train years {fold.train_years} overlap predict year {fold.predict_year}"
            )

    def test_expanding_window(self, train_data):
        folds = generate_temporal_folds(train_data)
        prev_size = 0
        for fold in folds:
            assert len(fold.train_idx) > prev_size, (
                f"Fold {fold.fold_id}: training set did not expand"
            )
            prev_size = len(fold.train_idx)

    def test_no_index_overlap(self, train_data):
        """Train and predict indices must never overlap within a fold."""
        folds = generate_temporal_folds(train_data)
        for fold in folds:
            overlap = set(fold.train_idx) & set(fold.predict_idx)
            assert len(overlap) == 0, (
                f"Fold {fold.fold_id}: {len(overlap)} overlapping indices"
            )

    def test_predict_indices_cover_correct_year(self, train_data):
        folds = generate_temporal_folds(train_data)
        for fold in folds:
            predict_years = train_data.iloc[fold.predict_idx]["year"].unique()
            assert len(predict_years) == 1
            assert predict_years[0] == fold.predict_year


class TestOOFPredictions:
    def test_oof_file_exists(self):
        from configs.paths import OOF_DIR
        oof_path = OOF_DIR / "stage1_oof_predictions.csv"
        assert oof_path.exists(), "OOF predictions file not found"

    def test_oof_no_leakage(self, train_data):
        """Verify OOF predictions only exist for predict-year rows, not training rows."""
        from configs.paths import OOF_DIR
        oof = pd.read_csv(OOF_DIR / "stage1_oof_predictions.csv")
        folds = generate_temporal_folds(train_data)

        # All OOF indices should come from predict folds only
        all_predict_indices = set()
        for fold in folds:
            all_predict_indices.update(fold.predict_idx.tolist())

        oof_indices = set(oof["index"].tolist())
        assert oof_indices.issubset(all_predict_indices), "OOF contains indices from training folds"

    def test_oof_years_match_folds(self, train_data):
        from configs.paths import OOF_DIR
        oof = pd.read_csv(OOF_DIR / "stage1_oof_predictions.csv")
        expected_years = set(range(2016, 2025))  # 2016 through 2024
        actual_years = set(oof["year"].unique())
        assert actual_years == expected_years
