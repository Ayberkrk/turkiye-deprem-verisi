"""Eksik hızın yumuşak zemin diye sınıflanmamasını sentetik girdilerle korur."""
import math

import fetch_vs30
import pandas as pd
import pytest
from fetch_vs30 import nehrp_class


@pytest.mark.parametrize("vs30", [None, math.nan, 0.0, -0.0, -1.0, -math.inf, math.inf])
def test_missing_or_invalid_velocity_has_no_class(vs30):
    assert nehrp_class(vs30) is None


@pytest.mark.parametrize("boundary, at_boundary, above_boundary", [
    (180.0, "E", "D"),
    (360.0, "D", "C"),
    (760.0, "C", "B"),
    (1500.0, "B", "A"),
])
def test_class_boundaries_keep_existing_strict_comparisons(boundary, at_boundary, above_boundary):
    assert nehrp_class(math.nextafter(boundary, -math.inf)) == at_boundary
    assert nehrp_class(boundary) == at_boundary
    assert nehrp_class(math.nextafter(boundary, math.inf)) == above_boundary


@pytest.mark.parametrize("vs30, expected", [
    (math.nextafter(0.0, math.inf), "E"),
    (100.0, "E"), (250.0, "D"), (500.0, "C"), (1000.0, "B"), (2000.0, "A"),
])
def test_positive_velocity_is_classified(vs30, expected):
    assert nehrp_class(vs30) == expected


def test_main_writes_missing_classes_without_querying_a_service(tmp_path, monkeypatch):
    # Gerçek istasyon dosyasına ve USGS servisine dokunmadan çıktı yolunu doğrula.
    path = tmp_path / "koeri_stations.csv"
    stations = pd.DataFrame({
        "station": ["SYN1", "SYN2", "SYN3", "SYN4"],
        "latitude": [0.0, 1.0, 2.0, 3.0],
        "longitude": [10.0, 11.0, 12.0, 13.0],
    })
    stations.to_csv(path, index=False)
    values = iter([760.0, math.nan, 0.0, -1.0])
    calls = []

    def fake_query(lat, lon):
        calls.append((lat, lon))
        return next(values)

    monkeypatch.setattr(fetch_vs30, "PROCESSED", tmp_path)
    monkeypatch.setattr(fetch_vs30, "query_vs30", fake_query)
    monkeypatch.setattr(fetch_vs30.time, "sleep", lambda _: None)
    fetch_vs30.main()
    output = pd.read_csv(path)
    pd.testing.assert_frame_equal(output[stations.columns], stations)
    assert calls == [(0.0, 10.0), (1.0, 11.0), (2.0, 12.0), (3.0, 13.0)]
    assert output.loc[0, "nehrp_site_class"] == "C"
    assert output.loc[1:, "nehrp_site_class"].isna().all()
