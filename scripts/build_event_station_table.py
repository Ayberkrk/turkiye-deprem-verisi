"""
Olay bazlı özet tablonun aksine, her satırı TEK BİR deprem-istasyon
çiftini temsil eden ayrı bir tablo üretir.

Neden gerekli: `turkiye_deprem_veriseti_v3.parquet` içindeki `max_pga_g`,
bir olay için indirilen BİRDEN FAZLA istasyon kaydı arasındaki en yüksek
değeri temsil ediyor. Bu değer, aynı olayın `nearest_strong_motion_station`
alanındaki istasyonuna ait olmak zorunda değil - max PGA başka bir
istasyondan, mesafe ise en yakın istasyondan gelebiliyordu. Bu, PGA-mesafe
(azalım) grafiğinde fiziksel olarak tutarsız noktalar üretiyordu.

Bu script her (event_id, station) çifti için mesafeyi ve PGA/PGV/SNR
değerlerini AYNI satırdan alarak bu sorunu çözüyor.

Kullanım:
    python scripts/build_event_station_table.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from build_dataset import estimate_mw, magnitude_scale_group  # noqa: E402

PROCESSED = Path("data/processed")


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def hypocentral_km(epicentral_km, depth_km):
    return np.sqrt(epicentral_km ** 2 + depth_km ** 2)


def main():
    expanded_path = PROCESSED / "turkiye_deprem_katalogu_genisletilmis.parquet"
    usgs_path = PROCESSED / "usgs_catalog_turkey.parquet"
    stations_path = PROCESSED / "koeri_stations.csv"
    features_path = PROCESSED / "waveform_features.csv"
    id_map_path = PROCESSED / "event_id_cluster_map.csv"

    if not features_path.exists():
        print("Önce scripts/enrich_waveforms.py çalıştırılmalı.")
        return
    if not stations_path.exists():
        print("Önce scripts/fetch_orfeus_eida.py çalıştırılmalı.")
        return

    if expanded_path.exists():
        events = pd.read_parquet(expanded_path).rename(columns={"source_event_id": "event_id"})
    elif usgs_path.exists():
        events = pd.read_parquet(usgs_path)
    else:
        print("Önce scripts/download_usgs.py veya scripts/expand_catalog.py çalıştırılmalı.")
        return

    stations = pd.read_csv(stations_path)
    features = pd.read_csv(features_path)

    # Waveform dosyaları, deduplikasyon öncesi (ör. USGS) kimlikleriyle
    # diske yazılmış olabilir. build_dataset.py'deki gibi, hayatta kalan
    # temsilci kimliğe eşliyoruz.
    if id_map_path.exists():
        id_map = pd.read_csv(id_map_path)
        usgs_map = id_map[id_map["source"] == "usgs"].set_index("source_event_id")["representative_event_id"]
        features = features.copy()
        features["event_id"] = features["event_id"].map(usgs_map).fillna(features["event_id"])

    events_cols = ["event_id", "latitude", "longitude", "depth_km", "magnitude", "mag_type", "time_utc"]
    if "mw_estimate" not in events.columns:
        events["magnitude_scale_group"] = events["mag_type"].apply(magnitude_scale_group)
        events["mw_estimate"] = events.apply(estimate_mw, axis=1)
    events_cols.append("mw_estimate")
    events_small = events[events_cols].rename(
        columns={"latitude": "event_latitude", "longitude": "event_longitude"}
    )
    stations_small = stations[
        ["station", "latitude", "longitude", "vs30_ms", "nehrp_site_class", "has_strong_motion"]
    ].rename(columns={"latitude": "station_latitude", "longitude": "station_longitude"})

    table = features.merge(events_small, on="event_id", how="inner")
    table = table.merge(stations_small, on="station", how="left")

    table["epicentral_distance_km"] = haversine_km(
        table["event_latitude"], table["event_longitude"],
        table["station_latitude"], table["station_longitude"],
    ).round(2)
    table["hypocentral_distance_km"] = hypocentral_km(
        table["epicentral_distance_km"], table["depth_km"].fillna(0)
    ).round(2)

    out_columns = [
        "event_id", "station", "network", "location", "channel_used", "instrument_type_used",
        "event_latitude", "event_longitude", "depth_km", "station_latitude", "station_longitude",
        "epicentral_distance_km", "hypocentral_distance_km", "magnitude", "mag_type",
        "mw_estimate", "time_utc",
        "pga_g", "pgv_cms", "snr_db", "vs30_ms", "nehrp_site_class", "has_strong_motion",
        "sa_g_0_1s", "sa_g_0_2s", "sa_g_0_5s", "sa_g_1_0s", "sa_g_2_0s",
        "arias_intensity_ms", "cav_ms", "duration_5_95_sec",
        "fas_dominant_freq_hz", "fas_mean_freq_hz",
        "p_pick_time", "s_pick_time", "p_pick_confidence", "s_pick_confidence",
        "response_removed_ok", "usable_for_engineering", "usable_for_phase_picking", "qc_flags",
        "file",
    ]
    out_columns = [c for c in out_columns if c in table.columns]
    table = table[out_columns].sort_values(["event_id", "epicentral_distance_km"])

    out_path = PROCESSED / "event_station_table.csv"
    table.to_csv(out_path, index=False)

    print(f"Olay-istasyon tablosu hazır -> {out_path} ({len(table)} satır)")
    print(f"  PGA değeri olan satır: {table['pga_g'].notna().sum()}")
    print(f"  Mühendislik için kullanılabilir (usable_for_engineering) satır: "
          f"{table['usable_for_engineering'].sum() if 'usable_for_engineering' in table.columns else 'n/a'}")


if __name__ == "__main__":
    main()
