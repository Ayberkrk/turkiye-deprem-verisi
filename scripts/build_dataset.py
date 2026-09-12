"""
Genişletilmiş deprem kataloğunu (USGS+EMSC+ISC, deduplike edilmiş), KOERI
istasyon envanterini, dalga formu erişilebilirliğini ve sinyal
özniteliklerini (PGA/PGV/SNR/faz okuması) tek bir veri setinde birleştirir.

v3 notları:
- Katalog artık sadece USGS değil, scripts/expand_catalog.py'nin ürettiği
  genişletilmiş ve deduplike edilmiş katalog (83.598 olay, önceki 15.782'ye
  göre ~5 kat daha fazla). "place/status/source" gibi bazı USGS'e özel
  metin alanları, olay başka bir kurumdan geliyorsa boş olabilir.
- "En yakın istasyon" yerine "en yakın GÜÇLÜ HAREKET istasyonu" da ayrıca
  hesaplanıyor. Genel bir broadband sismometre PGA/tasarım spektrumu için
  güvenilir değildir, bu yüzden ayrım gerekiyor.
- Her olay için gerçekten indirilmiş dalga formu olup olmadığı
  (has_waveform, num_waveform_files) eklendi.
- Karışık büyüklük ölçekleri (md/mb/ml/mw...) tek bir magnitude_scale_group
  sütununda gruplanıyor; bu ölçekler birbirine doğrudan denk değil.
- mw_estimate: ML tipi büyüklükler, Marmara Bölgesi için türetilmiş
  Mw = 0.7018*ML + 1.1715 ampirik denklemiyle (Şahin ve diğerleri, 2018,
  Uygulamalı Yerbilimleri Dergisi 17(2):193-201) Mw'ye yaklaşık olarak
  çevriliyor. Zaten Mw olan kayıtlar olduğu gibi bırakılıyor. Bu bölgesel
  bir formül; ulusal ölçekte kaba bir yaklaşıklık sağlıyor, kesin bir
  dönüşüm değil.
  mb/md/ms için Türkiye'ye özel, serbestçe erişilebilir bir katsayı
  bulunamadığından bu tipler dönüştürülmüyor (mw_estimate boş kalıyor).
- Dalga formu bulunan olaylar için en yüksek PGA/PGV değeri ve en iyi
  SNR ana veri setine ekleniyor.
- En yakın güçlü hareket istasyonunun Vs30 (zemin sınıfı) değeri ve NEHRP
  sınıfı (A-E) ekleniyor. Kaynak: USGS Global Vs30 Mosaic (public domain,
  nokta sorgusu ile, dosya indirilmeden).

Girdiler küçük olduğu için (KB-MB) tamamen pandas ile RAM'de işleniyor.
"""
from pathlib import Path

import numpy as np
import pandas as pd

PROCESSED = Path("data/processed")

# Moment magnitude (Mw) ailesi: fiziksel olarak en tutarlı ölçek, büyük
# depremler için tercih edilir. Diğerleri (md=duration, ml=local,
# mb=body-wave) küçük/orta depremlerde kullanılır ve Mw ile birebir denk
# değil.
MOMENT_MAGNITUDE_TYPES = {"mw", "mww", "mwc", "mwr", "mwb"}

# Marmara Bölgesi için türetilmiş ampirik ML->Mw dönüşümü. Kaynak:
# Şahin, Y.E., Irmak, T.S., Livaoğlu, H., Yavuz, E. (2018).
# "Marmara Bölgesi Orta-Küçük Depremlerinin Mw-ML Dönüşüm Bağıntısı."
# Uygulamalı Yerbilimleri Dergisi, 17(2), 193-201.
# https://dergipark.org.tr/tr/pub/uybd/issue/40430/363235
# Ulusal ölçekte kaba bir yaklaşıklıktır, bölgesel bir formüldür.
ML_TO_MW_SLOPE = 0.7018
ML_TO_MW_INTERCEPT = 1.1715


def magnitude_scale_group(mag_type: str) -> str:
    mt = (mag_type or "").lower()
    if mt in MOMENT_MAGNITUDE_TYPES:
        return "moment_magnitude"
    if mt == "md":
        return "duration_magnitude"
    if mt == "ml":
        return "local_magnitude"
    if mt in ("mb", "mblg"):
        return "body_wave_magnitude"
    if mt == "ms":
        return "surface_wave_magnitude"
    return "diger"


def estimate_mw(row) -> float:
    if row["magnitude_scale_group"] == "moment_magnitude":
        return row["magnitude"]
    if row["magnitude_scale_group"] == "local_magnitude":
        return round(ML_TO_MW_SLOPE * row["magnitude"] + ML_TO_MW_INTERCEPT, 2)
    return np.nan


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def nearest(events, stations):
    """Her olay için: en yakın istasyon (herhangi tip) ve en yakın güçlü hareket istasyonu."""
    sm_stations = stations[stations["has_strong_motion"]].reset_index(drop=True)

    near_any_station, near_any_km = [], []
    near_sm_station, near_sm_km = [], []

    for _, ev in events.iterrows():
        d_any = haversine_km(ev["latitude"], ev["longitude"], stations["latitude"], stations["longitude"])
        i = d_any.idxmin()
        near_any_station.append(stations.loc[i, "station"])
        near_any_km.append(round(d_any.loc[i], 2))

        if not sm_stations.empty:
            d_sm = haversine_km(ev["latitude"], ev["longitude"], sm_stations["latitude"], sm_stations["longitude"])
            j = d_sm.idxmin()
            near_sm_station.append(sm_stations.loc[j, "station"])
            near_sm_km.append(round(d_sm.loc[j], 2))
        else:
            near_sm_station.append(None)
            near_sm_km.append(None)

    events = events.copy()
    events["nearest_station"] = near_any_station
    events["nearest_station_distance_km"] = near_any_km
    events["nearest_strong_motion_station"] = near_sm_station
    events["nearest_strong_motion_distance_km"] = near_sm_km

    if "vs30_ms" in stations.columns:
        vs30_lookup = stations.set_index("station")[["vs30_ms", "nehrp_site_class"]]
        events = events.merge(
            vs30_lookup.rename(columns={"vs30_ms": "nearest_sm_vs30_ms", "nehrp_site_class": "nearest_sm_site_class"}),
            how="left", left_on="nearest_strong_motion_station", right_index=True,
        )
    return events


