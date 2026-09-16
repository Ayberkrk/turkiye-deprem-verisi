"""
scripts/build_dataset.py'deki nearest() fonksiyonu için birim testler:
her olay için en yakın istasyonu (herhangi tip) ve en yakın güçlü hareket
istasyonunu doğru ayırt ediyor mu (bkz. issue #12 - bu koddaki bir
regresyon issue #1'e yol açmıştı).
"""
import pandas as pd
import pytest

from build_dataset import nearest


@pytest.fixture
def stations():
    # A: olaya en yakın istasyon ama güçlü hareket kaydı yok.
    # B: ondan sonraki en yakın, güçlü hareket kaydı VAR.
    # C: uzak, güçlü hareket kaydı VAR.
    return pd.DataFrame(
        {
            "station": ["A_BROADBAND", "B_STRONG_MOTION", "C_STRONG_MOTION"],
            "latitude": [39.10, 39.20, 40.50],
            "longitude": [35.10, 35.20, 36.50],
            "has_strong_motion": [False, True, True],
        }
    )


@pytest.fixture
def events():
    return pd.DataFrame(
        {
            "event_id": ["ev1"],
            "latitude": [39.00],
            "longitude": [35.00],
        }
    )


def test_nearest_any_station_ignores_strong_motion_flag(events, stations):
    out = nearest(events, stations)
    assert out.loc[0, "nearest_station"] == "A_BROADBAND"


def test_nearest_strong_motion_station_skips_non_strong_motion_stations(events, stations):
    # En yakın istasyon (A) güçlü hareket kaydı yapmıyor, bu yüzden
    # nearest_strong_motion_station A değil, B olmalı - fiziksel olarak
    # daha uzak ama tek uygun aday.
    out = nearest(events, stations)
    assert out.loc[0, "nearest_strong_motion_station"] == "B_STRONG_MOTION"


def test_nearest_strong_motion_distance_is_not_nearest_any_distance(events, stations):
    out = nearest(events, stations)
    assert out.loc[0, "nearest_strong_motion_distance_km"] > out.loc[0, "nearest_station_distance_km"]


def test_nearest_handles_no_strong_motion_stations_gracefully():
    events = pd.DataFrame({"event_id": ["ev1"], "latitude": [39.0], "longitude": [35.0]})
    stations = pd.DataFrame(
        {
            "station": ["A_BROADBAND"],
            "latitude": [39.1],
            "longitude": [35.1],
            "has_strong_motion": [False],
        }
    )
    out = nearest(events, stations)
    assert out.loc[0, "nearest_strong_motion_station"] is None
    assert out.loc[0, "nearest_strong_motion_distance_km"] is None
