"""Tests for the stacked decision rule."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.decision import stacked_decision, regression_only_decision, parallel_decision


class TestStackedDecision:
    def test_clear_high_risk(self):
        """FWI >= 35 should always be flagged regardless of classifier."""
        fwi = np.array([40.0, 50.0, 35.0])
        prob = np.array([0.0, 0.0, 0.0])  # classifier says low risk
        flags = stacked_decision(fwi, prob)
        np.testing.assert_array_equal(flags, [1, 1, 1])

    def test_clear_low_risk(self):
        """FWI < 28 should never be flagged regardless of classifier."""
        fwi = np.array([10.0, 20.0, 27.9])
        prob = np.array([0.99, 0.99, 0.99])  # classifier says high risk
        flags = stacked_decision(fwi, prob)
        np.testing.assert_array_equal(flags, [0, 0, 0])

    def test_grey_zone_rescue(self):
        """In grey zone (28-35), classifier rescue should activate."""
        fwi = np.array([30.0, 30.0, 28.0, 34.9])
        prob = np.array([0.50, 0.05, 0.15, 0.10])
        flags = stacked_decision(fwi, prob)
        # prob >= 0.10: rescued; prob < 0.10: not rescued
        np.testing.assert_array_equal(flags, [1, 0, 1, 1])

    def test_grey_zone_boundary(self):
        """Exact boundary values."""
        fwi = np.array([28.0, 27.999])
        prob = np.array([0.10, 0.10])
        flags = stacked_decision(fwi, prob)
        np.testing.assert_array_equal(flags, [1, 0])


class TestRegressionOnlyDecision:
    def test_threshold(self):
        fwi = np.array([34.9, 35.0, 35.1])
        flags = regression_only_decision(fwi)
        np.testing.assert_array_equal(flags, [0, 1, 1])


class TestParallelDecision:
    def test_or_logic(self):
        """Old parallel: flagged if EITHER model says high risk."""
        fwi = np.array([40.0, 10.0, 10.0, 40.0])
        prob = np.array([0.01, 0.50, 0.01, 0.50])
        flags = parallel_decision(fwi, prob, prob_threshold=0.10)
        np.testing.assert_array_equal(flags, [1, 1, 0, 1])
