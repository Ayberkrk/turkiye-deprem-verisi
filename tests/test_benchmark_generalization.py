"""Focused offline tests for benchmark split scoring and event bootstrap."""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "notebooks"))
generalization = importlib.import_module("08_benchmark_generalization")


def _synthetic_frame(prefix, count, *, station=True):
    i = np.arange(count, dtype=float)
    frame = pd.DataFrame({
        "event_id": [f"{prefix}{int(j // 2)}" for j in i],
        "magnitude": 4.0 + i * 0.1,
        "hypocentral_distance_km": 10.0 + i * 4.0,
        "vs30_ms": 250.0 + i * 15.0,
        "pga_rotd50_g": 10 ** (-2.0 + i * 0.03),
    })
    if station:
        frame["station"] = [f"S{int(j % 3)}" for j in i]
    return frame


def test_group_bootstrap_metric_ci_is_deterministic_and_complete():
    y = np.array([0.0, 1.0, 2.0, 3.0])
    residuals = np.array([0.1, 0.1, -0.5, -0.5])
    groups = np.array(["A", "A", "B", "B"])
    first = generalization.grouped_bootstrap_metric_ci(y, residuals, groups, n_boot=100, seed=12)
    second = generalization.grouped_bootstrap_metric_ci(y, residuals, groups, n_boot=100, seed=12)
    assert first == second
    assert set(first) == {"rmse", "r2", "bias"}
    assert all(interval is not None and interval[0] <= interval[1] for interval in first.values())


def test_group_bootstrap_skips_missing_or_single_event_groups():
    assert generalization.grouped_bootstrap_metric_ci([1, 2], [0, 1], ["A", "A"]) is None
    assert generalization.grouped_bootstrap_metric_ci([1, 2], [0, 1], [None, None]) is None


def test_group_bootstrap_rejects_mismatched_arrays():
    with pytest.raises(ValueError, match="equal length"):
        generalization.grouped_bootstrap_metric_ci([1], [0, 1], ["A"])


def test_score_split_compares_fitted_model_and_handles_missing_station_column():
    result = generalization.score_split(
        _synthetic_frame("tr", 16, station=True),
        _synthetic_frame("te", 10, station=False),
        n_boot=100,
        seed=2,
    )
    assert result["train_counts"] == {"records": 16, "events": 8, "stations": 3}
    assert result["test_counts"] == {"records": 10, "events": 5, "stations": None}
    assert set(result["models"]) == {"naive_train_mean", "linear_ols"}
    assert result["models"]["linear_ols"]["rmse"] < result["models"]["naive_train_mean"]["rmse"]
    assert result["models"]["linear_ols"]["ci"]["rmse"] is not None


def test_score_split_reports_missing_required_schema_clearly():
    train = _synthetic_frame("tr", 8)
    test = _synthetic_frame("te", 8).drop(columns="vs30_ms")
    with pytest.raises(ValueError, match="vs30_ms"):
        generalization.score_split(train, test, n_boot=10)
