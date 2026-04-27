"""Service layer for historical FWI analytics from the training dataset."""
from __future__ import annotations

import pandas as pd

from configs.paths import DATASET_PATH


def _load_dataset() -> pd.DataFrame:
    df = pd.read_csv(DATASET_PATH, parse_dates=["date"])
    return df[["date", "year", "month", "FWI", "target_ge_35"]].copy()


def get_analytics() -> dict:
    """Return pre-aggregated analytics for the frontend Historical Analytics tab."""
    df = _load_dataset()

    # --- Daily FWI time series (sampled: monthly averages for chart performance) ---
    monthly = (
        df.groupby(["year", "month"])
        .agg(mean_fwi=("FWI", "mean"), max_fwi=("FWI", "max"), high_risk_days=("target_ge_35", "sum"), total_days=("FWI", "count"))
        .reset_index()
    )
    monthly["date"] = pd.to_datetime(monthly[["year", "month"]].assign(day=15))
    monthly_series = [
        {"date": row.date.strftime("%Y-%m-%d"), "mean_fwi": round(row.mean_fwi, 2), "max_fwi": round(row.max_fwi, 2)}
        for row in monthly.itertuples()
    ]

    # --- Yearly stats ---
    yearly = (
        df.groupby("year")
        .agg(mean_fwi=("FWI", "mean"), max_fwi=("FWI", "max"), high_risk_days=("target_ge_35", "sum"), total_days=("FWI", "count"))
        .reset_index()
    )
    yearly_stats = [
        {
            "year": int(row.year),
            "mean_fwi": round(row.mean_fwi, 2),
            "max_fwi": round(row.max_fwi, 2),
            "high_risk_days": int(row.high_risk_days),
            "total_days": int(row.total_days),
        }
        for row in yearly.itertuples()
    ]

    # --- Seasonal (monthly average across all years, for seasonal profile) ---
    seasonal = (
        df.groupby("month")
        .agg(mean_fwi=("FWI", "mean"), max_fwi=("FWI", "max"), high_risk_days=("target_ge_35", "sum"), total_days=("FWI", "count"))
        .reset_index()
    )
    month_names = {5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct"}
    seasonal_profile = [
        {
            "month": int(row.month),
            "month_name": month_names.get(int(row.month), str(row.month)),
            "mean_fwi": round(row.mean_fwi, 2),
            "max_fwi": round(row.max_fwi, 2),
            "high_risk_days": int(row.high_risk_days),
            "total_days": int(row.total_days),
        }
        for row in seasonal.itertuples()
    ]

    # --- Year-over-year by month (for seasonal comparison chart) ---
    yoy = (
        df.groupby(["year", "month"])
        .agg(mean_fwi=("FWI", "mean"), high_risk_days=("target_ge_35", "sum"))
        .reset_index()
    )
    year_over_year = [
        {
            "year": int(row.year),
            "month": int(row.month),
            "month_name": month_names.get(int(row.month), str(row.month)),
            "mean_fwi": round(row.mean_fwi, 2),
            "high_risk_days": int(row.high_risk_days),
        }
        for row in yoy.itertuples()
    ]

    return {
        "dataset_range": {"start": df["date"].min().strftime("%Y-%m-%d"), "end": df["date"].max().strftime("%Y-%m-%d")},
        "total_records": len(df),
        "total_high_risk_days": int(df["target_ge_35"].sum()),
        "monthly_series": monthly_series,
        "yearly_stats": yearly_stats,
        "seasonal_profile": seasonal_profile,
        "year_over_year": year_over_year,
    }
