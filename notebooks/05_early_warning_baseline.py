"""
`benchmarks/early_warning/` bölmeleri üzerinde minimal bir referans:
P varışından sonraki 1/3/5/10 saniyelik pencerelerin her biri için, ham
dalga formu genliğinden basit bir öznitelikle büyüklük (mw_estimate)
tahmini.

Model: log10(pencere içindeki mutlak tepe genlik) ile mw_estimate
arasında kapalı-form en küçük kareler (`numpy.linalg.lstsq`) -
`notebooks/02_ground_motion_baseline.py` ile aynı yöntem, ek bağımlılık
gerektirmez (obspy zaten waveform pipeline'ının çekirdek bağımlılığı).

SINIRLAMA (ÖNEMLİ - bir operasyonel erken uyarı sistemi DEĞİLDİR):
dalga formu dosyaları HAMDIR, cihaz tepkisi çıkarılmamıştır (bkz.
docs/schema.md - tepki çıkarımı sadece `enrich_waveforms.py`'nin
`waveform_features.csv` çıktısında yapılır, ham `.mseed` dosyalarında
değil). Bu yüzden buradaki öznitelik fiziksel olarak kalibre edilmiş bir
birimde (m/s vb.) DEĞİL, ham sayısal genlik - istasyon/sensör tipine
göre kazanç farklı olabilir, bu da modele bir miktar gürültü olarak
yansır. Amaç sadece: split'in P-sonrası pencere/olay-bazlı ayrım
kurgusuyla uçtan uca çalışan, öğrenilebilir bir sinyal taşıdığını
gösteren bir referans vermek.

Kullanım:
    python notebooks/05_early_warning_baseline.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
from obspy import UTCDateTime, read

BENCH_DIR = Path("benchmarks/early_warning")
WINDOWS = (1, 3, 5, 10)


def window_peak_amplitudes(file_path: str, p_pick_time: str) -> dict[int, float]:
    """Bir dalga formu dosyasını TEK SEFER okuyup, her pencere uzunluğu
    için P varışından sonraki mutlak tepe genliği hesaplar. Dosya
    okunamazsa ya da hiçbir bileşende örnek yoksa boş sözlük döner."""
    try:
        st = read(file_path)
    except Exception:
        return {}

    p_time = UTCDateTime(p_pick_time)
    out = {}
    for w in WINDOWS:
        sliced = st.slice(p_time, p_time + w)
        peaks = [abs(tr.data).max() for tr in sliced if len(tr.data)]
        if not peaks:
            continue
        peak = float(max(peaks))
        if peak > 0:
            out[w] = peak
    return out


def build_features(split: pd.DataFrame) -> tuple[dict[int, pd.DataFrame], int]:
    """Split'teki her satırı bir kez okuyup, pencere uzunluğu başına bir
    öznitelik tablosu üretir. Okunamayan/kullanılamayan dosya sayısını da
    döner (şeffaflık için, issue #21'in kabul kriteri)."""
    per_window_rows = {w: [] for w in WINDOWS}
    n_unreadable = 0
    for _, row in split.iterrows():
        peaks = window_peak_amplitudes(row["file"], row["p_pick_time"])
        if not peaks:
            n_unreadable += 1
            continue
        for w, peak in peaks.items():
            per_window_rows[w].append(
                dict(event_id=row["event_id"], station=row["station"],
                     log_peak_amp=np.log10(peak), mw_estimate=row["mw_estimate"])
            )
    return {w: pd.DataFrame(rows) for w, rows in per_window_rows.items()}, n_unreadable


def fit_ols(train: pd.DataFrame):
    X = np.column_stack([train["log_peak_amp"].values, np.ones(len(train))])
    y = train["mw_estimate"].values
    coefs, *_ = np.linalg.lstsq(X, y, rcond=None)
    return coefs


def predict(df: pd.DataFrame, coefs) -> np.ndarray:
    X = np.column_stack([df["log_peak_amp"].values, np.ones(len(df))])
    return X @ coefs


def mae(y_true, y_pred) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def main():
    train_split = pd.read_csv(BENCH_DIR / "train.csv")
    test_split = pd.read_csv(BENCH_DIR / "test.csv")

    print("Dalga formu dosyaları okunuyor (bir kere, tüm pencereler için "
          "yeniden kullanılıyor)...")
    train_by_window, train_unreadable = build_features(train_split)
    test_by_window, test_unreadable = build_features(test_split)
    print(f"train: {train_unreadable} satır okunamadı/atlandı "
          f"({len(train_split)} satırdan)")
    print(f"test:  {test_unreadable} satır okunamadı/atlandı "
          f"({len(test_split)} satırdan)\n")

    for w in WINDOWS:
        train_feats = train_by_window[w]
        test_feats = test_by_window[w]
        if len(train_feats) < 10 or len(test_feats) == 0:
            print(f"[{w}s penceresi] yetersiz kullanılabilir kayıt, atlanıyor.")
            continue
        coefs = fit_ols(train_feats)
        pred = predict(test_feats, coefs)
        err = mae(test_feats["mw_estimate"].values, pred)
        naive_err = mae(test_feats["mw_estimate"].values,
                         np.full(len(test_feats), train_feats["mw_estimate"].mean()))
        print(f"[{w}s penceresi] train n={len(train_feats)}, test n={len(test_feats)} "
              f"-> MAE(Mw) = {err:.3f}  (naif/ortalama tahmin: {naive_err:.3f})")

    print()
    print("SINIRLAMA: bu bir operasyonel erken uyarı sistemi DEĞİLDİR - ham,")
    print("cihaz tepkisi çıkarılmamış genlik kullanıyor; sadece official")
    print("split'in P-sonrası pencere kurgusuyla öğrenilebilir bir sinyal")
    print("taşıdığını gösteren minimal bir referans. Detaylar: docs/benchmarks.md.")


if __name__ == "__main__":
    main()