def main():
    expanded_path = PROCESSED / "turkiye_deprem_katalogu_genisletilmis.parquet"
    usgs_path = PROCESSED / "usgs_catalog_turkey.parquet"
    stations_path = PROCESSED / "koeri_stations.csv"
    waveform_log_path = PROCESSED / "waveform_fetch_log.csv"
    features_path = PROCESSED / "waveform_features.csv"

    if not stations_path.exists():
        print("Önce scripts/fetch_orfeus_eida.py çalıştırılmalı.")
        return

    if expanded_path.exists():
        events = pd.read_parquet(expanded_path).rename(columns={"source_event_id": "event_id"})
    elif usgs_path.exists():
        print("Genişletilmiş katalog bulunamadı, sadece USGS kataloğuyla devam ediliyor.")
        events = pd.read_parquet(usgs_path)
    else:
        print("Önce scripts/download_usgs.py veya scripts/expand_catalog.py çalıştırılmalı.")
        return

    stations = pd.read_csv(stations_path)

    events["magnitude_scale_group"] = events["mag_type"].apply(magnitude_scale_group)
    events["mw_estimate"] = events.apply(estimate_mw, axis=1)

    events = nearest(events, stations)

    # Deduplikasyon sırasında bir olay başka bir kümeye devredilmiş olabilir
    # (bkz. expand_catalog.py). Dalga formu dosyaları eski kimlikle diskte
    # durduğu için, sayım öncesi hayatta kalan kimliğe yeniden eşliyoruz.
    id_map_path = PROCESSED / "event_id_cluster_map.csv"
    usgs_map = None
    if id_map_path.exists():
        id_map = pd.read_csv(id_map_path)
        usgs_map = id_map[id_map["source"] == "usgs"].set_index("source_event_id")[
            "representative_event_id"
        ]

    def remap_event_id(df):
        if usgs_map is not None:
            df["event_id"] = df["event_id"].map(usgs_map).fillna(df["event_id"])
        return df

    if waveform_log_path.exists():
        wf = pd.read_csv(waveform_log_path)
        ok = remap_event_id(wf[wf["status"] == "ok"].copy())
        counts = ok.groupby("event_id").size().rename("num_waveform_files")
        events = events.merge(counts, how="left", left_on="event_id", right_index=True)
        events["num_waveform_files"] = events["num_waveform_files"].fillna(0).astype(int)
        events["has_waveform"] = events["num_waveform_files"] > 0
    else:
        events["num_waveform_files"] = 0
        events["has_waveform"] = False

    if features_path.exists():
        feat = remap_event_id(pd.read_csv(features_path))

        # max_pga_g/max_pgv_cms öncelikle "usable_for_engineering" olarak
        # işaretlenmiş (güçlü hareket sensöründen, QC sorunu olmayan)
        # kayıtlardan hesaplanır. Hiçbir olayda böyle bir kayıt yoksa,
        # broadband/short-period kayıtlara düşülür ve bu ayrı bir bayrakla
        # (pga_from_strong_motion) işaretlenir - bkz. issue #2.
        if "usable_for_engineering" in feat.columns:
            engineering_feat = feat[feat["usable_for_engineering"]]
        else:
            engineering_feat = feat[feat.get("instrument_type_used") == "strong_motion"]

        agg_engineering = engineering_feat.groupby("event_id").agg(
            max_pga_g=("pga_g", "max"), max_pgv_cms=("pgv_cms", "max"),
        )
        agg_any = feat.groupby("event_id").agg(
            max_pga_g_any=("pga_g", "max"), max_pgv_cms_any=("pgv_cms", "max"),
            best_snr_db=("snr_db", "max"),
            has_phase_pick=("p_pick_time", lambda s: s.notna().any()),
        )

        events = events.merge(agg_engineering, how="left", left_on="event_id", right_index=True)
        events = events.merge(agg_any, how="left", left_on="event_id", right_index=True)
        events["pga_from_strong_motion"] = events["max_pga_g"].notna()
        events["max_pga_g"] = events["max_pga_g"].fillna(events["max_pga_g_any"])
        events["max_pgv_cms"] = events["max_pgv_cms"].fillna(events["max_pgv_cms_any"])
        events = events.drop(columns=["max_pga_g_any", "max_pgv_cms_any"])
        events["has_phase_pick"] = events["has_phase_pick"].fillna(False)

    out_path = PROCESSED / "turkiye_deprem_veriseti_v3.parquet"
    events.to_parquet(out_path, index=False)

    print(f"Birleşik veri seti (v3) hazır -> {out_path} ({len(events)} satır)")
    print(f"  Gerçek dalga formu olan olay sayısı: {events['has_waveform'].sum()}")
    if "max_pga_g" in events.columns:
        print(f"  PGA değeri hesaplanan olay sayısı: {events['max_pga_g'].notna().sum()}")
    print(f"  Büyüklük ölçeği grupları:\n{events['magnitude_scale_group'].value_counts().to_string()}")


if __name__ == "__main__":
    main()
