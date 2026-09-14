"""
scripts/expand_catalog.py'deki deduplikasyon yardımcı fonksiyonları için
birim testler: mesafe hesabı ve büyüklüğe bağlı eşik.
"""
import numpy as np
import pytest

from expand_catalog import (
    MAX_DISTANCE_KM,
    MIN_DISTANCE_KM,
    distance_threshold_km,
    haversine_km,
)


def test_haversine_zero_distance():
    assert haversine_km(39.0, 35.0, 39.0, 35.0) == pytest.approx(0.0, abs=1e-9)


def test_haversine_known_distance():
    # İstanbul (41.0082, 28.9784) - Ankara (39.9334, 32.8597): gerçek
    # büyük daire mesafesi ~349 km (referans: harici GIS hesaplayıcı).
    d = haversine_km(41.0082, 28.9784, 39.9334, 32.8597)
    assert d == pytest.approx(349.0, rel=0.02)


def test_haversine_symmetric():
    d1 = haversine_km(38.0, 27.0, 40.0, 30.0)
    d2 = haversine_km(40.0, 30.0, 38.0, 27.0)
    assert d1 == pytest.approx(d2)


def test_distance_threshold_respects_bounds():
    assert distance_threshold_km(0.0) == MIN_DISTANCE_KM
    assert distance_threshold_km(20.0) == MAX_DISTANCE_KM


def test_distance_threshold_increases_with_magnitude():
    small = distance_threshold_km(3.0)
    large = distance_threshold_km(6.0)
    assert large > small


def test_distance_threshold_matches_formula_in_valid_range():
    # 50 + 10*büyüklük formülü sadece MIN/MAX arasında kaldığı sürece geçerli.
    for mag in np.arange(0.5, 9.5, 0.5):
        expected = np.clip(50 + 10 * mag, MIN_DISTANCE_KM, MAX_DISTANCE_KM)
        assert distance_threshold_km(mag) == pytest.approx(expected)
