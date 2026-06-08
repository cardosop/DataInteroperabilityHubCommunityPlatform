#!/usr/bin/env python3
"""
281.B.8.4/8.5 — Capacity growth forecasting.

Linear regression on tenant count, API volume, storage. Produces
3-month and 6-month forecasts. Flags when forecast >70% of capacity.

Usage: python scripts/forecast_capacity.py [--ci]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Any


def _linear_regression(x: list[float], y: list[float]) -> tuple[float, float]:
    """Simple linear regression: y = slope * x + intercept."""
    n = len(x)
    if n < 2:
        return 0.0, y[0] if y else 0.0
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi * xi for xi in x)
    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept


def _forecast_months(months: int) -> list[int]:
    """Return month indices for forecast (1, 2, ..., months)."""
    return list(range(1, months + 1))


def _mock_historical_data() -> dict[str, list[float]]:
    """Sample historical data (real implementation reads from Prometheus)."""
    return {
        "tenant_count": [12, 14, 17, 20, 23, 25],
        "api_volume_daily": [50000, 55000, 62000, 70000, 78000, 85000],
        "storage_gb": [120, 140, 165, 190, 220, 250],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Capacity growth forecasting")
    parser.add_argument("--ci", action="store_true", help="CI mode: flag if forecast >70% capacity")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    historical = _mock_historical_data()
    months = list(range(1, len(historical["tenant_count"]) + 1))
    forecasts_3m: dict[str, Any] = {}
    forecasts_6m: dict[str, Any] = {}

    # Capacity limits
    limits = {
        "tenant_count": 50,
        "api_volume_daily": 200000,
        "storage_gb": 1000,
    }

    warnings: list[str] = []

    for metric, values in historical.items():
        slope, intercept = _linear_regression([float(m) for m in months], values)
        forecast_3 = slope * (len(months) + 3) + intercept
        forecast_6 = slope * (len(months) + 6) + intercept
        limit = limits[metric]
        pct_3 = (forecast_3 / limit) * 100
        pct_6 = (forecast_6 / limit) * 100

        forecasts_3m[metric] = {
            "forecast": round(forecast_3, 1),
            "pct_of_limit": round(pct_3, 1),
            "limit": limit,
        }
        forecasts_6m[metric] = {
            "forecast": round(forecast_6, 1),
            "pct_of_limit": round(pct_6, 1),
            "limit": limit,
        }

        # 281.B.8.5 — trigger expansion when >70% within 3 months
        if pct_3 > 70:
            warnings.append(f"{metric}: forecast at {pct_3:.1f}% of limit within 3 months")

        # 281.B.8.6 — flag >20% over budget
        if pct_6 > 100:
            warnings.append(f"{metric}: forecast exceeds limit within 6 months ({pct_6:.1f}%)")

    result = {
        "forecast_3m": forecasts_3m,
        "forecast_6m": forecasts_6m,
        "warnings": warnings,
        "generated_at": datetime.now().isoformat(),
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Capacity Forecast (3 months):")
        for metric, f in forecasts_3m.items():
            print(f"  {metric}: {f['forecast']} ({f['pct_of_limit']}% of {f['limit']})")
        print("\nCapacity Forecast (6 months):")
        for metric, f in forecasts_6m.items():
            print(f"  {metric}: {f['forecast']} ({f['pct_of_limit']}% of {f['limit']})")

        if warnings:
            print(f"\n⚠️  {len(warnings)} warning(s):")
            for w in warnings:
                print(f"  - {w}")

    if warnings and args.ci:
        print(f"\nCI warning: Capacity forecasts exceed thresholds.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
