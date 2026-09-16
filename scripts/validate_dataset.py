"""
Yayınlanmadan önce veri setinin bütünlüğünü VE fiziksel/sismolojik
tutarlılığını kontrol eden doğrulama scripti. "Sessizce bozuk" bir veri
seti yayınlamamak için.

v2 notları: önceki sürüm sadece yapısal bütünlüğü (eksik değer, tip,
aralık) kontrol ediyordu. Bu sürüm ayrıca:
- event-station mesafesini koordinatlardan yeniden hesaplayıp
  kaydedilmiş değerle karşılaştırıyor,
- PGA/PGV için fiziksel olarak anlamsız (aşırı büyük/negatif) değerleri
  işaretliyor,
- P/S faz sıralamasının mantıklı olup olmadığını kontrol ediyor,
- deduplikasyon kümelerinin kalite metriklerini (dedup_confidence vb.)
  değerlendiriyor,
- sonunda makine tarafından okunabilir bir `validation_report.json` ve
  kısa bir `validation_report.md` üretiyor, böylece her yayınlanan
  sürümün kalite özeti arşivlenmiş oluyor.

Kullanım:
    python scripts/validate_dataset.py
Çıkış kodu 0 = her şey yolunda, 1 = en az bir kontrol başarısız.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from obspy import read

from geo import haversine_km

PROCESSED = Path("data/processed")
checks_failed = 0
report_rows = []


def check(name: str, condition: bool, detail: str = ""):
    global checks_failed
    status = "OK" if condition else "BAŞARISIZ"
    print(f"[{status}] {name}" + (f" - {detail}" if detail and not condition else ""))
    report_rows.append(dict(check=name, status=status, detail=detail if not condition else ""))
    if not condition:
        checks_failed += 1


def main():
    events = pd.read_parquet(PROCESSED / "turkiye_deprem_veriseti_v3.parquet")
    stations = pd.read_csv(PROCESSED / "koeri_stations.csv")
    features = pd.read_csv(PROCESSED / "waveform_features.csv")

    event_station_path = PROCESSED / "event_station_table.csv"
    event_station = pd.read_csv(event_station_path) if event_station_path.exists() else None

    # --- Yapısal kontroller (v1'den) ---
    check("event_id benzersiz", events["event_id"].is_unique)
    check("Eksik değer yok (kritik sütunlar)",
          events[["magnitude", "latitude", "longitude", "time_utc"]].isna().sum().sum() == 0)
    check("Büyüklük makul aralıkta (0-10)", events["magnitude"].between(0, 10).all())
    check("Koordinatlar Türkiye kutusunda (lat 34-44, lon 24-46)",
          events["latitude"].between(34, 44).all() and events["longitude"].between(24, 46).all())
    check("Derinlik negatif değil", (events["depth_km"] >= 0).all())
    check("İstasyon koordinatları eksik değil", stations[["latitude", "longitude"]].isna().sum().sum() == 0)
    check("has_waveform ile num_waveform_files tutarlı",
          ((events["has_waveform"]) == (events["num_waveform_files"] > 0)).all())

    waveform_files = list((PROCESSED / "waveforms").glob("*.mseed"))
    check("Dalga formu dosyaları listelendiği kadar var",
          len(waveform_files) == events["num_waveform_files"].sum(),
          f"beklenen={events['num_waveform_files'].sum()}, bulunan={len(waveform_files)}")

    unreadable = 0
    for f in waveform_files:
        try:
            st = read(str(f))
            if len(st) == 0:
                unreadable += 1
        except Exception:
            unreadable += 1
    check("Tüm dalga formu dosyaları okunabilir", unreadable == 0, f"{unreadable} dosya okunamadı")

    check("PGA değeri her satırda pozitif ya da sıfır",
          features["pga_g"].dropna().ge(0).all())
    check("Her dalga formu dosyası için en fazla 1 öznitelik satırı",
          not features["file"].duplicated().any())
    check("mw_estimate sadece local/moment magnitude gruplarında dolu",
          events.loc[events["mw_estimate"].notna(), "magnitude_scale_group"]
          .isin(["local_magnitude", "moment_magnitude"]).all())

    check("Vs30 makul fiziksel aralıkta (100-2000 m/s)",
          stations["vs30_ms"].dropna().between(100, 2000).all())
    check("NEHRP zemin sınıfı geçerli değerlerde (A-E)",
          stations["nehrp_site_class"].dropna().isin(list("ABCDE")).all())
    check("Büyüklük tutarlılık sapması negatif değil",
          events["magnitude_agreement_std"].dropna().ge(0).all())
    check("reported_by sütunu boş değil",
          events["reported_by"].notna().all())

    # --- Event-station geometrisi ---
    if event_station is not None and len(event_station):
        recomputed = haversine_km(
            event_station["event_latitude"], event_station["event_longitude"],
            event_station["station_latitude"], event_station["station_longitude"],
        )
        diff = (recomputed - event_station["epicentral_distance_km"]).abs()
        check("event-station epicentral mesafesi koordinatlarla tutarlı (<=1km fark)",
              (diff <= 1.0).all(), f"maksimum fark={diff.max():.3f}km")
        check("hypocentral mesafe >= epicentral mesafe",
              (event_station["hypocentral_distance_km"] >= event_station["epicentral_distance_km"] - 0.01).all())
    else:
        check("event-station tablosu mevcut (scripts/build_event_station_table.py)", False,
              "event_station_table.csv bulunamadı")

    # --- Ground-motion fiziksel tutarlılığı ---
    # Dünyadaki en büyük kayıtlı PGA değerleri bile ~4g civarında; bunun
    # üzerini şüpheli/muhtemel enstrüman hatası kabul ediyoruz.
    extreme_pga = features["pga_g"].dropna()
    extreme_pga = extreme_pga[extreme_pga > 4.0]
    check("Aşırı büyük PGA değeri yok (>4g şüpheli)", len(extreme_pga) == 0,
          f"{len(extreme_pga)} kayıt 4g üzerinde")
    extreme_pgv = features["pgv_cms"].dropna()
    extreme_pgv = extreme_pgv[extreme_pgv > 500]
    check("Aşırı büyük PGV değeri yok (>500 cm/s şüpheli)", len(extreme_pgv) == 0,
          f"{len(extreme_pgv)} kayıt 500 cm/s üzerinde")
    if "usable_for_engineering" in features.columns:
        non_sm_engineering = features[
            (features["usable_for_engineering"]) & (features["instrument_type_used"] != "strong_motion")
        ]
        check("usable_for_engineering yalnızca strong_motion kayıtlarda True",
              len(non_sm_engineering) == 0, f"{len(non_sm_engineering)} aykırı satır")

    # --- Faz / travel-time kontrolleri ---
    if {"p_pick_time", "s_pick_time"}.issubset(features.columns):
        both = features.dropna(subset=["p_pick_time", "s_pick_time"]).copy()
        if len(both):
            both["p_pick_time"] = pd.to_datetime(both["p_pick_time"])
            both["s_pick_time"] = pd.to_datetime(both["s_pick_time"])
            bad_order = both[both["s_pick_time"] <= both["p_pick_time"]]
            check("S faz okuması her zaman P'den sonra", len(bad_order) == 0,
                  f"{len(bad_order)} kayıtta S<=P")

    # --- Deduplikasyon küme kalitesi ---
    if "dedup_confidence" in events.columns:
        check("dedup_confidence 0-1 aralığında", events["dedup_confidence"].dropna().between(0, 1).all())
        low_conf = events[(events.get("cluster_size", 1) > 1) & (events["dedup_confidence"] < 0.5)]
        check("Düşük güvenli (<0.5) çok kaynaklı küme sayısı makul seviyede (<%1)",
              len(low_conf) <= 0.01 * len(events),
              f"{len(low_conf)}/{len(events)} küme düşük güvenli")

    # --- Waveform/feature/log bütünlüğü ---
    log_path = PROCESSED / "waveform_fetch_log.csv"
    if log_path.exists():
        log = pd.read_csv(log_path)
        ok_count = (log["status"] == "ok").sum()
        check("Başarılı waveform_fetch_log kayıt sayısı, waveform dosya sayısıyla tutarlı",
              ok_count == len(waveform_files), f"log_ok={ok_count}, dosya={len(waveform_files)}")

    print()
    report = dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_events=int(len(events)),
        total_waveform_files=len(waveform_files),
        checks_failed=checks_failed,
        checks=report_rows,
    )
    report_json_path = PROCESSED / "validation_report.json"
    with open(report_json_path, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    report_md_path = PROCESSED / "validation_report.md"
    with open(report_md_path, "w") as f:
        f.write(f"# Veri Doğrulama Raporu\n\n")
        f.write(f"Üretim zamanı: {report['generated_at']}\n\n")
        f.write(f"Toplam olay: {report['total_events']}, toplam dalga formu dosyası: "
                f"{report['total_waveform_files']}\n\n")
        f.write("| Kontrol | Durum | Detay |\n|---|---|---|\n")
        for row in report_rows:
            f.write(f"| {row['check']} | {row['status']} | {row['detail']} |\n")

    print(f"Rapor yazıldı -> {report_json_path}, {report_md_path}")

    if checks_failed == 0:
        print("Tüm kontroller başarılı. Veri seti yayına hazır.")
        sys.exit(0)
    else:
        print(f"{checks_failed} kontrol başarısız. Yayınlamadan önce düzeltin.")
        sys.exit(1)


if __name__ == "__main__":
    main()
