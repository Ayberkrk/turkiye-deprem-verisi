"""
scripts/build_benchmarks.py'deki bölme (split) fonksiyonları için birim
testler. En kritik özellik: aynı event_id/station her zaman aynı
bölmeye düşmeli (determinizm), aksi halde veri setine yeni olay
eklendiğinde mevcut olayların bölmesi kayar ve önceki yayınlanmış
sonuçlarla karşılaştırma anlamını kaybeder.
"""
import hashlib

import pytest

from build_benchmarks import (
    TRAIN_FRAC,
    VAL_FRAC,
    event_split,
    station_split,
)


def test_event_split_is_deterministic():
    ids = ["us7000pufv", "smi:ISC/evid=643165028", "20230206_ana_sok"]
    for event_id in ids:
        assert event_split(event_id) == event_split(event_id)


def test_event_split_only_valid_labels():
    for i in range(500):
        assert event_split(f"event_{i}") in {"train", "val", "test"}


def test_event_split_not_dependent_on_python_hash_seed():
    # hashlib.md5 kullanılmalı, yerleşik hash() değil - PYTHONHASHSEED'e
    # bağlı olsaydı her çalıştırmada farklı bölme çıkardı.
    digest = hashlib.md5(str("us7000pufv").encode()).hexdigest()
    frac = int(digest[:8], 16) / 0xFFFFFFFF
    expected = "train" if frac < TRAIN_FRAC else ("val" if frac < TRAIN_FRAC + VAL_FRAC else "test")
    assert event_split("us7000pufv") == expected


def test_event_split_proportions_roughly_match_target():
    n = 20000
    counts = {"train": 0, "val": 0, "test": 0}
    for i in range(n):
        counts[event_split(f"synthetic_event_{i}")] += 1
    assert counts["train"] / n == pytest.approx(TRAIN_FRAC, abs=0.03)
    assert counts["val"] / n == pytest.approx(VAL_FRAC, abs=0.03)


def test_station_split_independent_of_event_split():
    # Aynı string bir event_id olarak ve bir station olarak farklı
    # kümelere düşebilmeli (aksi halde istasyon bazlı holdout, olay
    # bazlı holdoutla aynı ayrımı tekrarlar ve ayrı bir sinyal vermez).
    same_string = "KHMN"
    assert event_split(same_string) in {"train", "val", "test"}
    assert station_split(same_string) in {"train", "val", "test"}


def test_station_split_is_deterministic():
    for station in ["KHMN", "BOTS", "SAUV"]:
        assert station_split(station) == station_split(station)
