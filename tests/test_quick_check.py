"""Hızlı kontrol orkestrasyonunu gerçek dosya/ağ olmadan doğrular."""
from pathlib import Path
from unittest.mock import Mock

import pytest
import quick_check


@pytest.fixture
def isolated_checks(monkeypatch):
    # Kimlik denetimi, doğru tablonun doğru kontrole iletildiğini de korur.
    tables = {name: object() for name in (
        "turkiye_deprem_veriseti_v3.parquet", "koeri_stations.csv",
        "waveform_features.csv", "event_station_table.csv", "waveform_fetch_log.csv",
    )}
    reads = []

    def read(path):
        reads.append(Path(path).name)
        return tables[Path(path).name]

    monkeypatch.setattr(quick_check.pd, "read_parquet", read)
    monkeypatch.setattr(quick_check.pd, "read_csv", read)
    monkeypatch.setattr(Path, "exists", lambda path: True)
    mocks = {}
    for name in (
        "structural_checks", "event_station_geometry_checks",
        "ground_motion_plausibility_checks", "horizontal_component_checks",
        "benchmark_leakage_checks", "benchmark_holdout_checks", "dedup_quality_checks",
    ):
        mocks[name] = Mock(return_value=[(name, True, "")])
    mocks["phase_order_check"] = Mock(return_value=("phase_order_check", True, ""))
    mocks["fetch_log_consistency_check"] = Mock(
        return_value=("fetch_log_consistency_check", True, ""))
    waveforms = ["synthetic.mseed"]
    splits = object()
    mocks["waveform_file_count_check"] = Mock(
        return_value=(waveforms, ("waveform_file_count_check", True, "")))
    mocks["load_benchmark_splits"] = Mock(return_value=splits)
    for name, mock in mocks.items():
        monkeypatch.setattr(quick_check, name, mock)
    return tables, reads, mocks, waveforms, splits


def test_all_checks_pass(isolated_checks, capsys):
    tables, reads, mocks, waveforms, splits = isolated_checks
    with pytest.raises(SystemExit) as exc:
        quick_check.main()
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "Tüm hızlı kontroller başarılı" in output
    assert "BAŞARISIZ" not in output
    for name in mocks:
        if name != "load_benchmark_splits":
            assert f"[OK] {name}" in output
    assert set(reads) == set(tables)
    mocks["structural_checks"].assert_called_once_with(
        tables["turkiye_deprem_veriseti_v3.parquet"], tables["koeri_stations.csv"],
        tables["waveform_features.csv"])
    mocks["benchmark_leakage_checks"].assert_called_once_with(
        tables["event_station_table.csv"], splits)
    mocks["fetch_log_consistency_check"].assert_called_once_with(
        tables["waveform_fetch_log.csv"], waveforms)


def test_failure_reports_name_detail_and_count(isolated_checks, capsys):
    isolated_checks[2]["structural_checks"].return_value = [
        ("sentetik hata", False, "sentetik ayrıntı")]
    with pytest.raises(SystemExit) as exc:
        quick_check.main()
    assert exc.value.code == 1
    output = capsys.readouterr().out
    assert "[BAŞARISIZ] sentetik hata - sentetik ayrıntı" in output
    assert "1 kontrol başarısız." in output
    assert "Tüm hızlı kontroller başarılı" not in output
    isolated_checks[2]["fetch_log_consistency_check"].assert_called_once()


def test_missing_optional_inputs_and_skipped_checks(isolated_checks, monkeypatch, capsys):
    _, reads, mocks, waveforms, splits = isolated_checks
    monkeypatch.setattr(Path, "exists", lambda path: False)
    mocks["phase_order_check"].return_value = None
    mocks["fetch_log_consistency_check"].return_value = None
    with pytest.raises(SystemExit) as exc:
        quick_check.main()
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "Tüm hızlı kontroller başarılı" in output
    assert "phase_order_check" not in output
    assert "fetch_log_consistency_check" not in output
    assert "event_station_table.csv" not in reads
    assert "waveform_fetch_log.csv" not in reads
    mocks["event_station_geometry_checks"].assert_called_once_with(None)
    mocks["benchmark_leakage_checks"].assert_called_once_with(None, splits)
    mocks["fetch_log_consistency_check"].assert_called_once_with(None, waveforms)
