"""Entry point: run full stacked training pipeline."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline.train_pipeline import run_full_training

if __name__ == "__main__":
    run_full_training()
