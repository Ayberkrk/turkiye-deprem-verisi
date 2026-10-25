"""Create and score a bounded, deterministic review sample for catalog matching.

This tool audits the pairwise threshold gate used by ``expand_catalog.py``. It
does not rerun or change the catalogue clustering algorithm. The review export
contains exact candidate pairs plus nearby hard negatives and leaves
``reviewer_label`` blank for human adjudication.

Examples::

    python scripts/review_catalog_matches.py export \
        --input data/processed/expanded_catalog_raw_cache.parquet \
        --output /tmp/catalog-review.csv
    # Fill reviewer_label with exactly ``match`` or ``non_match`` for every row.
    python scripts/review_catalog_matches.py score --input /tmp/catalog-review.csv

The export uses reservoir sampling per diagnostic stratum, so memory use is
bounded by strata_count * samples_per_stratum. Scoring reports weighted metrics
that account for the number of eligible pairs in each stratum.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd
from expand_catalog import (
    MAX_DISTANCE_KM,
    MAX_MAGNITUDE_DIFF,
    TIME_WINDOW_SEC,
    distance_threshold_km,
    haversine_km,
    match_score,
)

REQUIRED_COLUMNS = {"source", "source_event_id", "time_utc", "latitude", "longitude", "magnitude"}
REVIEW_LABELS = {"match", "non_match"}
EXPORT_COLUMNS = [
    "source_a", "source_event_id_a", "time_utc_a", "latitude_a", "longitude_a", "magnitude_a",
    "source_b", "source_event_id_b", "time_utc_b", "latitude_b", "longitude_b", "magnitude_b",
    "time_diff_sec", "distance_km", "distance_threshold_km", "distance_ratio", "magnitude_diff",
    "predicted_label", "candidate_score", "stratum", "stratum_population", "stratum_sample_size",
    "review_weight", "reviewer_label",
]


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".parquet", ".pq"}:
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Eksik zorunlu sütun(lar): {', '.join(sorted(missing))}")
    if frame.empty:
        raise ValueError("Girdi tablosu boş.")
    frame = frame.copy()
    frame["source"] = frame["source"].astype("string").str.strip().str.lower()
    frame["source_event_id"] = frame["source_event_id"].astype("string").str.strip()
    missing_identity = frame[["source", "source_event_id"]].isna().any().any()
    empty_source = (frame["source"] == "").any()
    empty_event_id = (frame["source_event_id"] == "").any()
    if missing_identity or empty_source or empty_event_id:
        raise ValueError("source ve source_event_id boş olamaz.")
    frame["time_utc"] = pd.to_datetime(frame["time_utc"], utc=True, errors="coerce")
    for column in ("latitude", "longitude", "magnitude"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[["time_utc", "latitude", "longitude", "magnitude"]].isna().any().any():
        raise ValueError("Zaman, koordinat ve büyüklük alanları geçerli sayısal/tarih değerleri içermeli.")
    values = frame[["latitude", "longitude", "magnitude"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Koordinat ve büyüklük alanlarında sonlu olmayan değer var.")
    if not frame["latitude"].between(-90, 90).all() or not frame["longitude"].between(-180, 180).all():
        raise ValueError("Enlem/boylam coğrafi aralık dışında.")
    # Stable tie-breaking makes sampling invariant to pandas' sort implementation.
    frame = frame.sort_values(["time_utc", "source", "source_event_id"], kind="mergesort").reset_index(drop=True)
    return frame


def _bucket(value: float, bounds: tuple[float, ...], names: tuple[str, ...]) -> str:
    for bound, name in zip(bounds, names, strict=True):
        if value <= bound:
            return name
    return names[-1]


def pair_stratum(time_diff: float, distance_ratio: float, magnitude_diff: float, same_source: bool) -> str:
    """Return a stable diagnostic stratum, including nearby gate misses."""
    time_bucket = _bucket(time_diff, (1, 5, 15, TIME_WINDOW_SEC, TIME_WINDOW_SEC * 2),
                          ("t00_01", "t01_05", "t05_15", "t15_30", "t30_60"))
    distance_bucket = _bucket(distance_ratio, (0.5, 1.0, 1.25, 2.0),
                              ("d00_050", "d050_100", "d100_125", "d125_200"))
    magnitude_bucket = _bucket(magnitude_diff, (0.25, 0.75, MAX_MAGNITUDE_DIFF, MAX_MAGNITUDE_DIFF * 2),
                               ("m00_025", "m025_075", "m075_150", "m150_300"))
    source_bucket = "same_source" if same_source else "cross_source"
    return "|".join((source_bucket, time_bucket, distance_bucket, magnitude_bucket))


def iter_review_pairs(frame: pd.DataFrame) -> Iterable[dict[str, object]]:
    """Yield threshold candidates and near misses within a 2x diagnostic envelope.

    The envelope is intentionally broader than the dedup gate so reviewed
    non-matches can reveal false negatives close to a threshold. It is not an
    exhaustive estimate of all possible missed matches outside that envelope.
    """
    times_ns = frame["time_utc"].astype("int64").to_numpy()
    lat = frame["latitude"].to_numpy(dtype=float)
    lon = frame["longitude"].to_numpy(dtype=float)
    mag = frame["magnitude"].to_numpy(dtype=float)
    sources = frame["source"].astype(str).to_numpy()
    ids = frame["source_event_id"].astype(str).to_numpy()
    times = frame["time_utc"].astype(str).to_numpy()

    max_dt_ns = int(TIME_WINDOW_SEC * 2 * 1e9)
    max_mag_diff = MAX_MAGNITUDE_DIFF * 2
    max_dist = MAX_DISTANCE_KM * 2
    for i in range(len(frame)):
        j = i + 1
        while j < len(frame) and times_ns[j] - times_ns[i] <= max_dt_ns:
            dt = (times_ns[j] - times_ns[i]) / 1e9
            dmag = abs(mag[i] - mag[j])
            if dmag <= max_mag_diff:
                threshold = distance_threshold_km(max(mag[i], mag[j]))
                distance = float(haversine_km(lat[i], lon[i], lat[j], lon[j]))
                ratio = distance / threshold
                if distance <= max_dist and ratio <= 2.0:
                    predicted = (
                        sources[i] != sources[j]
                        and dt <= TIME_WINDOW_SEC
                        and dmag <= MAX_MAGNITUDE_DIFF
                        and distance <= threshold
                    )
                    yield {
                        "source_a": sources[i], "source_event_id_a": ids[i], "time_utc_a": times[i],
                        "latitude_a": lat[i], "longitude_a": lon[i], "magnitude_a": mag[i],
                        "source_b": sources[j], "source_event_id_b": ids[j], "time_utc_b": times[j],
                        "latitude_b": lat[j], "longitude_b": lon[j], "magnitude_b": mag[j],
                        "time_diff_sec": dt, "distance_km": distance,
                        "distance_threshold_km": threshold, "distance_ratio": ratio,
                        "magnitude_diff": dmag,
                        "predicted_label": "match" if predicted else "non_match",
                        "candidate_score": match_score(dt, distance, dmag, threshold) if predicted else math.nan,
                        "stratum": pair_stratum(dt, ratio, dmag, sources[i] == sources[j]),
                    }
            j += 1


def export_review_sample(
    input_path: Path,
    output_path: Path,
    samples_per_stratum: int = 20,
    seed: int = 20261025,
) -> pd.DataFrame:
    """Write a deterministic reservoir sample and return the exported rows."""
    if samples_per_stratum < 1:
        raise ValueError("samples_per_stratum en az 1 olmalı.")
    frame = _read_table(input_path)
    rng = random.Random(seed)
    populations: dict[str, int] = defaultdict(int)
    reservoirs: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in iter_review_pairs(frame):
        stratum = str(row["stratum"])
        populations[stratum] += 1
        reservoir = reservoirs[stratum]
        count = populations[stratum]
        if len(reservoir) < samples_per_stratum:
            reservoir.append(row)
        else:
            index = rng.randrange(count)
            if index < samples_per_stratum:
                reservoir[index] = row

    rows = []
    for stratum in sorted(reservoirs):
        sample = reservoirs[stratum]
        population = populations[stratum]
        sample_size = len(sample)
        for row in sample:
            rows.append({
                **row,
                "stratum_population": population,
                "stratum_sample_size": sample_size,
                "review_weight": population / sample_size,
                "reviewer_label": "",
            })
    result = pd.DataFrame(rows, columns=EXPORT_COLUMNS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    return result


def score_review_file(input_path: Path, label_column: str = "reviewer_label") -> dict[str, object]:
    """Score pairwise threshold predictions against complete adjudicated labels."""
    frame = pd.read_csv(input_path)
    if frame.empty:
        raise ValueError("Skorlanacak inceleme tablosu boş.")
    required = {"predicted_label", label_column, "review_weight"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Skor için eksik sütun(lar): {', '.join(sorted(missing))}")
    predictions = frame["predicted_label"].astype("string").str.strip()
    labels = frame[label_column].astype("string").str.strip()
    invalid_predictions = sorted(set(predictions.dropna()) - REVIEW_LABELS)
    invalid_labels = sorted(set(labels.dropna()) - REVIEW_LABELS)
    if invalid_predictions or predictions.isna().any() or (predictions == "").any():
        raise ValueError(
            f"predicted_label her satırda yalnızca match/non_match olabilir; "
            f"geçersiz={invalid_predictions}, boş={int((predictions.isna() | (predictions == '')).sum())}"
        )
    if invalid_labels or labels.isna().any() or (labels == "").any():
        raise ValueError(
            f"{label_column} her satırda tam olarak match veya non_match olmalı; "
            f"geçersiz={invalid_labels}, boş={int((labels.isna() | (labels == '')).sum())}"
        )
    weights = pd.to_numeric(frame["review_weight"], errors="coerce")
    if weights.isna().any() or not np.isfinite(weights.to_numpy()).all() or (weights <= 0).any():
        raise ValueError("review_weight pozitif ve sonlu sayısal değer olmalı.")

    is_prediction = predictions.eq("match").to_numpy()
    is_label = labels.eq("match").to_numpy()
    weight_values = weights.to_numpy(dtype=float)
    tp = float(weight_values[is_prediction & is_label].sum())
    fp = float(weight_values[is_prediction & ~is_label].sum())
    fn = float(weight_values[~is_prediction & is_label].sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "metric_scope": "weighted pairwise threshold-gate review sample; not final cluster assignments",
        "rows_reviewed": len(frame),
        "weighted_true_positive": tp,
        "weighted_false_positive": fp,
        "weighted_false_negative": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    export_parser = subparsers.add_parser("export", help="Aday ve eşik yakını çiftlerden inceleme örneklemi üret")
    export_parser.add_argument("--input", type=Path, required=True, help="CSV veya Parquet ham katalog tablosu")
    export_parser.add_argument("--output", type=Path, required=True, help="İnceleme CSV çıktısı")
    export_parser.add_argument("--samples-per-stratum", type=int, default=20)
    export_parser.add_argument("--seed", type=int, default=20261025)
    score_parser = subparsers.add_parser(
        "score", help="İnceleme etiketlerini ağırlıklı precision/recall/F1 ile puanla"
    )
    score_parser.add_argument("--input", type=Path, required=True, help="Adjudike edilmiş inceleme CSV'si")
    score_parser.add_argument("--label-column", default="reviewer_label")
    args = parser.parse_args()
    if args.command == "export":
        sample = export_review_sample(args.input, args.output, args.samples_per_stratum, args.seed)
        print(json.dumps({"output": str(args.output), "rows": len(sample), "seed": args.seed}, ensure_ascii=False))
    else:
        print(json.dumps(score_review_file(args.input, args.label_column), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
