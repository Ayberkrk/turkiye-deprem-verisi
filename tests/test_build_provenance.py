import hashlib
import json
from pathlib import Path

import pytest
from build_provenance import (
    build_manifest,
    collect_outputs,
    collect_source_observations,
    compare_manifests,
    sha256_file,
)


def test_manifest_hashes_outputs_and_is_deterministic_with_explicit_metadata(tmp_path: Path) -> None:
    first = tmp_path / "catalog.csv"
    second = tmp_path / "waveforms" / "a.mseed"
    second.parent.mkdir()
    first.write_bytes(b"event_id\n1\n")
    second.write_bytes(b"waveform-bytes")
    outputs = [first, second]
    metadata = {"pipeline": "fixture", "seed": 17}
    git_info = {"revision": "abc123", "working_tree_dirty": False}
    dependencies = {"pandas": "2.3.0", "pyarrow": "23.0.0"}
    build_time_utc = "2026-10-25T10:00:00+00:00"

    manifest = build_manifest(
        tmp_path,
        outputs,
        metadata=metadata,
        git_info=git_info,
        dependencies=dependencies,
        build_time_utc=build_time_utc,
    )
    repeated = build_manifest(
        tmp_path,
        outputs,
        metadata=metadata,
        git_info=git_info,
        dependencies=dependencies,
        build_time_utc=build_time_utc,
    )

    assert manifest == repeated
    assert manifest["build"]["dependencies"] == dependencies
    assert manifest["build"]["build_time_utc"] == build_time_utc
    assert manifest["outputs"] == [
        {"path": "catalog.csv", "size_bytes": 11, "sha256": hashlib.sha256(first.read_bytes()).hexdigest()},
        {"path": "waveforms/a.mseed", "size_bytes": len(second.read_bytes()),
         "sha256": hashlib.sha256(second.read_bytes()).hexdigest()},
    ]
    assert sha256_file(second, chunk_size=3) == hashlib.sha256(second.read_bytes()).hexdigest()


def test_manifest_preserves_restricted_and_unclear_license_classifications(tmp_path: Path) -> None:
    artifact = tmp_path / "output.csv"
    artifact.write_text("x\n", encoding="utf-8")
    manifest = build_manifest(tmp_path, [artifact], metadata={}, git_info={})

    by_source = {item["source"]: item for item in manifest["sources"]}
    assert by_source["EMSC"]["license_classification"] == "unclear"
    assert by_source["KOERI / ORFEUS-EIDA"]["license_classification"] == "noncommercial_reuse_restricted"
    assert by_source["USGS ComCat"]["license_classification"] == "public_domain"
    assert all(item["license_reference"].startswith("https://") for item in manifest["sources"])
    assert by_source["USGS ComCat"]["query_configuration"]["minimum_magnitude"] == 3.0
    assert by_source["KOERI / ORFEUS-EIDA"]["query_configuration"]["waveform_window_seconds"] == {
        "before_event": 10,
        "after_event": 200,
    }


def test_manifest_marks_isc_picks_skipped_without_marking_isc_catalog_absent(tmp_path: Path) -> None:
    artifact = tmp_path / "output.csv"
    artifact.write_text("x\n", encoding="utf-8")
    manifest = build_manifest(
        tmp_path, [artifact], metadata={}, git_info={}, skip_isc_picks=True
    )

    isc = next(item for item in manifest["sources"] if item["source"].startswith("ISC Bulletin"))
    assert isc["status"].endswith("_picks_skipped")
    assert any(lineage["file"].endswith("katalogu_genisletilmis.parquet") for lineage in isc["lineage"])


