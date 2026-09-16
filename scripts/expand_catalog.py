"""
USGS kataloğunu EMSC ve ISC'nin FDSN olay servislerinden çekilen ek
kayıtlarla zenginleştirir ve aynı fiziksel depremi birden fazla kez
saymamak için zaman/konum/büyüklük bazlı bir eşleştirme (deduplikasyon)
uygular.

Neden gerekli: USGS'in küresel ağı, Türkiye'deki küçük/orta ölçekli
depremlerin bir kısmını yakalamıyor. ISC Bulletin (birçok ulusal ağın
verisini birleştiren en kapsamlı katalog) ve EMSC aynı zaman/bölge için
çok daha fazla olay bildiriyor (örnek: 2023-02-06 tek günü için
USGS 225, EMSC 369, ISC 613 olay).

Eşleştirme yöntemi (v2): tüm kaynaklardan gelen olaylar zamana göre
sıralanır. Bir olay, açık bir kümeye şu koşulların hepsi sağlanırsa
katılabilir:
  - zaman farkı <= 30 saniye
  - konum farkı <= büyüklüğe göre ölçeklenen eşik (50-150km arası;
    büyük depremlerin konum belirsizliği/farklı ağların hız modeli
    farkları daha büyük mesafe sapmasına yol açabiliyor)
  - büyüklük farkı <= 1.5 (farklı ölçek tipleri arasında beklenen
    olağan sapma payı; bunun üzerindeki fark muhtemelen farklı fiziksel
    olaylar demektir)
  - AYNI KAYNAKTAN gelen bir olay zaten o kümedeyse katılamaz (bir kurum
    aynı depremi iki kez bildirmez; aynı kaynaktan iki ayrı bildirim,
    yoğun artçı dizilerinde iki farklı fiziksel olay olma ihtimali
    yüksektir - v1'deki en büyük hata kaynağı buydu)

Birden fazla aday küme uyuyorsa, zaman/mesafe/büyüklük farkının en küçük
olduğu (en iyi eşleşen) küme seçilir. Her küme için bir `dedup_confidence`
(0-1) skoru üretilir; tek kaynaktan bildirilmiş (eşleşmesi gerekmeyen)
kümeler için bu değer 1.0'dır.

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

from geo import haversine_km

PROCESSED = Path("data/processed")
BBOX = dict(minlatitude=35.0, maxlatitude=43.0, minlongitude=25.0, maxlongitude=45.5)
START_YEAR = 1990
END_YEAR = 2026
MIN_MAGNITUDE = 3.0

TIME_WINDOW_SEC = 30
MIN_DISTANCE_KM = 50.0
MAX_DISTANCE_KM = 150.0
MAX_MAGNITUDE_DIFF = 1.5
SOURCE_PRIORITY = {"usgs": 0, "isc": 1, "emsc": 2}


def distance_threshold_km(magnitude: float) -> float:
    """Büyüklüğe göre ölçeklenen mesafe eşiği.

    Küçük bir depremin iki farklı kurum tarafından bildirilen konumları
    genelde birbirine yakın çıkar. Büyük bir depremde ise kurumlar farklı
    hız modelleri/istasyon dağılımı kullandığı için konum tahminleri daha
    fazla ayrışabilir. Bu yüzden sabit bir eşik yerine büyüklükle artan
    bir eşik kullanıyoruz.
    """
    return float(np.clip(50 + 10 * magnitude, MIN_DISTANCE_KM, MAX_DISTANCE_KM))


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

    n = len(all_events)
    times = all_events["time_utc"].values
    lats = all_events["latitude"].values
    lons = all_events["longitude"].values
    mags = all_events["magnitude"].values
    sources = all_events["source"].values

    cluster_id = np.full(n, -1)
    # Her açık küme için: temsilci (ilk giren) satırın index'i ve o kümede
    # şu ana kadar görülen kaynak isimleri (aynı kaynaktan ikinci bir olayı
    # o kümeye katmamak için).
    cluster_anchor = {}
    cluster_sources = {}
    open_cluster_ids = []
    next_cluster = 0

    for i in range(n):
        t = times[i]
        open_cluster_ids = [
            cid for cid in open_cluster_ids
            if (t - times[cluster_anchor[cid]]) / np.timedelta64(1, "s") <= TIME_WINDOW_SEC
        ]

        best_cid, best_score = None, -1.0
        for cid in open_cluster_ids:
            if sources[i] in cluster_sources[cid]:
                continue
            ridx = cluster_anchor[cid]
            d = haversine_km(lats[i], lons[i], lats[ridx], lons[ridx])
            dmag = abs(mags[i] - mags[ridx])
            thresh = distance_threshold_km(max(mags[i], mags[ridx]))
            if d > thresh or dmag > MAX_MAGNITUDE_DIFF:
                continue
            dt = abs((t - times[ridx]) / np.timedelta64(1, "s"))
            # 0-1 arası, düşük fark = yüksek skor
            score = (
                0.4 * (1 - dt / TIME_WINDOW_SEC)
                + 0.4 * (1 - d / thresh)
                + 0.2 * (1 - dmag / MAX_MAGNITUDE_DIFF)
            )
            if score > best_score:
                best_score, best_cid = score, cid

        if best_cid is None:
            best_cid = next_cluster
            next_cluster += 1
            cluster_anchor[best_cid] = i
            cluster_sources[best_cid] = set()
            open_cluster_ids.append(best_cid)

        cluster_sources[best_cid].add(sources[i])
        cluster_id[i] = best_cid

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

    # Küme kalite metrikleri: her kümenin içindeki en uzak zaman/mesafe/
    # büyüklük farkı ve bir güven skoru. Tekil (tek kaynaklı) kümeler
    # tanım gereği belirsizlik taşımaz, güven skoru 1.0 kabul edilir.
    cluster_quality_rows = []
    for cid, group in all_events.groupby("cluster_id"):
        if len(group) == 1:
            cluster_quality_rows.append(dict(
                cluster_id=cid, cluster_size=1,
                cluster_max_time_diff_sec=0.0, cluster_max_distance_km=0.0,
                cluster_max_magnitude_diff=0.0, dedup_confidence=1.0,
            ))
            continue
        g_times = group["time_utc"].values
        g_lats = group["latitude"].values
        g_lons = group["longitude"].values
        g_mags = group["magnitude"].values
        max_dt, max_d, max_dmag = 0.0, 0.0, 0.0
        for a in range(len(group)):
            for b in range(a + 1, len(group)):
                dt = abs((g_times[a] - g_times[b]) / np.timedelta64(1, "s"))
                d = haversine_km(g_lats[a], g_lons[a], g_lats[b], g_lons[b])
                dmag = abs(g_mags[a] - g_mags[b])
                max_dt, max_d, max_dmag = max(max_dt, dt), max(max_d, d), max(max_dmag, dmag)
        thresh = distance_threshold_km(max(g_mags))
        confidence = (
            0.4 * (1 - min(max_dt / TIME_WINDOW_SEC, 1.0))
            + 0.4 * (1 - min(max_d / thresh, 1.0))
            + 0.2 * (1 - min(max_dmag / MAX_MAGNITUDE_DIFF, 1.0))
        )
        cluster_quality_rows.append(dict(
            cluster_id=cid, cluster_size=len(group),
            cluster_max_time_diff_sec=round(max_dt, 2), cluster_max_distance_km=round(max_d, 2),
            cluster_max_magnitude_diff=round(max_dmag, 2), dedup_confidence=round(max(confidence, 0.0), 3),
        ))
    cluster_quality = pd.DataFrame(cluster_quality_rows).set_index("cluster_id")

    representative = (
        all_events.sort_values("source_priority")
        .groupby("cluster_id", as_index=False)
        .first()
    )
    representative = representative.merge(
        agencies.rename("reported_by"), left_on="cluster_id", right_index=True
    )
    representative = representative.merge(mag_stats, left_on="cluster_id", right_index=True)
    representative = representative.merge(cluster_quality, left_on="cluster_id", right_index=True)

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
    multi_source = deduped[deduped["cluster_size"] > 1]
    print(f"Birden fazla kaynaktan doğrulanmış olay: {len(multi_source)}")
    if len(multi_source) > 0:
        print(f"Ortalama dedup_confidence (çok kaynaklı kümeler): "
              f"{multi_source['dedup_confidence'].mean():.3f}")
        low_conf = multi_source[multi_source["dedup_confidence"] < 0.5]
        print(f"Düşük güvenli (dedup_confidence < 0.5) küme sayısı: {len(low_conf)}")

    out_path = PROCESSED / "turkiye_deprem_katalogu_genisletilmis.parquet"
    deduped.to_parquet(out_path, index=False)
    print(f"\nKaydedildi -> {out_path}")


if __name__ == "__main__":
    main()
