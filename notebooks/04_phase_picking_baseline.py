"""
`benchmarks/phase_picking/` bölmeleri üzerinde minimal bir referans.

DÜRÜSTLÜK NOTU: burada eğitilen bir model YOK. `p_pick_time`/`s_pick_time`
zaten `scripts/enrich_waveforms.py`'nin otomatik (STA/LTA tabanlı)
çıktısı - bu script onu "tahmin" olarak alıp, resmi split'teki
(event_id, station) çiftleri için ISC Bulletin'den çekilmiş UZMAN
(analyst-reviewed) pick'lerle (`data/processed/isc_analyst_picks.csv`)
karşılaştırıyor. Amaç iki şey:

1. Split'in gerçekten kullanılabilir olduğunu, somut bir zamanlama hatası
   metriğiyle göstermek (yeni bir model bunu ne kadar geçebilir sorusuna
   referans).
2. Otomatik pick'lerin evrensel bir ground-truth OLMADIĞINI, ISC uzman
   pick'lerinin (sınırlı bir alt küme, tüm olayları kapsamıyor) gerçek
   doğrulama kaynağı olduğunu somut sayılarla netleştirmek (bkz.
   DATA_CARD.md, docs/benchmarks.md).

`p_pick_confidence`/`s_pick_confidence` skoruna göre medyan-üstü/altı
ayrımı da raporlanıyor - `scripts/compare_picks_to_isc.py` ile aynı
yöntem (bkz. oradaki `summarize()`), burada sadece resmi split'e
kısıtlanıyor.

Kullanım:
    python notebooks/04_phase_picking_baseline.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from compare_picks_to_isc import summarize  # noqa: E402

BENCH_DIR = Path("benchmarks/phase_picking")
PROCESSED = Path("data/processed")


def matched_pairs_for_split(split: pd.DataFrame, isc_picks: pd.DataFrame, phase: str) -> pd.DataFrame:
    """Bir bölmedeki (event_id, station) çiftlerini, aynı çift için ISC
    uzman pick'i olanlarla kısıtlayıp eşleştirir."""
    auto_col = "p_pick_time" if phase == "P" else "s_pick_time"
    conf_col = "p_pick_confidence" if phase == "P" else "s_pick_confidence"

    picks = isc_picks[isc_picks["phase_type"] == phase][["event_id", "station", "pick_time"]]
    picks = picks.rename(columns={"pick_time": "isc_pick_time"})

    auto = split[["event_id", "station", auto_col, conf_col]].dropna(subset=[auto_col])
    auto = auto.rename(columns={auto_col: "auto_pick_time", conf_col: "confidence"})

    merged = picks.merge(auto, on=["event_id", "station"])
    merged["auto_pick_time"] = pd.to_datetime(merged["auto_pick_time"], utc=True)
    merged["isc_pick_time"] = pd.to_datetime(merged["isc_pick_time"], utc=True)
    merged["abs_error_sec"] = (
        (merged["auto_pick_time"] - merged["isc_pick_time"]).dt.total_seconds().abs()
    )
    return merged


def main():
    isc_picks_path = PROCESSED / "isc_analyst_picks.csv"
    if not isc_picks_path.exists():
        print(f"{isc_picks_path} bulunamadı - önce `python scripts/fetch_isc_picks.py` çalıştırın.")
        return
    isc_picks = pd.read_csv(isc_picks_path)

    for split_name in ["train", "val", "test"]:
        split = pd.read_csv(BENCH_DIR / f"{split_name}.csv")
        print(f"=== {split_name} bölmesi ({len(split)} satır) ===")
        for phase in ["P", "S"]:
            merged = matched_pairs_for_split(split, isc_picks, phase)
            if len(merged) == 0:
                print(f"  [{phase}] bu bölmede ISC uzman pick'iyle eşleşen kayıt yok "
                      "(ISC Bulletin kapsamı sınırlı, bkz. DATA_CARD.md).")
                continue
            summary = summarize(merged, phase)
            print(f"  [{phase}-dalgası] n={summary['n_matched']}  "
                  f"ortalama mutlak hata={summary['mean_abs_error_sec']}s  "
                  f"medyan={summary['median_abs_error_sec']}s")
            if summary["mean_abs_error_high_confidence"] is not None:
                print(f"      medyan-üstü güvenli pick'ler (n={summary['n_high_confidence']}): "
                      f"{summary['mean_abs_error_high_confidence']}s")
            if summary["mean_abs_error_low_confidence"] is not None:
                print(f"      medyan-altı güvenli pick'ler (n={summary['n_low_confidence']}): "
                      f"{summary['mean_abs_error_low_confidence']}s")
        print()

    print("NOT: yukarıdaki sayılar sadece resmi split içinde, ISC uzman pick'i")
    print("bulunan (sınırlı bir alt küme) kayıtlar için geçerli. Otomatik")
    print("p_pick_time/s_pick_time DEĞERLERİ EVRENSEL GROUND-TRUTH DEĞİLDİR -")
    print("bir model bu etiketlerle eğitilirse bu hatanın bir kısmını miras")
    print("alır. Detaylar: docs/benchmarks.md, DATA_CARD.md.")


if __name__ == "__main__":
    main()
