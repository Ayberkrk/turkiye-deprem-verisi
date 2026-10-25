"""Build a bounded-memory manifest for a generated dataset release.

The manifest records hashes of the published artifacts and source/license
references. It describes provenance and restrictions; it does not grant a
license to any source data.

Usage (from repository root):
    python scripts/build_provenance.py [--skip-isc-picks]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

CHUNK_SIZE = 1024 * 1024
PROCESSED = Path("data/processed")
MANIFEST_PATH = PROCESSED / "provenance_manifest.json"

SOURCE_REFERENCES: list[dict[str, Any]] = [
    {
        "source": "USGS ComCat",
        "status": "included",
        "license_classification": "public_domain",
        "license_reference": "https://earthquake.usgs.gov/data/comcat/",
        "lineage": [
            {"file": "data/processed/usgs_catalog_turkey.parquet", "columns": ["event_id", "source"]},
            {"file": "data/processed/expanded_catalog_raw_cache.parquet", "columns": ["source", "source_event_id"]},
            {"file": "data/processed/event_id_cluster_map.csv", "columns": ["source", "source_event_id"]},
            {"file": "data/processed/turkiye_deprem_katalogu_genisletilmis.parquet", "columns": ["reported_by"]},
        ],
    },
    {
        "source": "EMSC",
        "status": "included",
        "license_classification": "unclear",
        "license_reference": "https://www.seismicportal.eu/terms.html",
        "lineage": [
            {"file": "data/processed/expanded_catalog_raw_cache.parquet", "columns": ["source", "source_event_id"]},
            {"file": "data/processed/event_id_cluster_map.csv", "columns": ["source", "source_event_id"]},
            {"file": "data/processed/turkiye_deprem_katalogu_genisletilmis.parquet", "columns": ["reported_by"]},
        ],
    },
    {
        "source": "ISC Bulletin / FDSN event service",
        "status": "included",
        "license_classification": "attribution_required_bulk_redistribution_terms_unspecified",
        "license_reference": "https://www.isc.ac.uk/iscbulletin/citing.php",
        "lineage": [
            {"file": "data/processed/expanded_catalog_raw_cache.parquet", "columns": ["source", "source_event_id"]},
            {"file": "data/processed/event_id_cluster_map.csv", "columns": ["source", "source_event_id"]},
            {"file": "data/processed/turkiye_deprem_katalogu_genisletilmis.parquet", "columns": ["reported_by"]},
            {"file": "data/processed/isc_analyst_picks.csv", "columns": ["source_event_id", "source"]},
        ],
    },
    {
        "source": "KOERI / ORFEUS-EIDA",
        "status": "included",
        "license_classification": "noncommercial_reuse_restricted",
        "license_reference": "https://www.orfeus-eu.org/data/eida/acknowledgements/",
        "lineage": [
            {"file": "data/processed/koeri_stations.csv", "columns": ["station"]},
            {"file": "data/processed/koeri_channels.csv", "columns": ["station", "channel"]},
            {
                "file": "data/processed/waveform_fetch_log.csv",
                "columns": ["event_id", "station", "event_source", "file"],
            },
            {"file": "data/processed/waveform_features.csv", "columns": ["event_id", "station", "file"]},
            {"file": "data/processed/waveforms/", "columns": []},
        ],
    },
    {
        "source": "USGS Global Vs30 Mosaic",
        "status": "included",
        "license_classification": "public_domain",
        "license_reference": "https://earthquake.usgs.gov/arcgis/rest/services/eq/vs30_mosaic/MapServer",
        "lineage": [
            {"file": "data/processed/koeri_stations.csv", "columns": ["station", "vs30_ms", "nehrp_site_class"]}
        ],
    },
]

SOURCE_QUERY_CONFIG: dict[str, Any] = {
    "USGS ComCat": {
        "service": "https://earthquake.usgs.gov/fdsnws/event/1/query",
        "format": "geojson",
        "bbox": {"minlatitude": 35.0, "maxlatitude": 43.0, "minlongitude": 25.0, "maxlongitude": 45.5},
        "start_year": 1990,
        "end_year_inclusive": 2026,
        "minimum_magnitude": 3.0,
        "time_query": "one request per year, Jan 1 through Dec 31",
    },
    "EMSC": {
        "fdsn_alias": "EMSC",
        "endpoint_resolution": "ObsPy FDSN routing for alias EMSC",
        "bbox": {"minlatitude": 35.0, "maxlatitude": 43.0, "minlongitude": 25.0, "maxlongitude": 45.5},
        "start_year": 1990,
        "end_year_inclusive": 2026,
        "minimum_magnitude": 3.0,
        "time_query": "one request per year, Jan 1 through Dec 31",
    },
    "ISC Bulletin / FDSN event service": {
        "fdsn_alias": "ISC",
        "endpoint_resolution": "ObsPy FDSN routing for alias ISC",
        "bbox": {"minlatitude": 35.0, "maxlatitude": 43.0, "minlongitude": 25.0, "maxlongitude": 45.5},
        "start_year": 1990,
        "end_year_inclusive": 2026,
        "minimum_magnitude": 3.0,
        "time_query": "one request per year, Jan 1 through Dec 31",
    },
    "KOERI / ORFEUS-EIDA": {
        "fdsn_alias": "KOERI",
        "endpoint_resolution": "ObsPy FDSN routing for alias KOERI",
        "network": "KO",
        "event_filter": "mw_estimate when available, otherwise catalog magnitude >= 4.5",
        "station_candidates_max": 12,
        "successful_stations_target": 4,
        "maximum_event_station_distance_km": 400,
        "waveform_window_seconds": {"before_event": 10, "after_event": 200},
        "channel_activity_check": "channel-group active interval from koeri_channels.csv",
    },
    "USGS Global Vs30 Mosaic": {
        "service": "https://earthquake.usgs.gov/arcgis/rest/services/eq/vs30_mosaic/MapServer/identify",
        "query_coordinates": "each KOERI station latitude/longitude, one point identify request",
    },
}

BASE_OUTPUTS = [
    "data/processed/usgs_catalog_turkey.parquet",
    "data/processed/turkiye_deprem_katalogu_genisletilmis.parquet",
    "data/processed/turkiye_deprem_veriseti_v3.parquet",
    "data/processed/event_id_cluster_map.csv",
    "data/processed/event_station_table.csv",
    "data/processed/koeri_stations.csv",
    "data/processed/koeri_channels.csv",
    "data/processed/waveform_fetch_log.csv",
    "data/processed/waveform_features.csv",
    "data/processed/validation_report.json",
    "data/processed/validation_report.md",
]
BENCHMARK_OUTPUTS = [
    f"benchmarks/{task}/{split}.csv"
    for task in ("ground_motion", "phase_picking", "early_warning")
    for split in ("train", "val", "test")
]
BENCHMARK_OUTPUTS += [
    f"benchmarks/ground_motion/holdout_by_{holdout}/{split}.csv"
    for holdout in ("station", "time")
    for split in ("train", "val", "test")
]


def sha256_file(path: Path, chunk_size: int = CHUNK_SIZE) -> str:
    """Hash a file in fixed-size chunks so peak memory does not scale with it."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_outputs(root: Path, *, skip_isc_picks: bool = False) -> list[Path]:
    """Return the required release files, including each waveform separately."""
    relative_paths = BASE_OUTPUTS + BENCHMARK_OUTPUTS
    if not skip_isc_picks:
        relative_paths.append("data/processed/isc_analyst_picks.csv")

    missing = [p for p in relative_paths if not (root / p).is_file()]
    waveform_dir = root / "data/processed/waveforms"
    if not waveform_dir.is_dir():
        missing.append("data/processed/waveforms/")
    else:
        waveforms = sorted(p for p in waveform_dir.rglob("*") if p.is_file())
        if not waveforms:
            missing.append("data/processed/waveforms/*.mseed (no files found)")

    if missing:
        formatted = "\n".join(f"  - {name}" for name in missing)
        raise FileNotFoundError(f"Required dataset outputs are missing:\n{formatted}")

    paths = [root / name for name in relative_paths]
    raw_source_cache = root / "data/processed/expanded_catalog_raw_cache.parquet"
    if raw_source_cache.is_file():
        paths.append(raw_source_cache)
    optional_pick_report = root / "data/processed/isc_pick_comparison_report.json"
    if optional_pick_report.is_file():
        paths.append(optional_pick_report)
    paths.extend(waveforms)
    return sorted(paths, key=lambda p: p.relative_to(root).as_posix())


