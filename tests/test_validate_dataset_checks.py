"""
scripts/validate_dataset.py'deki saf kontrol fonksiyonları için birim
testler. Her kontrol grubu için hem "temiz" (hepsi geçer) hem sentetik
bir şekilde bozulmuş en az bir satır (ilgili kontrol beklenen isimle
başarısız olur) senaryosu deneniyor.
"""
import pandas as pd
import pytest

from validate_dataset import (
    dedup_quality_checks,
    event_station_geometry_checks,
    fetch_log_consistency_check,
    ground_motion_plausibility_checks,
    phase_order_check,
    structural_checks,
    waveform_file_count_check,
)


def result_for(results, name):
    for check_name, condition, detail in results:
        if check_name == name:
            return condition, detail
    raise AssertionError(f"'{name}' isimli kontrol bulunamadı: {[r[0] for r in results]}")


@pytest.fixture
def clean_events():
    return pd.DataFrame(
        {
            "event_id": ["ev1", "ev2"],
            "magnitude": [4.5, 5.0],
            "latitude": [39.0, 40.0],
            "longitude": [35.0, 36.0],
            "time_utc": ["2020-01-01T00:00:00", "2020-01-02T00:00:00"],
            "depth_km": [10.0, 5.0],
            "has_waveform": [True, False],
            "num_waveform_files": [2, 0],
            "mw_estimate": [4.5, float("nan")],
            "magnitude_scale_group": ["moment_magnitude", "local_magnitude"],
            "magnitude_agreement_std": [0.1, 0.0],
            "reported_by": ["usgs", "usgs,emsc"],
        }
    )


@pytest.fixture
def clean_stations():
    return pd.DataFrame(
        {
            "latitude": [39.1, 40.1],
            "longitude": [35.1, 36.1],
            "vs30_ms": [400.0, 500.0],
            "nehrp_site_class": ["C", "D"],
        }
    )


@pytest.fixture
def clean_features():
    return pd.DataFrame(
        {
            "pga_g": [0.05, 0.10],
            "file": ["a.mseed", "b.mseed"],
        }
    )


def test_structural_checks_all_pass_on_clean_data(clean_events, clean_stations, clean_features):
    results = structural_checks(clean_events, clean_stations, clean_features)
    assert all(condition for _, condition, _ in results)


def test_structural_checks_rejects_empty_core_tables(clean_events, clean_stations, clean_features):
    results = structural_checks(
        clean_events.iloc[0:0],
        clean_stations.iloc[0:0],
        clean_features.iloc[0:0],
    )

    for name in (
        "Ana deprem kataloğu boş değil",
        "İstasyon tablosu boş değil",
        "Dalga formu özellik tablosu boş değil",
    ):
        condition, detail = result_for(results, name)
        assert bool(condition) is False
        assert detail == "0 satır"


def test_structural_checks_catches_duplicate_event_id(clean_events, clean_stations, clean_features):
    broken = clean_events.copy()
    broken.loc[1, "event_id"] = "ev1"
    results = structural_checks(broken, clean_stations, clean_features)
    condition, _ = result_for(results, "event_id benzersiz")
    assert bool(condition) is False


def test_structural_checks_catches_out_of_range_magnitude(clean_events, clean_stations, clean_features):
    broken = clean_events.copy()
    broken.loc[0, "magnitude"] = 11.5
    results = structural_checks(broken, clean_stations, clean_features)
    condition, _ = result_for(results, "Büyüklük makul aralıkta (0-10)")
    assert bool(condition) is False


def test_structural_checks_catches_coordinates_outside_turkey(clean_events, clean_stations, clean_features):
    broken = clean_events.copy()
    broken.loc[0, "latitude"] = 10.0  # Türkiye kutusunun dışında
    results = structural_checks(broken, clean_stations, clean_features)
    condition, _ = result_for(results, "Koordinatlar Türkiye kutusunda (lat 34-44, lon 24-46)")
    assert bool(condition) is False


def test_structural_checks_catches_negative_pga(clean_events, clean_stations, clean_features):
    broken = clean_features.copy()
    broken.loc[0, "pga_g"] = -0.01
    results = structural_checks(clean_events, clean_stations, broken)
    condition, _ = result_for(results, "PGA değeri her satırda pozitif ya da sıfır")
    assert bool(condition) is False