def test_manifest_fails_clearly_for_missing_or_outside_outputs(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="missing.parquet"):
        build_manifest(
            tmp_path,
            [tmp_path / "missing.parquet"],
            metadata={},
            git_info={},
        )

    outside = tmp_path.parent / "outside.csv"
    outside.write_text("x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="outside repository root"):
        build_manifest(tmp_path, [outside], metadata={}, git_info={})


def test_collect_outputs_reports_all_missing_required_files(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError) as error:
        collect_outputs(tmp_path, skip_isc_picks=True)

    message = str(error.value)
    assert "usgs_catalog_turkey.parquet" in message
    assert "benchmarks/ground_motion/train.csv" in message
    assert "data/processed/waveforms/" in message


def test_source_observations_count_lineage_streaming_from_small_fixture(tmp_path: Path) -> None:
    processed = tmp_path / "data/processed"
    processed.mkdir(parents=True)
    (processed / "event_id_cluster_map.csv").write_text(
        "source,source_event_id,representative_event_id\nusgs,u1,u1\nemsc,e1,u1\nisc,i1,u1\n",
        encoding="utf-8",
    )
    (processed / "koeri_stations.csv").write_text(
        "station,vs30_ms\nAAA,500\nBBB,\n",
        encoding="utf-8",
    )
    waveform_dir = processed / "waveforms"
    waveform_dir.mkdir()
    (waveform_dir / "record.mseed").write_bytes(b"small-fixture")
    (processed / "expanded_catalog_raw_cache.parquet").write_bytes(b"raw-source-snapshot")

    observations = collect_source_observations(tmp_path)

    assert observations["USGS ComCat"]["catalog_source_records"] == 1
    assert observations["EMSC"]["catalog_source_records"] == 1
    assert observations["ISC Bulletin / FDSN event service"]["catalog_source_records"] == 1
    assert observations["USGS Global Vs30 Mosaic"]["stations_with_vs30"] == 1
    assert observations["KOERI / ORFEUS-EIDA"] == {"waveform_files": 1, "station_rows": 2}


def test_write_manifest_is_stable_json(tmp_path: Path) -> None:
    from build_provenance import write_manifest

    output = tmp_path / "manifest.json"
    data = {"z": 1, "a": {"value": "ok"}}
    write_manifest(data, output)
    first = output.read_text(encoding="utf-8")
    write_manifest(data, output)

    assert output.read_text(encoding="utf-8") == first
    assert json.loads(first) == data


def test_manifest_comparison_separates_artifact_and_lineage_deltas() -> None:
    previous = {
        "outputs": [
            {"path": "same.parquet", "sha256": "old", "size_bytes": 10},
            {"path": "removed.csv", "sha256": "gone", "size_bytes": 2},
        ],
        "sources": [
            {"source": "USGS", "observed_lineage_counts": {"records": 10}},
            {"source": "ISC", "observed_lineage_counts": {"records": 4}},
        ],
    }
    current = {
        "outputs": [
            {"path": "same.parquet", "sha256": "new", "size_bytes": 12},
            {"path": "added.csv", "sha256": "new-file", "size_bytes": 3},
        ],
        "sources": [
            {"source": "USGS", "observed_lineage_counts": {"records": 11}},
            {"source": "ISC", "observed_lineage_counts": {"records": 4}},
            {"source": "EMSC", "observed_lineage_counts": {"records": 2}},
        ],
    }

    report = compare_manifests(previous, current)

    assert report["comparison_kind"] == "artifact_and_lineage_delta_not_scientific_quality_verdict"
    assert report["artifacts"]["added"] == ["added.csv"]
    assert report["artifacts"]["removed"] == ["removed.csv"]
    assert report["artifacts"]["changed"] == [
        {
            "path": "same.parquet",
            "previous": {"sha256": "old", "size_bytes": 10},
            "current": {"sha256": "new", "size_bytes": 12},
        }
    ]
    assert report["source_lineage_counts"] == [
        {"source": "EMSC", "metric": "records", "previous": 0, "current": 2, "delta": 2},
        {"source": "USGS", "metric": "records", "previous": 10, "current": 11, "delta": 1},
    ]


def test_manifest_comparison_rejects_missing_or_invalid_inputs(tmp_path: Path) -> None:
    from build_provenance import read_manifest

    with pytest.raises(FileNotFoundError, match="does not exist"):
        read_manifest(tmp_path / "missing.json")
    with pytest.raises(ValueError, match="valid JSON"):
        (tmp_path / "bad.json").write_text("{", encoding="utf-8")
        read_manifest(tmp_path / "bad.json")
    with pytest.raises(ValueError, match="outputs and sources"):
        compare_manifests({"outputs": []}, {"outputs": [], "sources": []})