def discover_git_info(root: Path) -> dict[str, Any]:
    """Capture the source revision and whether tracked/untracked changes exist."""
    try:
        revision = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"Could not determine git revision/status for {root}: {exc}") from exc
    return {"revision": revision, "working_tree_dirty": bool(status.strip())}


def build_manifest(
    root: Path,
    output_paths: list[Path],
    *,
    metadata: dict[str, Any],
    git_info: dict[str, Any],
    skip_isc_picks: bool = False,
    source_observations: dict[str, dict[str, int]] | None = None,
    dependencies: dict[str, str] | None = None,
    build_time_utc: str | None = None,
) -> dict[str, Any]:
    """Build deterministic manifest data when metadata and git info are fixed."""
    root = root.resolve()
    outputs = []
    validated_paths = []
    for path in output_paths:
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"Output is outside repository root: {path}") from exc
        if not resolved.is_file():
            raise FileNotFoundError(f"Output file is missing or not a regular file: {relative}")
        validated_paths.append((relative, resolved))

    for relative, resolved in sorted(validated_paths):
        outputs.append(
            {
                "path": relative,
                "size_bytes": resolved.stat().st_size,
                "sha256": sha256_file(resolved),
            }
        )

    observations = source_observations or {}
    sources = []
    for source in SOURCE_REFERENCES:
        item = dict(source)
        source_counts = observations.get(source["source"], {})
        item["observed_lineage_counts"] = source_counts
        item["query_configuration"] = SOURCE_QUERY_CONFIG[source["source"]]
        if source["source"] in {"USGS ComCat", "EMSC", "ISC Bulletin / FDSN event service"}:
            count = source_counts.get("catalog_source_records")
            item["status"] = (
                "catalog_records_observed" if count and count > 0
                else "no_catalog_records_observed" if count == 0
                else "catalog_source_status_unverified"
            )
        elif source["source"] == "KOERI / ORFEUS-EIDA":
            stations = source_counts.get("station_rows", 0)
            waveforms = source_counts.get("waveform_files", 0)
            item["status"] = (
                "stations_and_waveforms_observed" if stations > 0 and waveforms > 0
                else "stations_observed_no_waveforms" if stations > 0
                else "koeri_source_status_unverified"
            )
        elif source["source"] == "USGS Global Vs30 Mosaic":
            count = source_counts.get("stations_with_vs30")
            item["status"] = (
                "vs30_values_observed" if count and count > 0
                else "no_vs30_values_observed" if count == 0
                else "vs30_source_status_unverified"
            )
        if skip_isc_picks and source["source"] == "ISC Bulletin / FDSN event service":
            item["status"] += "_picks_skipped"
        sources.append(item)

    return {
        "manifest_schema_version": 1,
        "build": {
            "git": dict(git_info),
            "metadata": metadata,
            "dependencies": dict(dependencies or {}),
            "build_time_utc": build_time_utc,
        },
        "sources": sources,
        "outputs": outputs,
    }


