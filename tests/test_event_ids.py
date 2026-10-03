"""
scripts/event_ids.py: deduplikasyon öncesi kimliklerin temsilciye
eşlenmesi ve aynı (olay, istasyon) için yinelenen kayıtların tekilleştirilmesi.
"""
import pandas as pd

from event_ids import (
    collapse_duplicate_station_records,
    remap_to_representative,
    representative_id_lookup,
)


def _id_map():
    return pd.DataFrame(
        {
            "source": ["usgs", "isc", "emsc", "isc"],
            "source_event_id": ["us1", "isc1", "emsc1", "isc2"],
            "representative_event_id": ["us1", "us1", "us1", "isc2"],
        }
    )


def test_lookup_covers_every_source_not_only_usgs():
    # Eski kod yalnızca USGS kimliklerini eşliyordu; ISC/EMSC kimliğiyle
    # indirilmiş bir dosya, olayı başka bir temsilciye devredilince
    # ayrı bir deprem gibi kalıyordu.
    lookup = representative_id_lookup(_id_map())
    assert lookup["isc1"] == "us1"
    assert lookup["emsc1"] == "us1"
    assert lookup["isc2"] == "isc2"


def test_remap_keeps_unknown_ids_and_does_not_mutate_input():
    df = pd.DataFrame({"event_id": ["isc1", "bilinmeyen"]})
    out = remap_to_representative(df, representative_id_lookup(_id_map()))
    assert list(out["event_id"]) == ["us1", "bilinmeyen"]
    assert list(df["event_id"]) == ["isc1", "bilinmeyen"]


def test_remap_without_lookup_returns_input_unchanged():
    df = pd.DataFrame({"event_id": ["isc1"]})
    assert remap_to_representative(df, None) is df


def test_collapse_keeps_one_record_per_event_station_preferring_representative_file():
    table = pd.DataFrame(
        {
            "file_event_id": ["isc1", "us1", "us1", "isc2"],
            "event_id": ["us1", "us1", "us1", "isc2"],
            "station": ["KHMN", "KHMN", "GAZ", "KHMN"],
            "pga_g": [0.11, 0.10, 0.05, 0.02],
        }
    )

    out = collapse_duplicate_station_records(table, "file_event_id")

    assert len(out) == 3
    assert not out.duplicated(["event_id", "station"]).any()
    kept = out[(out["event_id"] == "us1") & (out["station"] == "KHMN")].iloc[0]
    assert kept["file_event_id"] == "us1"
    assert kept["pga_g"] == 0.10
