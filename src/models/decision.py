"""
Final stacked decision rule for Option 3.

Decision logic (regression-centered):
  1. If predicted_fwi >= HIGH_THRESHOLD (35) → High Risk
  2. Else if predicted_fwi >= NEAR_THRESHOLD (28) AND high_risk_probability >= prob_threshold → High Risk
  3. Else → Not High Risk

The classifier only acts as a safety net in the "grey zone" near the threshold.
Regression remains the authoritative signal.
"""
from __future__ import annotations

import numpy as np

from configs.settings import CLASS_THRESHOLD, NEAR_THRESHOLD, DEFAULT_PROBABILITY_THRESHOLD


def stacked_decision(
    predicted_fwi: np.ndarray,
    high_risk_probability: np.ndarray,
    high_threshold: float = CLASS_THRESHOLD,
    near_threshold: float = NEAR_THRESHOLD,
    prob_threshold: float = DEFAULT_PROBABILITY_THRESHOLD,
) -> np.ndarray:
    """
    Apply the stacked decision rule.

    Returns an integer array: 1 = High Risk, 0 = Not High Risk.
    """
    predicted_fwi = np.asarray(predicted_fwi, dtype=float)
    high_risk_probability = np.asarray(high_risk_probability, dtype=float)

    flags = np.zeros(len(predicted_fwi), dtype=int)

    # Rule 1: clear high-risk from regression
    flags[predicted_fwi >= high_threshold] = 1

    # Rule 2: grey-zone rescue by classifier
    grey_zone = (predicted_fwi >= near_threshold) & (predicted_fwi < high_threshold)
    classifier_says_high = high_risk_probability >= prob_threshold
    flags[grey_zone & classifier_says_high] = 1

    return flags


def regression_only_decision(
    predicted_fwi: np.ndarray,
    threshold: float = CLASS_THRESHOLD,
) -> np.ndarray:
    """Baseline: decision using only the regression prediction."""
    return (np.asarray(predicted_fwi, dtype=float) >= threshold).astype(int)


def parallel_decision(
    predicted_fwi: np.ndarray,
    high_risk_probability: np.ndarray,
    fwi_threshold: float = CLASS_THRESHOLD,
    prob_threshold: float = DEFAULT_PROBABILITY_THRESHOLD,
) -> np.ndarray:
    """
    Old parallel architecture decision (for comparison).

    Either the regression says high risk OR the classifier says high risk.
    """
    fwi_flag = np.asarray(predicted_fwi, dtype=float) >= fwi_threshold
    cls_flag = np.asarray(high_risk_probability, dtype=float) >= prob_threshold
    return (fwi_flag | cls_flag).astype(int)
