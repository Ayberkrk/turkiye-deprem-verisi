"""
`scripts/validate_dataset.py`'nin hızlı, geliştirme-sırası versiyonu.

Aradaki fark: `validate_dataset.py`, her dalga formu dosyasını
`obspy.read()` ile açıp okunabilirliğini doğruluyor (5.413 dosya için
dakikalar sürebilir). Bu script SADECE parquet/CSV'leri kontrol eder -
o tek yavaş kontrolü (`waveform_files_readable_check`) atlar, bu yüzden
`obspy`'yi hiç import etmez ve saniyeler içinde biter.

Bu, CONTRIBUTING.md'de önerilen bir ön-kontrol: değişikliğinizin veri
setini bozup bozmadığını hızlıca görmek için. Yayınlamadan/PR açmadan
önce hâlâ tam `python scripts/validate_dataset.py` çalıştırılmalı.

Kullanım:
    python scripts/quick_check.py
Çıkış kodu 0 = her şey yolunda, 1 = en az bir kontrol başarısız.
"""
import sys
from pathlib import Path

import pandas as pd

from validate_dataset import (
    dedup_quality_checks,
    event_station_geometry_checks,
    fetch_log_consistency_check,
    ground_motion_plausibility_checks,
    phase_order_check,
    structural_checks,
    waveform_file_count_check,
)

PROCESSED = Path("data/processed")


def main():
    events = pd.read_parquet(PROCESSED / "turkiye_deprem_veriseti_v3.parquet")
    stations = pd.read_csv(PROCESSED / "koeri_stations.csv")
    features = pd.read_csv(PROCESSED / "waveform_features.csv")

    event_station_path = PROCESSED / "event_station_table.csv"
    event_station = pd.read_csv(event_station_path) if event_station_path.exists() else None

    checks_failed = 0

    def check(name, condition, detail=""):
        nonlocal checks_failed
        status = "OK" if condition else "BAŞARISIZ"
        print(f"[{status}] {name}" + (f" - {detail}" if detail and not condition else ""))
        if not condition:
            checks_failed += 1

    for name, condition, detail in structural_checks(events, stations, features):
        check(name, condition, detail)

    waveform_files, count_result = waveform_file_count_check(events, PROCESSED / "waveforms")
    check(*count_result)

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
    if checks_failed == 0:
        print("Tüm hızlı kontroller başarılı. (obspy/dalga formu okunabilirlik kontrolü ATLANDI - "
              "yayınlamadan önce `python scripts/validate_dataset.py` çalıştırın.)")
        sys.exit(0)
    else:
        print(f"{checks_failed} kontrol başarısız.")
        sys.exit(1)


if __name__ == "__main__":
    main()
