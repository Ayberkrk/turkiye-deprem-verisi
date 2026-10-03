"""
scripts/windows.py: kayıt pencereleri örtüşen olayların gruplanması ve
penceredeki başka depremlerin tespiti.
"""
import numpy as np
import pandas as pd
import pytest

from build_benchmarks import event_split, split_key
from windows import (
    RECORD_WINDOW_SEC,
    add_window_context,
    assign_window_groups,
    largest_other_event_magnitude,
)


def _times(seconds_by_id):
    base = pd.Timestamp("2023-02-06T13:00:00Z")
    return pd.Series({eid: base + pd.Timedelta(seconds=s) for eid, s in seconds_by_id.items()})


def test_events_with_overlapping_windows_share_a_group():
    # a-b 100 sn, b-c 150 sn: a ve c arası 250 sn olsa da b üzerinden
    # zincirleme örtüşüyorlar (b'nin kaydı ikisiyle de örnek paylaşır).
    groups = assign_window_groups(_times({"c": 250, "a": 0, "b": 100, "d": 1000}))

    assert groups["a"] == groups["b"] == groups["c"] == "a"
    assert groups["d"] == "d"


def test_group_boundary_is_the_record_window_length():
    groups = assign_window_groups(_times({"a": 0, "b": RECORD_WINDOW_SEC, "c": 2 * RECORD_WINDOW_SEC + 1}))
    assert groups["a"] == groups["b"]
    assert groups["c"] == "c"


def test_isolated_event_keeps_its_own_id_so_its_split_is_unchanged():
    groups = assign_window_groups(_times({"us7000pufv": 0, "us6000jlrt": 5000}))
    assert groups["us7000pufv"] == "us7000pufv"
    assert event_split(groups["us7000pufv"]) == event_split("us7000pufv")


def test_split_by_group_never_separates_overlapping_events():
    # event_id bazlı bölmede bu iki olayın farklı bölmelere düştüğü
    # bilinen bir çift: grup anahtarıyla bölündüklerinde aynı bölmede kalmalılar.
    ids = [f"event_{i}" for i in range(200)]
    first = ids[0]
    partner = next(e for e in ids[1:] if event_split(e) != event_split(first))
    table = pd.DataFrame({"event_id": [first, partner]})
    assert event_split(first) != event_split(partner)

    table["window_group"] = table["event_id"].map(assign_window_groups(_times({first: 0, partner: 60})))

    assert split_key(table).map(event_split).nunique() == 1


def test_split_key_falls_back_to_event_id_without_window_group():
    table = pd.DataFrame({"event_id": ["a", "b"]})
    assert list(split_key(table)) == ["a", "b"]


def _catalog_arrays(rows):
    ids, secs, mags = zip(*rows)
    return np.array(ids), (np.array(secs) * 1e9).astype("int64"), np.array(mags, dtype=float)


def test_largest_other_event_excludes_the_event_itself():
    ids, times, mags = _catalog_arrays([("main", 1000, 7.8), ("after", 1090, 4.6)])
    assert largest_other_event_magnitude(ids, times, mags, "after", times[1]) == 7.8
    assert largest_other_event_magnitude(ids, times, mags, "main", times[0]) == 4.6


def test_largest_other_event_respects_window_and_lookback():
    ids, times, mags = _catalog_arrays([("early", 0, 6.0), ("e", 1000, 4.5), ("late", 1300, 6.5)])
    # 1000 sn önceki ve pencere bitiminden (200 sn) sonraki olaylar dışarıda.
    assert np.isnan(largest_other_event_magnitude(ids, times, mags, "e", times[1]))

    ids, times, mags = _catalog_arrays([("coda", 900, 6.0), ("e", 1000, 4.5), ("inside", 1150, 3.2)])
    assert largest_other_event_magnitude(ids, times, mags, "e", times[1]) == 6.0


def test_add_window_context_flags_only_records_with_equal_or_larger_other_event():
    catalog = pd.DataFrame(
        {
            "event_id": ["main", "after", "small", "alone"],
            "time_utc": pd.to_datetime(
                ["2023-02-06T10:24:49Z", "2023-02-06T10:26:00Z", "2023-02-06T10:27:00Z", "2024-01-01T00:00:00Z"]
            ),
            "magnitude": [7.5, 4.6, 3.1, 5.0],
        }
    )
    table = pd.DataFrame(
        {
            "event_id": ["main", "after", "alone"],
            "station": ["KHMN", "KHMN", "GAZ"],
            "time_utc": ["2023-02-06T10:24:49Z", "2023-02-06T10:26:00Z", "2024-01-01T00:00:00Z"],
            "magnitude": [7.5, 4.6, 5.0],
        }
    )

    out = add_window_context(table, catalog).set_index("event_id")

    # Artçının penceresinde ana şok var: tepe değer artçıya ait sayılamaz.
    assert bool(out.loc["after", "label_ambiguous"])
    assert out.loc["after", "window_other_max_magnitude"] == 7.5
    # Ana şokun penceresindeki artçılar daha küçük: etiket güvenilir.
    assert not bool(out.loc["main", "label_ambiguous"])
    assert out.loc["main", "window_other_max_magnitude"] == 4.6
    assert not bool(out.loc["alone", "label_ambiguous"])
    assert np.isnan(out.loc["alone", "window_other_max_magnitude"])
    assert out.loc["main", "window_group"] == out.loc["after", "window_group"] == "main"
    assert out.loc["alone", "window_group"] == "alone"
