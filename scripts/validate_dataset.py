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

v6 notları: kontroller, `scripts/quick_check.py`'nin de yeniden
kullanabilmesi için saf fonksiyonlara ayrıldı (her biri DataFrame alıp
`(isim, koşul, detay)` üçlüleri döndürür). Tek yavaş kontrol - her
miniSEED dosyasını `obspy.read()` ile açmak - `waveform_files_readable_check`
içinde izole edildi; `obspy` artık modül seviyesinde değil, sadece o
fonksiyonun içinde import ediliyor.

Kullanım:
    python scripts/validate_dataset.py
Çıkış kodu 0 = her şey yolunda, 1 = en az bir kontrol başarısız.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

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


def structural_checks(events, stations, features):
    return [
        ("Ana deprem kataloğu boş değil", len(events) > 0, f"{len(events)} satır"),
        ("İstasyon tablosu boş değil", len(stations) > 0, f"{len(stations)} satır"),
        ("Dalga formu özellik tablosu boş değil", len(features) > 0, f"{len(features)} satır"),
        ("event_id benzersiz", events["event_id"].is_unique, ""),
        ("Eksik değer yok (kritik sütunlar)",
         events[["magnitude", "latitude", "longitude", "time_utc"]].isna().sum().sum() == 0, ""),
        ("Büyüklük makul aralıkta (0-10)", events["magnitude"].between(0, 10).all(), ""),
        ("Koordinatlar Türkiye kutusunda (lat 34-44, lon 24-46)",
         events["latitude"].between(34, 44).all() and events["longitude"].between(24, 46).all(), ""),
        ("Derinlik negatif değil", (events["depth_km"] >= 0).all(), ""),
        ("İstasyon koordinatları eksik değil",
         stations[["latitude", "longitude"]].isna().sum().sum() == 0, ""),
        ("has_waveform ile num_waveform_files tutarlı",
         ((events["has_waveform"]) == (events["num_waveform_files"] > 0)).all(), ""),
        ("PGA değeri her satırda pozitif ya da sıfır",
         features["pga_g"].dropna().ge(0).all(), ""),
        ("Her dalga formu dosyası için en fazla 1 öznitelik satırı",
         not features["file"].duplicated().any(), ""),
        ("mw_estimate sadece local/moment magnitude gruplarında dolu",
         events.loc[events["mw_estimate"].notna(), "magnitude_scale_group"]
         .isin(["local_magnitude", "moment_magnitude"]).all(), ""),
        ("Vs30 makul fiziksel aralıkta (100-2000 m/s)",
         stations["vs30_ms"].dropna().between(100, 2000).all(), ""),
        ("NEHRP zemin sınıfı geçerli değerlerde (A-E)",
         stations["nehrp_site_class"].dropna().isin(list("ABCDE")).all(), ""),
        ("Büyüklük tutarlılık sapması negatif değil",
         events["magnitude_agreement_std"].dropna().ge(0).all(), ""),
        ("reported_by sütunu boş değil", events["reported_by"].notna().all(), ""),
    ]


def waveform_file_count_check(events, waveform_dir):
    waveform_files = list(waveform_dir.glob("*.mseed"))
    expected = events["num_waveform_files"].sum()
    return waveform_files, ("Dalga formu dosyaları listelendiği kadar var",
                             len(waveform_files) == expected,
                             f"beklenen={expected}, bulunan={len(waveform_files)}")


def waveform_files_readable_check(waveform_files):
    from obspy import read

    unreadable = 0
    for f in waveform_files:
        try:
            st = read(str(f))
            if len(st) == 0:
                unreadable += 1
        except Exception:
            unreadable += 1
    return "Tüm dalga formu dosyaları okunabilir", unreadable == 0, f"{unreadable} dosya okunamadı"


def event_station_geometry_checks(event_station):
    if event_station is None or not len(event_station):
        return [("event-station tablosu mevcut (scripts/build_event_station_table.py)", False,
                  "event_station_table.csv bulunamadı")]

    recomputed = haversine_km(
        event_station["event_latitude"], event_station["event_longitude"],
        event_station["station_latitude"], event_station["station_longitude"],
    )
    diff = (recomputed - event_station["epicentral_distance_km"]).abs()
    return [
        ("event-station epicentral mesafesi koordinatlarla tutarlı (<=1km fark)",
         (diff <= 1.0).all(), f"maksimum fark={diff.max():.3f}km"),
        ("hypocentral mesafe >= epicentral mesafe",
         (event_station["hypocentral_distance_km"] >= event_station["epicentral_distance_km"] - 0.01).all(), ""),
    ]


