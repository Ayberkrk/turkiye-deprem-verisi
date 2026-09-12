"""
Genişletilmiş (USGS+EMSC+ISC, deduplike) katalogdaki büyük depremler için,
en yakın KOERI istasyonlarından toplu dalga formu çeker.

v2 notu: Bu script önceden yalnızca `usgs_catalog_turkey.parquet` üzerinden
çalışıyordu, yani dalga formu araması sadece USGS'in bildirdiği olaylarla
sınırlıydı. Artık genişletilmiş/deduplike katalog kullanılıyor, böylece
sadece EMSC/ISC tarafından bildirilmiş (USGS'te bulunmayan) büyük olaylar
da dalga formu aramasına dahil oluyor. Genişletilmiş katalog yoksa (ör.
scripts/expand_catalog.py hiç çalıştırılmamışsa) USGS kataloğuna geri
düşülür ve bu durum ekrana açıkça yazdırılır.

Büyüklük filtresi artık ham `magnitude` yerine `mw_estimate` (moment
büyüklüğüne yaklaşık, ölçek-homojen değer) üzerinden uygulanıyor; farklı
kurumlar farklı büyüklük ölçekleri (ml/mb/md/mw) kullandığı için doğrudan
ham değer üzerinden filtrelemek ölçek karışıklığına yol açabilir.
mw_estimate hesaplanamayan (mb/md/ms gibi) kayıtlarda ham büyüklük değeri
kullanılıyor.

Küçük depremlerin sinyali mühendislik açısından daha az anlamlı, bu yüzden
M>=4.5 filtresiyle sınırlı bir olay kümesi üzerinde, her biri için en
yakın 4 istasyonu, 400km'ye kadar deniyoruz.

Her (olay, istasyon) çifti tek tek isteniyor, diske yazılıyor ve bellekten
atılıyor. Sonuçlar CSV'ye satır satır eklenip flush ediliyor, yani program
yarıda kesilse bile o ana kadarki iş kaybolmaz. Yeniden çalıştırıldığında
log dosyasında zaten denenmiş çiftleri atlayıp kaldığı yerden devam eder.

Kullanım:
    python scripts/fetch_waveforms_bulk.py
"""
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from obspy import UTCDateTime
from obspy.clients.fdsn import Client
from obspy.clients.fdsn.header import FDSNException

sys.path.insert(0, str(Path(__file__).parent))
from build_dataset import estimate_mw, magnitude_scale_group  # noqa: E402

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

# Log şeması sabit tutulur ki dosya, eski/yeni sütun sayısı karışık
# (bozuk) bir CSV'ye dönüşmesin. Yeni bir sütun eklenirse burada
# EXPECTED_LOG_COLUMNS güncellenmeli ve _migrate_log_if_needed eski
# satırları da bu şemaya taşımalı.
EXPECTED_LOG_COLUMNS = [
    "event_id", "station", "distance_km", "magnitude", "event_time",
    "event_source", "status", "file", "fetched_at",
]


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def sanitize_event_id(event_id: str) -> str:
    """USGS olay kimlikleri düz alfanümerik (ör. us7000tctp), ama EMSC/ISC
    kimlikleri ":" ve "/" gibi dosya sisteminde özel anlamı olan karakterler
    içeriyor (ör. "smi:ISC/evid=12702302"). Bunları doğrudan dosya adında
    kullanmak "/" nedeniyle var olmayan bir alt dizine yazmaya çalışıp
    FileNotFoundError'a yol açıyor. Bu fonksiyon, dosya adı için güvenli ve
    tersine çevrilebilir bir kodlama uygular (bkz. enrich_waveforms.py'deki
    desanitize_event_id ile eşleşmeli)."""
    return event_id.replace(":", "-c-").replace("/", "-s-").replace("=", "-e-")