def collect_source_observations(root: Path) -> dict[str, dict[str, int]]:
    """Count source identifiers using streaming CSV reads, without loading tables."""
    counts: dict[str, dict[str, int]] = {
        source: {"catalog_source_records": 0}
        for source in ("USGS ComCat", "EMSC", "ISC Bulletin / FDSN event service")
    }
    cluster_map = root / "data/processed/event_id_cluster_map.csv"
    with cluster_map.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            source = row.get("source", "").strip().lower()
            if source in {"usgs", "emsc", "isc"}:
                label = {"usgs": "USGS ComCat", "emsc": "EMSC", "isc": "ISC Bulletin / FDSN event service"}[source]
                bucket = counts.setdefault(label, {})
                bucket["catalog_source_records"] = bucket.get("catalog_source_records", 0) + 1

    stations = root / "data/processed/koeri_stations.csv"
    station_count = 0
    if stations.is_file():
        vs30_count = 0
        with stations.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                station_count += 1
                if row.get("vs30_ms", "").strip():
                    vs30_count += 1
        counts["USGS Global Vs30 Mosaic"] = {"stations_with_vs30": vs30_count}

    waveform_dir = root / "data/processed/waveforms"
    if waveform_dir.is_dir():
        waveform_count = sum(1 for path in waveform_dir.rglob("*") if path.is_file())
        counts["KOERI / ORFEUS-EIDA"] = {"waveform_files": waveform_count, "station_rows": station_count}
    elif station_count:
        counts["KOERI / ORFEUS-EIDA"] = {"waveform_files": 0, "station_rows": station_count}
    return counts


def collect_dependency_versions() -> dict[str, str]:
    """Return installed versions for the runtime packages used by the pipeline."""
    dependencies = {}
    for distribution in ("numpy", "obspy", "pandas", "pyarrow", "requests"):
        try:
            dependencies[distribution] = package_version(distribution)
        except PackageNotFoundError:
            dependencies[distribution] = "not-installed"
    return dependencies


