"""
scripts/expand_catalog.py'deki deduplikasyon yardımcı fonksiyonları için
birim testler: mesafe hesabı, büyüklüğe bağlı eşik ve kümeleme.
"""
import numpy as np
import pytest

from expand_catalog import (
    MAX_DISTANCE_KM,
    MAX_MAGNITUDE_DIFF,
    MIN_DISTANCE_KM,
    TIME_WINDOW_SEC,
    best_first_clusters,
    candidate_pairs,
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


def _clusters(events):
    """events: (zaman_sn, enlem, boylam, büyüklük, kaynak) listesi, zamana göre sıralı."""
    times, lats, lons, mags, sources = (np.array(col) for col in zip(*events))
    pairs = candidate_pairs(times, lats, lons, mags, sources)
    return best_first_clusters(times, sources, pairs)


def test_true_counterpart_wins_over_earlier_weak_match():
    # v2'deki hatanın reprodüksiyonu: USGS kaydı, 20 sn önceki ve ~45 km
    # uzaktaki başka bir ISC olayıyla da eşik içinde eşleşebiliyor. Zaman
    # sırasıyla açgözlü atama USGS'i o kümeye bağlıyor, aynı an ve aynı
    # konumdaki gerçek ISC eşi "kümede zaten ISC var" diye dışarıda kalıyordu.
    events = [
        (0.0, 36.90, 25.49, 4.4, "isc"),
        (20.0, 36.50, 25.49, 4.6, "usgs"),
        (20.0, 36.50, 25.49, 4.6, "isc"),
        (21.0, 36.52, 25.50, 4.5, "emsc"),
    ]

    cid = _clusters(events)

    assert cid[1] == cid[2] == cid[3]
    assert cid[0] != cid[1]


def test_same_source_events_never_share_a_cluster():
    events = [
        (0.0, 38.0, 37.0, 5.0, "isc"),
        (1.0, 38.0, 37.0, 5.0, "isc"),
        (2.0, 38.0, 37.0, 5.0, "usgs"),
    ]

    cid = _clusters(events)

    assert cid[0] != cid[1]
    assert cid[2] in (cid[0], cid[1])


def test_events_beyond_thresholds_stay_separate():
    base = (0.0, 38.0, 37.0, 4.0, "usgs")
    too_late = (TIME_WINDOW_SEC + 1.0, 38.0, 37.0, 4.0, "isc")
    too_far = (1.0, 40.0, 37.0, 4.0, "emsc")  # ~222 km
    cid = _clusters([base, too_far, too_late])
    assert len(set(cid)) == 3

    too_different = (1.0, 38.0, 37.0, 4.0 + MAX_MAGNITUDE_DIFF + 0.1, "isc")
    assert len(set(_clusters([base, too_different]))) == 2


def test_cluster_time_span_never_exceeds_window():
    # A-B ve B-C ayrı ayrı pencere içinde, ama A-C 40 sn: zincirleme
    # birleşme, 30 sn kuralını dolaylı yoldan delmemeli.
    events = [
        (0.0, 38.0, 37.0, 5.0, "usgs"),
        (20.0, 38.0, 37.0, 5.0, "isc"),
        (40.0, 38.0, 37.0, 5.0, "emsc"),
    ]

    cid = _clusters(events)

    assert cid[0] != cid[2]
    assert len(set(cid)) == 2


def test_candidate_pairs_score_prefers_closer_match():
    times = np.array([0.0, 1.0, 10.0])
    lats, lons = np.array([38.0, 38.0, 38.3]), np.array([37.0, 37.0, 37.0])
    mags, sources = np.array([5.0, 5.0, 5.0]), np.array(["usgs", "isc", "emsc"])

    scores = {(i, j): score for score, i, j in candidate_pairs(times, lats, lons, mags, sources)}

    assert set(scores) == {(0, 1), (0, 2), (1, 2)}
    assert scores[(0, 1)] > scores[(0, 2)]
    assert all(0.0 <= score <= 1.0 for score in scores.values())
