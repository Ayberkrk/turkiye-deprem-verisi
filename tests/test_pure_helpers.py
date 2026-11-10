"""Saf yardımcıların dönüşüm ve sınır sözleşmelerini sentetik girdilerle korur."""

import math

import pandas as pd
import pytest
from build_dataset import estimate_mw
from enrich_waveforms import desanitize_event_id
from fetch_orfeus_eida import _instrument_types
from fetch_waveforms_bulk import sanitize_event_id, station_had_usable_channel_at


@pytest.mark.parametrize("magnitude", [0.0, 4.12345, 7.5])
def test_moment_magnitude_is_preserved(magnitude):
    assert estimate_mw({"magnitude_scale_group": "moment_magnitude", "magnitude": magnitude}) == magnitude


@pytest.mark.parametrize("magnitude, expected", [(5.0, 4.68), (4.2, 4.12)])
def test_local_magnitude_is_converted_and_rounded(magnitude, expected):
    assert estimate_mw({"magnitude_scale_group": "local_magnitude", "magnitude": magnitude}) == expected


@pytest.mark.parametrize("group", ["body_wave_magnitude", "surface_wave_magnitude", "diger"])
def test_unsupported_magnitude_is_missing(group):
    assert math.isnan(estimate_mw({"magnitude_scale_group": group, "magnitude": 5.0}))


@pytest.mark.parametrize("event_id", ["us7000tctp", "smi:ISC/evid=12702302", "quakeml:eu.emsc/event/20140524_0000027"])
def test_event_id_roundtrip(event_id):
    encoded = sanitize_event_id(event_id)
    assert not any(character in encoded for character in ":/=")
    assert desanitize_event_id(encoded) == event_id


@pytest.mark.parametrize("event_time, expected", [
    ("2019-12-31", False), ("2020-01-01", True), ("2020-06-01", True),
    ("2021-01-01", True), ("2021-01-02", False),
])
def test_channel_active_interval_is_inclusive(event_time, expected):
    activity = pd.DataFrame({
        "earliest_start": [pd.Timestamp("2020-01-01", tz="UTC")],
        "latest_end": [pd.Timestamp("2021-01-01", tz="UTC")],
    }, index=pd.MultiIndex.from_tuples([("SYN", "strong_motion")]))
    assert bool(station_had_usable_channel_at(activity, "SYN", pd.Timestamp(event_time, tz="UTC"))) is expected


def test_missing_channel_table_preserves_fallback():
    assert station_had_usable_channel_at(None, "SYN", pd.Timestamp("2020-01-01", tz="UTC")) is True


@pytest.mark.parametrize("start, end", [("2020-01-01", None), (None, "2022-01-01"), (None, None)])
def test_open_channel_interval(start, end):
    activity = pd.DataFrame({
        "earliest_start": [pd.Timestamp(start, tz="UTC") if start else pd.NaT],
        "latest_end": [pd.Timestamp(end, tz="UTC") if end else pd.NaT],
    }, index=pd.MultiIndex.from_tuples([("SYN", "broadband")]))
    assert station_had_usable_channel_at(activity, "SYN", pd.Timestamp("2021-01-01", tz="UTC"))
    assert station_had_usable_channel_at(activity, "ABSENT", pd.Timestamp("2021-01-01", tz="UTC")) is False


@pytest.mark.parametrize("codes, expected", [
    ({"HNZ", "HNE", "HNN"}, "strong_motion"),
    ({"HHZ"}, "broadband"), ({"EHZ"}, "broadband"),
    ({"ELZ"}, "short_period"),
    ({"HNZ", "HHZ", "ELZ"}, "broadband,short_period,strong_motion"),
    (set(), "bilinmiyor"), ({"", "H", "XXZ"}, "bilinmiyor"),
])
def test_instrument_types_use_seed_instrument_character(codes, expected):
    assert _instrument_types(codes) == expected