def ground_motion_plausibility_checks(features):
    # Dünyadaki en büyük kayıtlı PGA değerleri bile ~4g civarında; bunun
    # üzerini şüpheli/muhtemel enstrüman hatası kabul ediyoruz.
    extreme_pga = features["pga_g"].dropna()
    extreme_pga = extreme_pga[extreme_pga > 4.0]
    extreme_pgv = features["pgv_cms"].dropna()
    extreme_pgv = extreme_pgv[extreme_pgv > 500]

    results = [
        ("Aşırı büyük PGA değeri yok (>4g şüpheli)", len(extreme_pga) == 0,
         f"{len(extreme_pga)} kayıt 4g üzerinde"),
        ("Aşırı büyük PGV değeri yok (>500 cm/s şüpheli)", len(extreme_pgv) == 0,
         f"{len(extreme_pgv)} kayıt 500 cm/s üzerinde"),
    ]
    if "usable_for_engineering" in features.columns:
        non_sm_engineering = features[
            (features["usable_for_engineering"]) & (features["instrument_type_used"] != "strong_motion")
        ]
        results.append(("usable_for_engineering yalnızca strong_motion kayıtlarda True",
                         len(non_sm_engineering) == 0, f"{len(non_sm_engineering)} aykırı satır"))
    return results


def phase_order_check(features):
    if not {"p_pick_time", "s_pick_time"}.issubset(features.columns):
        return None
    both = features.dropna(subset=["p_pick_time", "s_pick_time"]).copy()
    if not len(both):
        return None
    both["p_pick_time"] = pd.to_datetime(both["p_pick_time"])
    both["s_pick_time"] = pd.to_datetime(both["s_pick_time"])
    bad_order = both[both["s_pick_time"] <= both["p_pick_time"]]
    return ("S faz okuması her zaman P'den sonra", len(bad_order) == 0, f"{len(bad_order)} kayıtta S<=P")


def dedup_quality_checks(events):
    if "dedup_confidence" not in events.columns:
        return []
    low_conf = events[(events.get("cluster_size", 1) > 1) & (events["dedup_confidence"] < 0.5)]
    return [
        ("dedup_confidence 0-1 aralığında", events["dedup_confidence"].dropna().between(0, 1).all(), ""),
        ("Düşük güvenli (<0.5) çok kaynaklı küme sayısı makul seviyede (<%1)",
         len(low_conf) <= 0.01 * len(events), f"{len(low_conf)}/{len(events)} küme düşük güvenli"),
    ]


def fetch_log_consistency_check(log, waveform_files):
    if log is None:
        return None
    ok_count = (log["status"] == "ok").sum()
    return ("Başarılı waveform_fetch_log kayıt sayısı, waveform dosya sayısıyla tutarlı",
            ok_count == len(waveform_files), f"log_ok={ok_count}, dosya={len(waveform_files)}")


def main():
    events = pd.read_parquet(PROCESSED / "turkiye_deprem_veriseti_v3.parquet")
    stations = pd.read_csv(PROCESSED / "koeri_stations.csv")
    features = pd.read_csv(PROCESSED / "waveform_features.csv")

    event_station_path = PROCESSED / "event_station_table.csv"
    event_station = pd.read_csv(event_station_path) if event_station_path.exists() else None

    for name, condition, detail in structural_checks(events, stations, features):
        check(name, condition, detail)

    waveform_files, count_result = waveform_file_count_check(events, PROCESSED / "waveforms")
    check(*count_result)
    check(*waveform_files_readable_check(waveform_files))

    for name, condition, detail in event_station_geometry_checks(event_station):
        check(name, condition, detail)

    for name, condition, detail in ground_motion_plausibility_checks(features):
        check(name, condition, detail)

    phase_result = phase_order_check(features)
    if phase_result is not None:
        check(*phase_result)

    for name, condition, detail in dedup_quality_checks(events):
        check(name, condition, detail)

    log_path = PROCESSED / "waveform_fetch_log.csv"
    log = pd.read_csv(log_path) if log_path.exists() else None
    log_result = fetch_log_consistency_check(log, waveform_files)
    if log_result is not None:
        check(*log_result)

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
