"""Monitoring / detection layer.

This package is the **detection-only** surface of the system:
  - live camera feeds (pc_camera, webcam)
  - drone feed (DJI Tello, optional hardware)
  - YOLO fire detection on each frame
  - fire-detection notifications

It is strictly separated from the Option 3 prediction pipeline
(`src/inference/`, `src/models/`, `src/pipeline/live_inference.py`).
Nothing in this package is allowed to read from or write to the FWI
prediction path or the run_history table. Fire detection here is an
operational alert only and never modifies `predicted_fwi` or
`high_risk_flag`.
"""
