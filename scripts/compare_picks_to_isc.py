"""
Otomatik (STA/LTA tabanlı) P/S faz okumalarını, ISC Bulletin'den çekilmiş
uzman (analyst-reviewed) pick'lerle karşılaştırıp somut bir hata payı
çıkarır.

Neden gerekli: `enrich_waveforms.py`'de üretilen `p_pick_time`/
`s_pick_time` otomatik bir yöntemle bulunuyor ve DATA_CARD.md'de "yayın
kalitesinde bir faz okuma değildir" diye uyarılıyor - ama şimdiye kadar
bu uyarı sayısal bir hata payıyla desteklenmiyordu.
`isc_analyst_picks.csv` içinde tam da bunun için toplanmış 384 uzman
pick'i var; bu script otomatik pick'lerle bunları eşleştirip ortalama/
medyan sapmayı hesaplıyor, ayrıca `p_pick_confidence`/`s_pick_confidence`
skorunun gerçekten anlamlı olup olmadığını (yüksek güvenli pick'ler
düşük hatalı mı) kontrol ediyor.

Kullanım:
    python scripts/compare_picks_to_isc.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

PROCESSED = Path("data/processed")


def load_matched_pairs(phase: str) -> pd.DataFrame:
    """Bir faz tipi (P veya S) için otomatik pick ile ISC uzman pick'ini
    aynı (event_id, station) çifti üzerinden eşleştirir."""
    picks = pd.read_csv(PROCESSED / "isc_analyst_picks.csv")
    picks = picks[picks["phase_type"] == phase][["event_id", "station", "pick_time"]]
    picks = picks.rename(columns={"pick_time": "isc_pick_time"})

    table = pd.read_csv(PROCESSED / "event_station_table.csv")
    auto_col = "p_pick_time" if phase == "P" else "s_pick_time"
    conf_col = "p_pick_confidence" if phase == "P" else "s_pick_confidence"
    table = table[["event_id", "station", auto_col, conf_col]].dropna(subset=[auto_col])
    table = table.rename(columns={auto_col: "auto_pick_time", conf_col: "confidence"})

    merged = picks.merge(table, on=["event_id", "station"])
    merged["auto_pick_time"] = pd.to_datetime(merged["auto_pick_time"], utc=True)
    merged["isc_pick_time"] = pd.to_datetime(merged["isc_pick_time"], utc=True)
    merged["abs_error_sec"] = (
        (merged["auto_pick_time"] - merged["isc_pick_time"]).dt.total_seconds().abs()
    )
    return merged


def summarize(merged: pd.DataFrame, phase: str) -> dict:
    errors = merged["abs_error_sec"]
    summary = dict(
        phase=phase,
        n_matched=len(merged),
        mean_abs_error_sec=round(float(errors.mean()), 3),
        median_abs_error_sec=round(float(errors.median()), 3),
        p90_abs_error_sec=round(float(errors.quantile(0.9)), 3),
        max_abs_error_sec=round(float(errors.max()), 3),
        # 1 saniyeden büyük sapma, bir sonraki dalga fazıyla veya tamamen
        # farklı bir tetiklenmeyle karıştırıldığını gösterir - kaba bir
        # "büyük hata" oranı.
        fraction_over_1s=round(float((errors > 1.0).mean()), 3),
    )

    # Güven skoru gerçekten anlamlı mı: yüksek güvenli pick'lerin hata
    # ortalaması, düşük güvenlilerden belirgin şekilde düşük olmalı.
    # Sabit bir eşik yerine medyan bazlı bölme kullanılıyor - güven skoru
    # veri setinin tamamında zaten düşük bir aralıkta kalıyor (max~0.57,
    # bkz. STA/LTA tepe değeri ölçeklendirmesi), sabit bir eşik (ör. 0.7)
    # hiçbir örneği "yüksek güvenli" tarafa düşürmezdi.
    median_conf = merged["confidence"].median()
    high_conf = merged[merged["confidence"] >= median_conf]["abs_error_sec"]
    low_conf = merged[merged["confidence"] < median_conf]["abs_error_sec"]
    summary["mean_abs_error_high_confidence"] = (
        round(float(high_conf.mean()), 3) if len(high_conf) > 0 else None
    )
    summary["mean_abs_error_low_confidence"] = (
        round(float(low_conf.mean()), 3) if len(low_conf) > 0 else None
    )
    summary["n_high_confidence"] = int(len(high_conf))
    summary["n_low_confidence"] = int(len(low_conf))
    return summary


def main():
    results = {}
    for phase in ["P", "S"]:
        merged = load_matched_pairs(phase)
        if len(merged) == 0:
            print(f"[{phase}] eşleşen pick bulunamadı, atlanıyor.")
            continue
        summary = summarize(merged, phase)
        results[phase] = summary
        print(f"[{phase}-dalgası] {summary['n_matched']} eşleşen pick")
        print(f"  Ortalama mutlak hata: {summary['mean_abs_error_sec']}s "
              f"(medyan: {summary['median_abs_error_sec']}s, "
              f"90. yüzdelik: {summary['p90_abs_error_sec']}s)")
        print(f"  1 saniyeden fazla sapan pick oranı: {summary['fraction_over_1s']*100:.1f}%")
        if summary["mean_abs_error_high_confidence"] is not None:
            print(f"  Medyan üstü güvenli pick'lerde ortalama hata: "
                  f"{summary['mean_abs_error_high_confidence']}s (n={summary['n_high_confidence']})")
        if summary["mean_abs_error_low_confidence"] is not None:
            print(f"  Medyan altı güvenli pick'lerde ortalama hata: "
                  f"{summary['mean_abs_error_low_confidence']}s (n={summary['n_low_confidence']})")
        print()

    out_path = PROCESSED / "isc_pick_comparison_report.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Rapor kaydedildi -> {out_path}")


if __name__ == "__main__":
    main()
