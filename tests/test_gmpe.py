"""
scripts/gmpe.py: Akkar, Sandıkkaya ve Bommer (2014) PGA modeli.

Beklenen değerler, OpenQuake Engine'in bu model için kullandığı
doğrulama tablolarından alınmış satırlardır
(openquake/hazardlib/tests/gsim/data/AKKAR14/AKKAR_2014_{RHYPO,REPI}_MEAN.csv):
(Mw, rake, mesafe km, Vs30 m/s, medyan PGA g). Satırlar menteşe
büyüklüğünün (6.75) iki yanını, üç faylanma tipini ve zemin teriminin üç
bölgesini (Vs30 < 750, 750-1000, > 1000) kapsıyor. Tabloların tamamı
(540'ar satır) yerelde karşılaştırıldığında en büyük göreli fark 5e-9.
"""
import numpy as np
import pytest

from gmpe import ASB14_SIGMA_LN, akkar2014_pga_g

RHYPO_CASES = [
    (5, -90, 10, 570, 1.11411821e-01),
    (5, 90, 10, 1100, 1.09428803e-01),
    (5, 0, 200, 180, 9.86674753e-04),
    (5, -90, 200, 800, 4.75666516e-04),
    (7, -90, 10, 1100, 4.60476895e-01),
    (7, 90, 10, 180, 4.86111124e-01),
    (7, 90, 10, 1100, 5.64004754e-01),
    (8, 0, 0, 180, 8.67650769e-01),
    (8, -90, 10, 800, 6.34002598e-01),
]
REPI_CASES = [
    (5, -90, 10, 570, 7.58078724e-02),
    (5, 90, 10, 1100, 7.41076157e-02),
    (5, 0, 200, 180, 1.06731327e-03),
    (5, -90, 200, 800, 5.14789641e-04),
    (7, -90, 10, 1100, 3.32788400e-01),
    (7, 90, 10, 180, 3.77793053e-01),
    (7, 90, 10, 1100, 4.07608376e-01),
    (8, 0, 0, 180, 6.29629471e-01),
    (8, -90, 10, 800, 4.64191519e-01),
]


def _predict(case, distance_type):
    mag, rake, distance, vs30, _ = case
    return akkar2014_pga_g(mag, distance, vs30, distance_type,
                           normal_fault=rake == -90, reverse_fault=rake == 90)


@pytest.mark.parametrize("case", RHYPO_CASES)
def test_hypocentral_model_matches_reference_table(case):
    assert _predict(case, "rhypo") == pytest.approx(case[-1], rel=1e-6)


@pytest.mark.parametrize("case", REPI_CASES)
def test_epicentral_model_matches_reference_table(case):
    assert _predict(case, "repi") == pytest.approx(case[-1], rel=1e-6)


def test_pga_decreases_with_distance_and_increases_with_magnitude():
    distances = np.array([5.0, 20.0, 80.0, 200.0])
    pga = akkar2014_pga_g(6.0, distances, 400.0)
    assert np.all(np.diff(pga) < 0)
    assert akkar2014_pga_g(6.5, 30.0, 400.0) > akkar2014_pga_g(5.0, 30.0, 400.0)


def test_soft_soil_amplifies_weak_motion_relative_to_rock():
    # Zayıf harekette (uzak, küçük deprem) doğrusal olmayan terim önemsiz;
    # yumuşak zemin kayaya göre büyütme yapmalı.
    assert akkar2014_pga_g(5.0, 150.0, 250.0) > akkar2014_pga_g(5.0, 150.0, 800.0)


def test_accepts_arrays_and_scalars_consistently():
    mags, dists, vs30 = np.array([5.0, 7.0]), np.array([10.0, 50.0]), np.array([300.0, 900.0])
    vector = akkar2014_pga_g(mags, dists, vs30)
    for i in range(2):
        assert vector[i] == pytest.approx(float(akkar2014_pga_g(mags[i], dists[i], vs30[i])))


def test_sigma_table_has_both_distance_types():
    assert set(ASB14_SIGMA_LN) == {"rhypo", "repi"}
