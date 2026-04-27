"""
JSON-safe coercion for API responses.

FastAPI's default encoder does not handle:
  - pandas.Timestamp
  - numpy scalars (np.int64, np.float64, np.bool_)
  - datetime.date / datetime.datetime (dates only — FastAPI does datetimes)

Anything that flows out of the pipeline layer (raw_inputs from DataFrames,
feature_values, validation dicts) must be pushed through `to_json_safe`
before being returned as an API response, otherwise the client sees a
generic 500: "Object of type Timestamp is not JSON serializable".
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd


def to_json_safe(obj: Any) -> Any:
    """
    Recursively convert a Python object into something `json.dumps` and
    FastAPI can serialize without custom encoders.
    """
    # None / primitive JSON-native types
    if obj is None or isinstance(obj, (str, bool, int, float)):
        # Filter NaN/Inf floats → None (FastAPI rejects them by default)
        if isinstance(obj, float) and (pd.isna(obj) or not np.isfinite(obj)):
            return None
        return obj

    # pandas Timestamp / NaT
    if isinstance(obj, pd.Timestamp):
        if pd.isna(obj):
            return None
        return obj.isoformat()

    # datetime / date
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()

    # numpy scalar types
    if isinstance(obj, np.generic):
        try:
            val = obj.item()
        except Exception:
            return str(obj)
        if isinstance(val, float) and (pd.isna(val) or not np.isfinite(val)):
            return None
        return val

    # numpy arrays / pandas Series → list
    if isinstance(obj, (np.ndarray, pd.Series)):
        return [to_json_safe(v) for v in obj.tolist()]

    # pandas DataFrame → list of row dicts
    if isinstance(obj, pd.DataFrame):
        return [to_json_safe(r) for r in obj.to_dict(orient="records")]

    # Mapping
    if isinstance(obj, dict):
        return {str(k): to_json_safe(v) for k, v in obj.items()}

    # Iterable
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_json_safe(v) for v in obj]

    # Last resort: string repr so we never crash the response
    return str(obj)
