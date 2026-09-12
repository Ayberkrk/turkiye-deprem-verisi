"""
USGS kataloğunu EMSC ve ISC'nin FDSN olay servislerinden çekilen ek
kayıtlarla zenginleştirir ve aynı fiziksel depremi birden fazla kez
saymamak için zaman/konum bazlı bir eşleştirme (deduplikasyon) uygular.

Neden gerekli: USGS'in küresel ağı, Türkiye'deki küçük/orta ölçekli
depremlerin bir kısmını yakalamıyor. ISC Bulletin (birçok ulusal ağın
verisini birleştiren en kapsamlı katalog) ve EMSC aynı zaman/bölge için
çok daha fazla olay bildiriyor (örnek: 2023-02-06 tek günü için
USGS 225, EMSC 369, ISC 613 olay).

Eşleştirme yöntemi: tüm kaynaklardan gelen olaylar zamana göre sıralanır,
30 saniyelik bir pencere içinde ve 100km'den yakın olan kayıtlar aynı
fiziksel deprem olarak kümelenir. Her küme için USGS > ISC > EMSC
önceliğiyle bir "ana" kayıt seçilir, hangi kaynakların da aynı olayı
bildirdiği ayrı bir sütunda tutulur.

Kullanım:
    python scripts/expand_catalog.py
"""
import time
from pathlib import Path

import numpy as np
import pandas as pd
from obspy import UTCDateTime
from obspy.clients.fdsn import Client
from obspy.clients.fdsn.header import FDSNException

PROCESSED = Path("data/processed")
BBOX = dict(minlatitude=35.0, maxlatitude=43.0, minlongitude=25.0, maxlongitude=45.5)
START_YEAR = 1990
END_YEAR = 2026
MIN_MAGNITUDE = 3.0

TIME_WINDOW_SEC = 30
DISTANCE_WINDOW_KM = 100
SOURCE_PRIORITY = {"usgs": 0, "isc": 1, "emsc": 2}


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def fetch_source(source_name: str) -> pd.DataFrame:
    client = Client(source_name.upper())
    rows = []
    for year in range(START_YEAR, END_YEAR + 1):
        try:
            cat = client.get_events(
                starttime=UTCDateTime(f"{year}-01-01"), endtime=UTCDateTime(f"{year}-12-31"),
                minmagnitude=MIN_MAGNITUDE, **BBOX,
            )
        except FDSNException:
            continue
        except Exception as e:
            print(f"[UYARI] {source_name} {year}: {e}")
            continue
        for ev in cat:
            try:
                origin = ev.preferred_origin() or ev.origins[0]
                mag = ev.preferred_magnitude() or ev.magnitudes[0]
            except IndexError:
                continue
            rows.append(dict(
                source=source_name,
                source_event_id=str(ev.resource_id),
                time_utc=origin.time.datetime,
                latitude=origin.latitude,
                longitude=origin.longitude,
                depth_km=(origin.depth or 0) / 1000.0,
                magnitude=mag.mag,
                mag_type=(mag.magnitude_type or "").lower(),
            ))
        print(f"{source_name} {year}: {len(cat)} olay (toplam {len(rows)})")
        time.sleep(0.2)
    return pd.DataFrame(rows)