def _migrate_log_if_needed():
    """Log dosyası eski şemadaysa (ör. event_source sütunu eklenmeden
    önce yazılmışsa) eksik sütunları doldurup yeni şemaya taşır. Bunu
    yapmazsak eski (8 sütunlu) satırlarla yeni (9 sütunlu) satırlar aynı
    dosyada karışır ve dosya pandas ile okunamaz hale gelir."""
    if not LOG_PATH.exists():
        return
    existing = pd.read_csv(LOG_PATH, nrows=1)
    if list(existing.columns) == EXPECTED_LOG_COLUMNS:
        return
    print("[BİLGİ] waveform_fetch_log.csv eski şemada, yeni sütunlarla yeniden yazılıyor.")
    df = pd.read_csv(LOG_PATH)
    if "event_source" not in df.columns:
        # Bu script'in event_source eklenmeden önceki tüm çalıştırmaları
        # yalnızca USGS kataloğu üzerinden yapılıyordu.
        df["event_source"] = "usgs"
    df = df[EXPECTED_LOG_COLUMNS]
    df.to_csv(LOG_PATH, index=False)


def load_already_tried():
    if not LOG_PATH.exists():
        return set()
    df = pd.read_csv(LOG_PATH)
    return set(zip(df["event_id"], df["station"]))


def append_log(row: dict):
    is_new = not LOG_PATH.exists()
    with open(LOG_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=EXPECTED_LOG_COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)
        f.flush()


def load_candidate_events():
    expanded_path = PROCESSED / "turkiye_deprem_katalogu_genisletilmis.parquet"
    usgs_path = PROCESSED / "usgs_catalog_turkey.parquet"

    if expanded_path.exists():
        events = pd.read_parquet(expanded_path).rename(columns={"source_event_id": "event_id"})
        events["magnitude_scale_group"] = events["mag_type"].apply(magnitude_scale_group)
        events["mw_estimate"] = events.apply(estimate_mw, axis=1)
        events["filter_magnitude"] = events["mw_estimate"].fillna(events["magnitude"])
        events = events[events["filter_magnitude"] >= MIN_MAGNITUDE].reset_index(drop=True)
        print(f"Genişletilmiş katalog kullanılıyor ({expanded_path.name}).")
        return events
    if usgs_path.exists():
        print("[UYARI] Genişletilmiş katalog bulunamadı, yalnızca USGS kataloğu kullanılıyor. "
              "Bu, dalga formu aramasının sadece USGS kaynaklı olaylarla sınırlı kalacağı "
              "anlamına gelir (bkz. DATA_CARD.md).")
        events = pd.read_parquet(usgs_path)
        events["source"] = "usgs"
        events["reported_by"] = "usgs"
        events["filter_magnitude"] = events["magnitude"]
        return events[events["filter_magnitude"] >= MIN_MAGNITUDE].reset_index(drop=True)
    raise SystemExit("Önce scripts/download_usgs.py veya scripts/expand_catalog.py çalıştırılmalı.")


def main():
    WAVEFORM_DIR.mkdir(parents=True, exist_ok=True)
    _migrate_log_if_needed()

    events = load_candidate_events()
    stations = pd.read_csv(PROCESSED / "koeri_stations.csv")
    stations["start_date_parsed"] = pd.to_datetime(stations["start_date"], utc=True, errors="coerce")

    already_tried = load_already_tried()
    print(f"{len(events)} olay (mw_estimate/magnitude >= {MIN_MAGNITUDE}), {len(stations)} istasyon. "
          f"{len(already_tried)} çift daha önce denenmiş, atlanacak.")

    success_count, fail_count, skip_count = 0, 0, 0
    per_source_success = {}

    for i, ev in events.iterrows():
        event_time = ev["time_utc"]
        event_source = ev.get("reported_by", ev.get("source", "usgs"))

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

            out_path = WAVEFORM_DIR / f"{sanitize_event_id(ev['event_id'])}_{sta['station']}.mseed"
            t0 = UTCDateTime(event_time) - WINDOW_BEFORE_SEC
            t1 = UTCDateTime(event_time) + WINDOW_AFTER_SEC

            result_row = dict(
                event_id=ev["event_id"],
                station=sta["station"],
                distance_km=round(sta["distance_km"], 2),
                magnitude=ev["magnitude"],
                event_time=str(event_time),
                event_source=event_source,
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
                    per_source_success[event_source] = per_source_success.get(event_source, 0) + 1
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
    print("Kaynak bazında başarılı indirme sayısı (event_source alanına göre):")
    for src, count in sorted(per_source_success.items(), key=lambda x: -x[1]):
        print(f"  {src}: {count}")
    print(f"Dalga formları: {WAVEFORM_DIR}/")
    print(f"Detaylı log: {LOG_PATH}")


if __name__ == "__main__":
    main()
