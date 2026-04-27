"""Tests for the full stacked pipeline integrity."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from configs.paths import STAGE1_DIR, STAGE2_DIR, METADATA_DIR, OOF_DIR
from src.features.feature_schema import TRAINING_FEATURES, STAGE2_INPUT_FEATURES


class TestArtifactsExist:
    def test_stage1_model(self):
        assert (STAGE1_DIR / "histgb_regressor.joblib").exists()

    def test_stage2_model(self):
        assert (STAGE2_DIR / "rf_classifier_stacked.joblib").exists()

    def test_stage1_metadata(self):
        assert (METADATA_DIR / "stage1_metadata.json").exists()

    def test_stage2_metadata(self):
        assert (METADATA_DIR / "stage2_metadata.json").exists()

    def test_oof_predictions(self):
        assert (OOF_DIR / "stage1_oof_predictions.csv").exists()

    def test_test_predictions(self):
        assert (OOF_DIR / "stage1_test_predictions.csv").exists()
        assert (OOF_DIR / "stage2_test_predictions.csv").exists()


class TestEndToEndPipeline:
    def test_stage1_accepts_34_features(self):
        model = joblib.load(STAGE1_DIR / "histgb_regressor.joblib")
        dummy = pd.DataFrame(np.zeros((1, 34)), columns=TRAINING_FEATURES)
        pred = model.predict(dummy)
        assert pred.shape == (1,)

    def test_stage2_accepts_4_features(self):
        model = joblib.load(STAGE2_DIR / "rf_classifier_stacked.joblib")
        dummy = pd.DataFrame(np.zeros((1, 4)), columns=STAGE2_INPUT_FEATURES)
        prob = model.predict_proba(dummy)
        assert prob.shape == (1, 2)

    def test_stacked_inference_flow(self):
        """Full stacked flow: 34 features -> Stage 1 -> Stage 2 -> decision."""
        from src.models.decision import stacked_decision

        stage1 = joblib.load(STAGE1_DIR / "histgb_regressor.joblib")
        stage2 = joblib.load(STAGE2_DIR / "rf_classifier_stacked.joblib")

        dummy = pd.DataFrame(np.random.randn(5, 34), columns=TRAINING_FEATURES)
        pred_fwi = stage1.predict(dummy)
        assert pred_fwi.shape == (5,)

        stage2_input = dummy[["rh", "ws", "fuel_drying_rate"]].copy()
        stage2_input.insert(0, "predicted_fwi", pred_fwi)
        prob = stage2.predict_proba(stage2_input)[:, 1]
        assert prob.shape == (5,)

        flags = stacked_decision(pred_fwi, prob)
        assert flags.shape == (5,)
        assert set(flags).issubset({0, 1})

    def test_comparison_results_exist(self):
        import json
        path = METADATA_DIR / "three_way_comparison.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "regression_only" in data["decision_comparison"]
        assert "old_parallel" in data["decision_comparison"]
        assert "new_stacked" in data["decision_comparison"]
