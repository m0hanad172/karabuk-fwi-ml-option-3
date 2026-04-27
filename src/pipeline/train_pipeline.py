"""
Full stacked training pipeline orchestrator.

Runs Stage 1, Stage 2, and the three-way comparison in sequence.
"""
from __future__ import annotations

import json
from configs.paths import METADATA_DIR
from src.models.stage1_regression import train_stage1
from src.models.stage2_classifier import train_stage2


def run_full_training() -> dict:
    """Run the complete stacked training pipeline."""
    print("=" * 60)
    print("PHASE 1: Stage 1 — Regression backbone")
    print("=" * 60)
    stage1_result = train_stage1()
    print(f"  OOF metrics: {stage1_result['oof_metrics']}")
    print(f"  Test metrics: {stage1_result['test_metrics']}")

    print()
    print("=" * 60)
    print("PHASE 1: Stage 2 — Stacked safety classifier")
    print("=" * 60)
    stage2_result = train_stage2()
    print(f"  Test metrics: {stage2_result['test_metrics']}")

    result = {
        "stage1": stage1_result,
        "stage2": stage2_result,
    }

    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    (METADATA_DIR / "full_training_summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print()
    print("Full training complete. Summary saved to models/metadata/full_training_summary.json")
    return result
