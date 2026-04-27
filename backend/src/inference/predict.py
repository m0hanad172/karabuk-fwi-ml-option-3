"""
Stacked inference pipeline for Option 3.

Flow: 34 features → Stage 1 (regression) → Stage 2 (classifier) → decision rule.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from configs.paths import STAGE1_DIR, STAGE2_DIR, METADATA_DIR
from src.features.feature_schema import TRAINING_FEATURES, STAGE2_SUPPORT_FEATURES, STAGE2_INPUT_FEATURES
from src.models.decision import stacked_decision
from configs.settings import DEFAULT_PROBABILITY_THRESHOLD, CLASS_THRESHOLD, NEAR_THRESHOLD


class StackedPredictor:
    """Loads model artifacts and runs the full stacked inference."""

    def __init__(self):
        self._stage1 = None
        self._stage2 = None
        self._prob_threshold = DEFAULT_PROBABILITY_THRESHOLD

    def _load_models(self):
        if self._stage1 is None:
            self._stage1 = joblib.load(STAGE1_DIR / "histgb_regressor.joblib")
        if self._stage2 is None:
            self._stage2 = joblib.load(STAGE2_DIR / "rf_classifier_stacked.joblib")
            meta_path = METADATA_DIR / "stage2_metadata.json"
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                self._prob_threshold = meta.get("probability_threshold", DEFAULT_PROBABILITY_THRESHOLD)

    def predict(self, feature_row: pd.DataFrame) -> dict:
        """
        Run full stacked prediction on a single feature row.

        Args:
            feature_row: DataFrame with at least the 34 TRAINING_FEATURES columns.

        Returns:
            Dict with predicted_fwi, high_risk_probability, high_risk_flag,
            decision_reason, and thresholds used.
        """
        self._load_models()

        X_stage1 = feature_row[TRAINING_FEATURES].copy()
        predicted_fwi = float(self._stage1.predict(X_stage1)[0])

        stage2_input = feature_row[STAGE2_SUPPORT_FEATURES].copy()
        stage2_input.insert(0, "predicted_fwi", predicted_fwi)
        high_risk_prob = float(self._stage2.predict_proba(stage2_input.values)[0, 1])

        flags = stacked_decision(
            np.array([predicted_fwi]),
            np.array([high_risk_prob]),
            high_threshold=CLASS_THRESHOLD,
            near_threshold=NEAR_THRESHOLD,
            prob_threshold=self._prob_threshold,
        )
        high_risk_flag = int(flags[0])

        if predicted_fwi >= CLASS_THRESHOLD:
            reason = f"predicted_fwi ({predicted_fwi:.1f}) >= {CLASS_THRESHOLD} threshold"
        elif predicted_fwi >= NEAR_THRESHOLD and high_risk_prob >= self._prob_threshold:
            reason = (
                f"Grey-zone rescue: predicted_fwi ({predicted_fwi:.1f}) in [{NEAR_THRESHOLD}, {CLASS_THRESHOLD}) "
                f"and probability ({high_risk_prob:.3f}) >= {self._prob_threshold}"
            )
        else:
            reason = f"predicted_fwi ({predicted_fwi:.1f}) below risk zone"

        return {
            "predicted_fwi": predicted_fwi,
            "high_risk_probability": high_risk_prob,
            "high_risk_flag": high_risk_flag,
            "decision_reason": reason,
            "thresholds": {
                "high_threshold": CLASS_THRESHOLD,
                "near_threshold": NEAR_THRESHOLD,
                "probability_threshold": self._prob_threshold,
            },
        }


# Module-level singleton for reuse across requests
_predictor: StackedPredictor | None = None


def get_predictor() -> StackedPredictor:
    global _predictor
    if _predictor is None:
        _predictor = StackedPredictor()
    return _predictor


def predict_from_features(feature_row: pd.DataFrame) -> dict:
    """Convenience function for stacked prediction."""
    return get_predictor().predict(feature_row)
