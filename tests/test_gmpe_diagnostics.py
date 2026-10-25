"""Focused tests for event-clustered uncertainty and GMPE diagnostics."""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "notebooks"))
diagnostics = importlib.import_module("07_gmpe_comparison")


def test_grouped_bootstrap_ci_is_deterministic_and_uses_event_clusters():
    # Event A has two records; event B one. Resampling events should keep both
    # A records together and produce the same interval for a fixed seed.
    residuals = np.array([-1.0, -1.0, 1.0])
    groups = np.array(["A", "A", "B"])
    first = diagnostics.grouped_bootstrap_mean_ci(residuals, groups, n_boot=200, seed=7)
    second = diagnostics.grouped_bootstrap_mean_ci(residuals, groups, n_boot=200, seed=7)
    assert first == second
    assert first is not None
    assert first[0] <= residuals.mean() <= first[1]


def test_grouped_bootstrap_ci_is_unavailable_for_one_event():
    assert diagnostics.grouped_bootstrap_mean_ci([0.1, 0.2], ["A", "A"], n_boot=20) is None


def test_grouped_bootstrap_ci_rejects_mismatched_inputs():
    try:
        diagnostics.grouped_bootstrap_mean_ci([0.1], ["A", "B"])
    except ValueError as exc:
        assert "equal length" in str(exc)
    else:
        raise AssertionError("expected ValueError for mismatched arrays")


def test_subgroup_diagnostics_uses_only_declared_available_columns(capsys):
    frame = pd.DataFrame({
        "event_id": [f"e{i}" for i in range(10)],
        "mw_estimate": np.linspace(4.1, 6.2, 10),
        "hypocentral_distance_km": np.linspace(10, 300, 10),
        "vs30_ms": np.linspace(200, 1100, 10),
    })
    diagnostics.subgroup_diagnostics(frame, np.linspace(-0.5, 0.5, 10), seed=5)
    output = capsys.readouterr().out
    assert "mw_estimate" in output
    assert "hypocentral_distance_km" in output
    assert "vs30_ms" in output
    assert "instrument_type" not in output
