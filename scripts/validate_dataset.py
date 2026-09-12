"""
Yayınlanmadan önce veri setinin bütünlüğünü kontrol eden basit bir
doğrulama scripti. "Sessizce bozuk" bir veri seti yayınlamamak için.

Kullanım:
    python scripts/validate_dataset.py
Çıkış kodu 0 = her şey yolunda, 1 = en az bir kontrol başarısız.
"""
import sys
from pathlib import Path

import pandas as pd
from obspy import read

PROCESSED = Path("data/processed")
checks_failed = 0


def check(name: str, condition: bool, detail: str = ""):
    global checks_failed
    status = "OK" if condition else "BAŞARISIZ"
    print(f"[{status}] {name}" + (f" - {detail}" if detail and not condition else ""))
    if not condition:
        checks_failed += 1


def main():
    events = pd.read_parquet(PROCESSED / "turkiye_deprem_veriseti_v3.parquet")
    stations = pd.read_csv(PROCESSED / "koeri_stations.csv")
    features = pd.read_csv(PROCESSED / "waveform_features.csv")

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

    print()
    if checks_failed == 0:
        print("Tüm kontroller başarılı. Veri seti yayına hazır.")
        sys.exit(0)
    else:
        print(f"{checks_failed} kontrol başarısız. Yayınlamadan önce düzeltin.")
        sys.exit(1)


if __name__ == "__main__":
    main()
