"""
scripts/build_event_station_table.py'deki join_features_with_distances()
için regresyon testi.

issue #1'in kök nedeni: eski koddaki max_pga_g, bir olay için indirilen
BİRDEN FAZLA istasyon kaydı arasındaki en yüksek değeri, mesafe ise ayrı
olarak hesaplanan "en yakın istasyon" değerini kullanıyordu - ikisi aynı
istasyona ait olmak zorunda değildi. Bu testler her (event_id, station)
satırının mesafesinin, o SATIRDAKİ istasyona göre hesaplandığını ve
başka bir istasyonun mesafesiyle karışmadığını doğruluyor.
"""
import pandas as pd
import pytest

from build_event_station_table import hypocentral_km, join_features_with_distances


@pytest.fixture
def events_small():
    return pd.DataFrame(
        {
            "event_id": ["ev1"],
            "event_latitude": [39.00],
            "event_longitude": [35.00],
            "depth_km": [10.0],
            "magnitude": [5.0],
            "mag_type": ["mw"],
            "time_utc": ["2020-01-01T00:00:00"],
            "mw_estimate": [5.0],
        }
    )


@pytest.fixture
def stations_small():
    # NEAR: olaya yakın, düşük PGA kaydetmiş.
    # FAR: olaya çok uzak, ama en yüksek PGA'yı bu kaydetmiş (ör. yerel
    # zemin etkisi/farklı bir artçı depremin karışması gibi gerçekçi bir
    # senaryo).
    return pd.DataFrame(
        {
            "station": ["NEAR", "FAR"],
            "station_latitude": [39.05, 41.00],
            "station_longitude": [35.05, 37.00],
            "vs30_ms": [400.0, 350.0],
            "nehrp_site_class": ["C", "C"],
            "has_strong_motion": [True, True],
        }
    )


@pytest.fixture
def features():
    return pd.DataFrame(
        {
            "event_id": ["ev1", "ev1"],
            "station": ["NEAR", "FAR"],
            "pga_g": [0.05, 0.80],
        }
    )


def test_each_row_keeps_its_own_stations_distance(events_small, stations_small, features):
    table = join_features_with_distances(features, events_small, stations_small)
    near_row = table[table["station"] == "NEAR"].iloc[0]
    far_row = table[table["station"] == "FAR"].iloc[0]

    assert near_row["epicentral_distance_km"] < far_row["epicentral_distance_km"]


def test_max_pga_row_is_not_silently_paired_with_nearest_station_distance(events_small, stations_small, features):
    # Bu, issue #1'in tam olarak tersini kanıtlıyor: en yüksek PGA'ya
    # sahip satır (FAR), NEAR'ın küçük mesafesiyle değil, kendi (büyük)
    # mesafesiyle eşleşmeli.
    table = join_features_with_distances(features, events_small, stations_small)
    max_pga_row = table.loc[table["pga_g"].idxmax()]

    assert max_pga_row["station"] == "FAR"
    assert max_pga_row["epicentral_distance_km"] > 100


def test_hypocentral_distance_uses_pythagorean_combination_with_depth():
    epicentral_km = pd.Series([3.0])
    depth_km = pd.Series([4.0])
    # 3-4-5 üçgeni: kolay doğrulanabilir bir sonuç.
    assert hypocentral_km(epicentral_km, depth_km).iloc[0] == pytest.approx(5.0)


def test_join_is_inner_on_event_id_drops_events_without_waveform_features():
    events_small = pd.DataFrame(
        {
            "event_id": ["ev1", "ev_no_waveform"],
            "event_latitude": [39.0, 38.0],
            "event_longitude": [35.0, 34.0],
            "depth_km": [10.0, 5.0],
            "magnitude": [5.0, 4.0],
            "mag_type": ["mw", "mw"],
            "time_utc": ["2020-01-01T00:00:00", "2021-01-01T00:00:00"],
            "mw_estimate": [5.0, 4.0],
        }
    )
    stations_small = pd.DataFrame(
        {
            "station": ["NEAR"],
            "station_latitude": [39.05],
            "station_longitude": [35.05],
            "vs30_ms": [400.0],
            "nehrp_site_class": ["C"],
            "has_strong_motion": [True],
        }
    )
    features = pd.DataFrame({"event_id": ["ev1"], "station": ["NEAR"], "pga_g": [0.05]})

    table = join_features_with_distances(features, events_small, stations_small)

    assert list(table["event_id"]) == ["ev1"]