def test_structural_checks_catches_invalid_nehrp_class(clean_events, clean_stations, clean_features):
    broken = clean_stations.copy()
    broken.loc[0, "nehrp_site_class"] = "Z"
    results = structural_checks(clean_events, broken, clean_features)
    condition, _ = result_for(results, "NEHRP zemin sınıfı geçerli değerlerde (A-E)")
    assert bool(condition) is False


def test_waveform_file_count_check_matches(tmp_path, clean_events):
    waveform_dir = tmp_path / "waveforms"
    waveform_dir.mkdir()
    (waveform_dir / "a.mseed").write_bytes(b"")
    (waveform_dir / "b.mseed").write_bytes(b"")

    files, result = waveform_file_count_check(clean_events, waveform_dir)
    assert len(files) == 2
    assert bool(result[1]) is True


def test_waveform_file_count_check_mismatch(tmp_path, clean_events):
    waveform_dir = tmp_path / "waveforms"
    waveform_dir.mkdir()
    (waveform_dir / "a.mseed").write_bytes(b"")

    _, result = waveform_file_count_check(clean_events, waveform_dir)
    assert bool(result[1]) is False


@pytest.fixture
def clean_event_station():
    return pd.DataFrame(
        {
            "event_latitude": [39.0],
            "event_longitude": [35.0],
            "station_latitude": [39.05],
            "station_longitude": [35.05],
            "epicentral_distance_km": [7.04],
            "hypocentral_distance_km": [12.19],
        }
    )


def test_event_station_geometry_checks_pass_on_consistent_data(clean_event_station):
    results = event_station_geometry_checks(clean_event_station)
    assert all(condition for _, condition, _ in results)


def test_event_station_geometry_checks_catches_stale_distance(clean_event_station):
    broken = clean_event_station.copy()
    broken.loc[0, "epicentral_distance_km"] = 999.0
    results = event_station_geometry_checks(broken)
    condition, _ = result_for(results, "event-station epicentral mesafesi koordinatlarla tutarlı (<=1km fark)")
    assert bool(condition) is False


def test_event_station_geometry_checks_missing_table_fails():
    results = event_station_geometry_checks(None)
    assert len(results) == 1
    assert bool(results[0][1]) is False


def test_ground_motion_plausibility_flags_extreme_pga():
    features = pd.DataFrame({"pga_g": [0.5, 5.5], "pgv_cms": [10.0, 20.0]})
    results = ground_motion_plausibility_checks(features)
    condition, _ = result_for(results, "Aşırı büyük PGA değeri yok (>4g şüpheli)")
    assert bool(condition) is False


def test_ground_motion_plausibility_flags_extreme_pgv():
    features = pd.DataFrame({"pga_g": [0.5, 0.6], "pgv_cms": [10.0, 600.0]})
    results = ground_motion_plausibility_checks(features)
    condition, _ = result_for(results, "Aşırı büyük PGV değeri yok (>500 cm/s şüpheli)")
    assert bool(condition) is False


def test_phase_order_check_catches_s_before_p():
    features = pd.DataFrame(
        {
            "p_pick_time": ["2020-01-01T00:00:10", "2020-01-01T00:00:20"],
            "s_pick_time": ["2020-01-01T00:00:15", "2020-01-01T00:00:19"],
        }
    )
    _, condition, detail = phase_order_check(features)
    assert bool(condition) is False
    assert "1" in detail


def test_phase_order_check_returns_none_without_picks():
    features = pd.DataFrame({"pga_g": [0.1]})
    assert phase_order_check(features) is None


def test_dedup_quality_checks_flags_low_confidence_clusters():
    events = pd.DataFrame(
        {
            "dedup_confidence": [0.9, 0.1, 0.2],
            "cluster_size": [1, 3, 3],
        }
    )
    results = dedup_quality_checks(events)
    condition, _ = result_for(results, "Düşük güvenli (<0.5) çok kaynaklı küme sayısı makul seviyede (<%1)")
    assert bool(condition) is False


def test_dedup_quality_checks_empty_without_column():
    assert dedup_quality_checks(pd.DataFrame({"magnitude": [4.0]})) == []


def test_fetch_log_consistency_check_catches_mismatch():
    log = pd.DataFrame({"status": ["ok", "ok", "failed"]})
    _, condition, _ = fetch_log_consistency_check(log, waveform_files=["a.mseed"])
    assert bool(condition) is False


def test_fetch_log_consistency_check_none_without_log():
    assert fetch_log_consistency_check(None, waveform_files=[]) is None
