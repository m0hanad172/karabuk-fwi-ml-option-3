"""Tests for the stacked inference pipeline."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.inference.predict import StackedPredictor, predict_from_features, get_predictor
from src.features.feature_schema import TRAINING_FEATURES
from configs.paths import DATASET_PATH


@pytest.fixture
def sample_row():
    """Load a real row from the dataset for realistic inference testing."""
    df = pd.read_csv(DATASET_PATH)
    return df.iloc[[100]].copy()


class TestStackedPredictor:
    def test_loads_models(self):
        p = StackedPredictor()
        p._load_models()
        assert p._stage1 is not None
        assert p._stage2 is not None

    def test_predict_returns_expected_keys(self, sample_row):
        result = predict_from_features(sample_row)
        assert "predicted_fwi" in result
        assert "high_risk_probability" in result
        assert "high_risk_flag" in result
        assert "decision_reason" in result
        assert "thresholds" in result

    def test_predict_types(self, sample_row):
        result = predict_from_features(sample_row)
        assert isinstance(result["predicted_fwi"], float)
        assert isinstance(result["high_risk_probability"], float)
        assert result["high_risk_flag"] in (0, 1)
        assert isinstance(result["decision_reason"], str)

    def test_probability_range(self, sample_row):
        result = predict_from_features(sample_row)
        assert 0.0 <= result["high_risk_probability"] <= 1.0

    def test_singleton_reuse(self):
        p1 = get_predictor()
        p2 = get_predictor()
        assert p1 is p2

    def test_decision_reason_not_empty(self, sample_row):
        result = predict_from_features(sample_row)
        assert len(result["decision_reason"]) > 0

    def test_thresholds_present(self, sample_row):
        result = predict_from_features(sample_row)
        t = result["thresholds"]
        assert "high_threshold" in t
        assert "near_threshold" in t
        assert "probability_threshold" in t
