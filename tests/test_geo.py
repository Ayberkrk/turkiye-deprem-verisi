"""
scripts/geo.py'deki paylaşılan haversine_km için birim testler. Önceden
5 farklı script'te ayrı ayrı kopyalanmış olan bu fonksiyon artık tek bir
yerde tanımlı ve buradan test ediliyor (bkz. issue #12).
"""
import pytest

from geo import haversine_km


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


def test_haversine_antipodal_points_are_half_circumference():
    # 180 derece boylam farkı, ekvator üzerinde küre çevresinin yarısına
    # (pi * r) karşılık gelir.
    d = haversine_km(0.0, 0.0, 0.0, 180.0)
    assert d == pytest.approx(20015.09, rel=1e-3)
