"""Evaluation metrics for regression and classification."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    mean_squared_error,
    mean_absolute_error,
    r2_score,
    precision_score,
    recall_score,
    f1_score,
    accuracy_score,
    confusion_matrix,
)


def regression_metrics(y_true, y_pred) -> dict:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return {
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
    }


def classifier_metrics(y_true, y_prob, threshold: float) -> dict:
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob)
    y_pred = (y_prob >= threshold).astype(int)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
    return {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "tn": int(tn),
    }


def decision_metrics(y_true_fwi, high_risk_flags, threshold: float = 35) -> dict:
    """Evaluate a binary high-risk decision against true FWI values."""
    y_true_binary = (np.asarray(y_true_fwi) >= threshold).astype(int)
    flags = np.asarray(high_risk_flags).astype(int)
    cm = confusion_matrix(y_true_binary, flags, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
    return {
        "recall": float(recall_score(y_true_binary, flags, zero_division=0)),
        "precision": float(precision_score(y_true_binary, flags, zero_division=0)),
        "f1": float(f1_score(y_true_binary, flags, zero_division=0)),
        "accuracy": float(accuracy_score(y_true_binary, flags)),
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "tn": int(tn),
        "missed_high_risk_days": int(fn),
        "false_alarms": int(fp),
    }