def compare_manifests(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Compare artifact bytes separately from source lineage row-count deltas."""
    for label, manifest in (("previous", previous), ("current", current)):
        if not isinstance(manifest.get("outputs"), list) or not isinstance(manifest.get("sources"), list):
            raise ValueError(f"{label} manifest must contain outputs and sources lists")

    def output_index(manifest: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
        indexed = {}
        for output in manifest["outputs"]:
            if not isinstance(output, dict) or not isinstance(output.get("path"), str):
                raise ValueError(f"{label} manifest contains an invalid output entry")
            if output["path"] in indexed:
                raise ValueError(f"{label} manifest contains duplicate output path: {output['path']}")
            indexed[output["path"]] = output
        return indexed

    old_outputs = output_index(previous, "previous")
    new_outputs = output_index(current, "current")
    old_paths, new_paths = set(old_outputs), set(new_outputs)
    added = sorted(new_paths - old_paths)
    removed = sorted(old_paths - new_paths)
    changed = []
    for path in sorted(old_paths & new_paths):
        old, new = old_outputs[path], new_outputs[path]
        if old.get("sha256") != new.get("sha256") or old.get("size_bytes") != new.get("size_bytes"):
            changed.append(
                {
                    "path": path,
                    "previous": {"sha256": old.get("sha256"), "size_bytes": old.get("size_bytes")},
                    "current": {"sha256": new.get("sha256"), "size_bytes": new.get("size_bytes")},
                }
            )

    def source_index(manifest: dict[str, Any], label: str) -> dict[str, dict[str, int]]:
        indexed = {}
        for source in manifest["sources"]:
            if not isinstance(source, dict) or not isinstance(source.get("source"), str):
                raise ValueError(f"{label} manifest contains an invalid source entry")
            indexed[source["source"]] = source.get("observed_lineage_counts", {})
        return indexed

    old_sources = source_index(previous, "previous")
    new_sources = source_index(current, "current")
    lineage_deltas = []
    for source in sorted(set(old_sources) | set(new_sources)):
        old_counts = old_sources.get(source, {})
        new_counts = new_sources.get(source, {})
        for metric in sorted(set(old_counts) | set(new_counts)):
            old_count = old_counts.get(metric, 0)
            new_count = new_counts.get(metric, 0)
            if old_count != new_count:
                lineage_deltas.append(
                    {"source": source, "metric": metric, "previous": old_count, "current": new_count,
                     "delta": new_count - old_count}
                )

    return {
        "comparison_kind": "artifact_and_lineage_delta_not_scientific_quality_verdict",
        "artifacts": {"added": added, "removed": removed, "changed": changed},
        "source_lineage_counts": lineage_deltas,
    }


def read_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Manifest does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Manifest is not valid JSON: {path}") from exc
    if not isinstance(manifest, dict):
        raise ValueError(f"Manifest root must be a JSON object: {path}")
    return manifest


def write_manifest(manifest: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root (default: cwd)")
    parser.add_argument("--skip-isc-picks", action="store_true", help="record that analyst picks were skipped")
    parser.add_argument(
        "--metadata-json",
        type=Path,
        help="optional JSON object with explicit build metadata; avoids implicit timestamps",
    )
    parser.add_argument("--compare-to", type=Path, help="compare this previous manifest with the current manifest")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH, help="manifest path for --compare-to")
    args = parser.parse_args()

    try:
        if args.compare_to:
            report = compare_manifests(read_manifest(args.compare_to), read_manifest(args.manifest))
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        metadata = json.loads(args.metadata_json.read_text(encoding="utf-8")) if args.metadata_json else {}
        if not isinstance(metadata, dict):
            raise ValueError("--metadata-json must contain a JSON object")
        metadata.setdefault("python_version", ".".join(map(str, sys.version_info[:3])))
        metadata.setdefault("isc_analyst_picks_skipped", args.skip_isc_picks)
        build_time = metadata.get("build_time_utc") or datetime.now(timezone.utc).isoformat()
        outputs = collect_outputs(args.root, skip_isc_picks=args.skip_isc_picks)
        manifest = build_manifest(
            args.root,
            outputs,
            metadata=metadata,
            git_info=discover_git_info(args.root),
            skip_isc_picks=args.skip_isc_picks,
            source_observations=collect_source_observations(args.root),
            dependencies=collect_dependency_versions(),
            build_time_utc=build_time,
        )
        write_manifest(manifest, args.root / MANIFEST_PATH)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"[HATA] provenance manifest oluşturulamadı: {exc}", file=sys.stderr)
        return 1

    print(f"Provenance manifest yazıldı -> {args.root / MANIFEST_PATH} ({len(manifest['outputs'])} dosya)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
