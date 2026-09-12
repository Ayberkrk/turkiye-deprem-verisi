"""
M>=4.5 depremler için, en yakın KOERI istasyonlarından toplu dalga formu çeker.

Küçük depremlerin sinyali mühendislik açısından daha az anlamlı, bu yüzden
M>=4.5 filtresiyle ~1.635 olaya iniyoruz ve her biri için en yakın 4
istasyonu, 400km'ye kadar deniyoruz. Eşiği M>=4.0'a çekmek istasyon
denemesini ~22.000'e çıkarıp KOERI'nin açık FDSN servisini saatlerce
meşgul ederdi; M>=4.5 önceki sürüme göre olay sayısını ~4 kat artırırken
makul bir sürede (~1-1.5 saat) tamamlanıyor.

Her (olay, istasyon) çifti tek tek isteniyor, diske yazılıyor ve bellekten
atılıyor. Sonuçlar CSV'ye satır satır eklenip flush ediliyor, yani program
yarıda kesilse bile o ana kadarki iş kaybolmaz. Yeniden çalıştırıldığında
log dosyasında zaten denenmiş çiftleri atlayıp kaldığı yerden devam eder.

Kullanım:
    python scripts/fetch_waveforms_bulk.py
"""
import csv
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from obspy import UTCDateTime
from obspy.clients.fdsn import Client
from obspy.clients.fdsn.header import FDSNException

PROCESSED = Path("data/processed")
WAVEFORM_DIR = PROCESSED / "waveforms"
LOG_PATH = PROCESSED / "waveform_fetch_log.csv"

MIN_MAGNITUDE = 4.5
STATIONS_PER_EVENT = 4
MAX_DISTANCE_KM = 400
WINDOW_BEFORE_SEC = 10
WINDOW_AFTER_SEC = 200
SLEEP_BETWEEN_REQUESTS = 0.4

client = Client("KOERI")


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def load_already_tried():
    if not LOG_PATH.exists():
        return set()
    df = pd.read_csv(LOG_PATH)
    return set(zip(df["event_id"], df["station"]))


def append_log(row: dict):
    is_new = not LOG_PATH.exists()
    with open(LOG_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if is_new:
            writer.writeheader()
        writer.writerow(row)
        f.flush()


def main():
    WAVEFORM_DIR.mkdir(parents=True, exist_ok=True)

    events = pd.read_parquet(PROCESSED / "usgs_catalog_turkey.parquet")
    events = events[events["magnitude"] >= MIN_MAGNITUDE].reset_index(drop=True)
    stations = pd.read_csv(PROCESSED / "koeri_stations.csv")
    stations["start_date_parsed"] = pd.to_datetime(stations["start_date"], utc=True, errors="coerce")

    already_tried = load_already_tried()
    print(f"{len(events)} olay (M>={MIN_MAGNITUDE}), {len(stations)} istasyon. "
          f"{len(already_tried)} çift daha önce denenmiş, atlanacak.")

    success_count, fail_count, skip_count = 0, 0, 0

    for i, ev in events.iterrows():
        event_time = ev["time_utc"]

        # O tarihte zaten kurulmuş olan istasyonlarla sınırla (henüz kurulmamış
        # bir istasyondan veri istemenin anlamı yok)
        active = stations[
            stations["start_date_parsed"].isna() | (stations["start_date_parsed"] <= event_time)
        ].copy()
        if active.empty:
            continue

        active["distance_km"] = haversine_km(
            ev["latitude"], ev["longitude"], active["latitude"], active["longitude"]
        )
        nearest = active.nsmallest(STATIONS_PER_EVENT, "distance_km")
        nearest = nearest[nearest["distance_km"] <= MAX_DISTANCE_KM]

        for _, sta in nearest.iterrows():
            key = (ev["event_id"], sta["station"])
            if key in already_tried:
                skip_count += 1
                continue

            out_path = WAVEFORM_DIR / f"{ev['event_id']}_{sta['station']}.mseed"
            t0 = UTCDateTime(event_time) - WINDOW_BEFORE_SEC
            t1 = UTCDateTime(event_time) + WINDOW_AFTER_SEC

            result_row = dict(
                event_id=ev["event_id"],
                station=sta["station"],
                distance_km=round(sta["distance_km"], 2),
                magnitude=ev["magnitude"],
                event_time=str(event_time),
                status=None,
                file=None,
                fetched_at=datetime.now(timezone.utc).isoformat(),
            )
            try:
                st = client.get_waveforms(
                    network="KO", station=sta["station"], location="*",
                    channel="HH*,HN*,EH*,BH*", starttime=t0, endtime=t1,
                )
                if len(st) == 0:
                    result_row["status"] = "no_data"
                    fail_count += 1
                else:
                    st.write(str(out_path), format="MSEED")
                    result_row["status"] = "ok"
                    result_row["file"] = str(out_path)
                    success_count += 1
            except FDSNException:
                result_row["status"] = "no_data"
                fail_count += 1
            except Exception as e:
                result_row["status"] = f"error: {type(e).__name__}"
                fail_count += 1

            append_log(result_row)
            time.sleep(SLEEP_BETWEEN_REQUESTS)

        if i % 20 == 0:
            print(f"[{i}/{len(events)}] olay işlendi | başarılı={success_count} "
                  f"veri_yok={fail_count} atlandı={skip_count}")

    print(f"\nTamamlandı. Başarılı: {success_count}, veri yok/hata: {fail_count}, "
          f"atlanan (önceden denenmiş): {skip_count}")
    print(f"Dalga formları: {WAVEFORM_DIR}/")
    print(f"Detaylı log: {LOG_PATH}")


if __name__ == "__main__":
    main()