def deduplicate(all_events: pd.DataFrame) -> pd.DataFrame:
    all_events = all_events.copy()
    all_events["time_utc"] = pd.to_datetime(all_events["time_utc"], utc=True)
    all_events = all_events.sort_values("time_utc").reset_index(drop=True)

    cluster_id = np.full(len(all_events), -1)
    open_clusters = []  # (cluster_idx, temsilci_satır_index)
    next_cluster = 0

    times = all_events["time_utc"].values
    lats = all_events["latitude"].values
    lons = all_events["longitude"].values

    for i in range(len(all_events)):
        t = times[i]
        open_clusters = [
            (cid, ridx) for cid, ridx in open_clusters
            if (t - times[ridx]) / np.timedelta64(1, "s") <= TIME_WINDOW_SEC
        ]
        match = None
        for cid, ridx in open_clusters:
            d = haversine_km(lats[i], lons[i], lats[ridx], lons[ridx])
            if d <= DISTANCE_WINDOW_KM:
                match = cid
                break
        if match is None:
            match = next_cluster
            next_cluster += 1
            open_clusters.append((match, i))
        cluster_id[i] = match

    all_events["cluster_id"] = cluster_id
    all_events["source_priority"] = all_events["source"].map(SOURCE_PRIORITY)

    agencies = all_events.groupby("cluster_id")["source"].apply(lambda s: ",".join(sorted(set(s))))

    # Büyüklük tutarlılık kontrolü: aynı depremi birden fazla kurum
    # bildirdiğinde, bildirdikleri büyüklükler ne kadar uyuşuyor. Küçük
    # bir std, kurumların hemfikir olduğunu gösterir; büyük bir std, ya
    # farklı ölçek tipi (ml/mb/mw) kullanıldığını ya da veri kalitesi
    # sorununu işaret edebilir.
    mag_stats = all_events.groupby("cluster_id")["magnitude"].agg(
        magnitude_agreement_std="std", magnitude_report_count="count"
    )
    mag_stats["magnitude_agreement_std"] = mag_stats["magnitude_agreement_std"].fillna(0.0)

    representative = (
        all_events.sort_values("source_priority")
        .groupby("cluster_id", as_index=False)
        .first()
    )
    representative = representative.merge(
        agencies.rename("reported_by"), left_on="cluster_id", right_index=True
    )
    representative = representative.merge(mag_stats, left_on="cluster_id", right_index=True)

    # Her orijinal (kaynak, olay kimliği) çiftinin hangi temsilci kayda
    # devredildiğini kaydet. Bir olay başka bir olayla aynı kümeye
    # düştüğünde (örn. yoğun artçı dizisinde), kendi kimliği veri setinden
    # kaybolur ama dalga formu dosyaları hâlâ o eski kimlikle diskte durur.
    # Bu eşleme sayesinde build_dataset.py o dosyaları doğru (hayatta kalan)
    # olaya bağlayabiliyor.
    id_map = all_events[["source", "source_event_id", "cluster_id"]].merge(
        representative[["cluster_id", "source_event_id"]].rename(
            columns={"source_event_id": "representative_event_id"}
        ),
        on="cluster_id",
    )
    id_map[["source", "source_event_id", "representative_event_id"]].to_csv(
        PROCESSED / "event_id_cluster_map.csv", index=False
    )

    return representative.drop(columns=["cluster_id", "source_priority"])


RAW_CACHE_PATH = PROCESSED / "expanded_catalog_raw_cache.parquet"


def main():
    if RAW_CACHE_PATH.exists():
        print(f"Önbellekten okunuyor: {RAW_CACHE_PATH}")
        combined = pd.read_parquet(RAW_CACHE_PATH)
    else:
        usgs = pd.read_parquet(PROCESSED / "usgs_catalog_turkey.parquet")
        usgs_std = usgs.rename(columns={"event_id": "source_event_id"})[
            ["source_event_id", "time_utc", "latitude", "longitude", "depth_km", "magnitude", "mag_type"]
        ].copy()
        usgs_std["source"] = "usgs"

        print("EMSC çekiliyor...")
        emsc = fetch_source("emsc")
        print("\nISC çekiliyor...")
        isc = fetch_source("isc")

        combined = pd.concat([usgs_std, emsc, isc], ignore_index=True)
        combined = combined.dropna(subset=["latitude", "longitude", "magnitude"])
        combined.to_parquet(RAW_CACHE_PATH, index=False)

    print(f"\nBirleştirme öncesi toplam ham kayıt: {len(combined)}")

    deduped = deduplicate(combined)
    print(f"Deduplikasyon sonrası benzersiz deprem sayısı: {len(deduped)}")
    print(deduped["reported_by"].value_counts().head(10))

    out_path = PROCESSED / "turkiye_deprem_katalogu_genisletilmis.parquet"
    deduped.to_parquet(out_path, index=False)
    print(f"\nKaydedildi -> {out_path}")


if __name__ == "__main__":
    main()
