"""Compare ground-motion benchmark generalization across event/station/time splits.

Uses only the small CSV split files under ``benchmarks/ground_motion``; it
does not load the processed parquet catalogue or waveform archive.
"""
import sys
from importlib import import_module
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))
baseline = import_module("02_ground_motion_baseline")

BENCH_DIR = Path("benchmarks/ground_motion")
BOOTSTRAP_REPLICATES = 1000
BOOTSTRAP_SEED = 20261025


def _metrics(y_true, residuals):
    y_true = np.asarray(y_true, dtype=float)
    residuals = np.asarray(residuals, dtype=float)
    rmse = float(np.sqrt(np.mean(residuals ** 2)))
    ss_total = float(np.sum((y_true - y_true.mean()) ** 2))
    r2 = float(1.0 - np.sum(residuals ** 2) / ss_total) if ss_total > 0 else float("nan")
    return {"rmse": rmse, "r2": r2, "bias": float(np.mean(residuals))}


def grouped_bootstrap_metric_ci(y_true, residuals, groups, *, n_boot=BOOTSTRAP_REPLICATES,
                                seed=BOOTSTRAP_SEED, confidence=0.95):
    """Percentile CI for RMSE, R², and bias from event-cluster resampling.

    Every sampled event contributes all of its records. Returns ``None`` if
    event IDs are unavailable or fewer than two distinct events are present.
    """
    y_true = np.asarray(y_true, dtype=float)
    residuals = np.asarray(residuals, dtype=float)
    groups = np.asarray(groups)
    if any(a.ndim != 1 for a in (y_true, residuals, groups)) or not (
        len(y_true) == len(residuals) == len(groups)
    ):
        raise ValueError("y_true, residuals, and groups must be 1-D arrays of equal length")
    if n_boot < 1:
        raise ValueError("n_boot must be positive")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")
    if len(groups) == 0 or pd.isna(groups).any():
        return None

    _, inverse = np.unique(groups, return_inverse=True)
    n_groups = int(inverse.max() + 1)
    if n_groups < 2:
        return None
    group_y = [y_true[inverse == i] for i in range(n_groups)]
    group_residuals = [residuals[inverse == i] for i in range(n_groups)]
    rng = np.random.default_rng(seed)
    samples = {key: [] for key in ("rmse", "r2", "bias")}
    for _ in range(n_boot):
        chosen = rng.integers(0, n_groups, size=n_groups)
        y = np.concatenate([group_y[i] for i in chosen])
        residual = np.concatenate([group_residuals[i] for i in chosen])
        metrics = _metrics(y, residual)
        for key, value in metrics.items():
            if np.isfinite(value):
                samples[key].append(value)

    tail = (1.0 - confidence) / 2.0
    intervals = {}
    for key, values in samples.items():
        if values:
            low, high = np.quantile(values, [tail, 1.0 - tail])
            intervals[key] = (float(low), float(high))
        else:
            intervals[key] = None
    return intervals


def _counts(frame: pd.DataFrame):
    return {
        "records": len(frame),
        "events": int(frame["event_id"].nunique()) if "event_id" in frame else None,
        "stations": int(frame["station"].nunique()) if "station" in frame else None,
    }


def score_split(train_frame: pd.DataFrame, test_frame: pd.DataFrame, *, n_boot=BOOTSTRAP_REPLICATES,
                seed=BOOTSTRAP_SEED):
    """Fit the existing OLS baseline and score it against train-mean baseline."""
    required = {"magnitude", "hypocentral_distance_km", "vs30_ms", baseline.TARGET}
    for label, frame in (("train", train_frame), ("test", test_frame)):
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{label} split is missing required columns: {', '.join(sorted(missing))}")
    train = baseline._prepare(train_frame)
    test = baseline._prepare(test_frame)
    if train.empty or test.empty:
        raise ValueError("train and test splits must contain usable positive PGA records")

    coefs = baseline._fit_ols(train)
    y_train = train["log_pga_g"].to_numpy()
    y_test = test["log_pga_g"].to_numpy()
    predictions = {
        "naive_train_mean": np.full(len(test), y_train.mean()),
        "linear_ols": baseline._predict(test, coefs),
    }
    result = {"train_counts": _counts(train), "test_counts": _counts(test), "models": {}}
    groups = test["event_id"].to_numpy() if "event_id" in test else None
    for name, predicted in predictions.items():
        residuals = y_test - predicted
        model_result = _metrics(y_test, residuals)
        model_result["ci"] = (grouped_bootstrap_metric_ci(
            y_test, residuals, groups, n_boot=n_boot, seed=seed
        ) if groups is not None else None)
        result["models"][name] = model_result
    return result


def _report(name, train_path: Path, test_path: Path):
    result = score_split(pd.read_csv(train_path), pd.read_csv(test_path))
    train_counts, test_counts = result["train_counts"], result["test_counts"]
    print(f"\n=== {name} ===")
    print("train: " + _format_counts(train_counts))
    print("test:  " + _format_counts(test_counts))
    for model, values in result["models"].items():
        ci = values["ci"]
        rmse_ci = "yok" if ci is None or ci["rmse"] is None else f"[{ci['rmse'][0]:.3f}, {ci['rmse'][1]:.3f}]"
        r2_ci = "yok" if ci is None or ci["r2"] is None else f"[{ci['r2'][0]:.3f}, {ci['r2'][1]:.3f}]"
        print(f"{model}: RMSE={values['rmse']:.3f} (95% olay-bootstrap GA {rmse_ci}), "
              f"R²={values['r2']:.3f} (GA {r2_ci}), bias={values['bias']:+.3f}")
    return result


def _format_counts(counts):
    events = "n/a" if counts["events"] is None else str(counts["events"])
    stations = "n/a" if counts["stations"] is None else str(counts["stations"])
    return f"kayıt={counts['records']}, olay={events}, istasyon={stations}"


def main():
    cases = [
        ("event-based", BENCH_DIR / "train.csv", BENCH_DIR / "test.csv"),
        ("holdout_by_station", BENCH_DIR / "holdout_by_station/train.csv",
         BENCH_DIR / "holdout_by_station/test.csv"),
        ("holdout_by_time", BENCH_DIR / "holdout_by_time/train.csv",
         BENCH_DIR / "holdout_by_time/test.csv"),
    ]
    for name, train_path, test_path in cases:
        if not train_path.exists() or not test_path.exists():
            print(f"{name}: train/test CSV eksik, atlandı.")
            continue
        _report(name, train_path, test_path)


if __name__ == "__main__":
    main()
