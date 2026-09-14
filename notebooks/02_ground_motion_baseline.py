"""
`benchmarks/ground_motion/` bölmeleri üzerinde basit bir referans (baseline)
model eğitir. Amaç iki şey:

1. Split'lerin gerçekten kullanılabilir olduğunu kanıtlamak (uçtan uca
   çalışan bir model + anlamlı bir skor).
2. Yeni gelenlere kıyaslanacak bir referans sayı vermek: "kendi modelin
   bundan daha iyi mi?" sorusuna cevap.

Model: klasik zayıflama (attenuation) ilişkisinin basitleştirilmiş bir
hali - log10(PGA), büyüklük ve log10(mesafe)'nin doğrusal bir
fonksiyonu olarak modelleniyor (bkz. Boore-Atkinson tarzı GMPE'lerin
temel formu). Ekstra bağımlılık (scikit-learn vb.) gerektirmemesi için
katsayılar `numpy.linalg.lstsq` ile kapalı-form en küçük kareler
çözümüyle bulunuyor.

Bu, yayın kalitesinde bir GMPE değildir; tek amacı benchmark'ın anlamlı
bir sinyal taşıdığını göstermek (naif "ortalamayı tahmin et" temeline
göre iyileşme).

Kullanım:
    python notebooks/02_ground_motion_baseline.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

BENCH_DIR = Path("benchmarks/ground_motion")

FEATURES = ["magnitude", "log_hypocentral_km", "log_vs30"]


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["magnitude", "hypocentral_distance_km", "vs30_ms", "pga_g"]).copy()
    df = df[df["pga_g"] > 0]  # log10 tanımsız, PGA=0 zaten fiziksel olarak anlamsız
    df["log_hypocentral_km"] = np.log10(df["hypocentral_distance_km"])
    df["log_vs30"] = np.log10(df["vs30_ms"])
    df["log_pga_g"] = np.log10(df["pga_g"])
    return df


def _fit_ols(train: pd.DataFrame):
    X = np.column_stack([train[FEATURES].values, np.ones(len(train))])
    y = train["log_pga_g"].values
    coefs, *_ = np.linalg.lstsq(X, y, rcond=None)
    return coefs


def _predict(df: pd.DataFrame, coefs) -> np.ndarray:
    X = np.column_stack([df[FEATURES].values, np.ones(len(df))])
    return X @ coefs


def _rmse(y_true, y_pred) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def main():
    train = _prepare(pd.read_csv(BENCH_DIR / "train.csv"))
    val = _prepare(pd.read_csv(BENCH_DIR / "val.csv"))
    test = _prepare(pd.read_csv(BENCH_DIR / "test.csv"))

    coefs = _fit_ols(train)
    b_mag, b_logdist, b_logvs30, intercept = coefs
    print("Model: log10(PGA_g) = "
          f"{b_mag:.4f}*M + {b_logdist:.4f}*log10(R_hipo) + "
          f"{b_logvs30:.4f}*log10(Vs30) + {intercept:.4f}")
    print(f"(train n={len(train)}, val n={len(val)}, test n={len(test)})\n")

    # Naif temel çizgi: hiçbir girdi kullanmadan, sadece train ortalamasını
    # tahmin et. Gerçek modelin bunu ne kadar geçtiği, benchmark'ın anlamlı
    # bir sinyal taşıdığının kanıtı.
    for name, split in [("val", val), ("test", test)]:
        pred = _predict(split, coefs)
        rmse_log = _rmse(split["log_pga_g"].values, pred)
        naive_rmse_log = _rmse(split["log_pga_g"].values, np.full(len(split), train["log_pga_g"].mean()))
        ss_res = np.sum((split["log_pga_g"].values - pred) ** 2)
        ss_tot = np.sum((split["log_pga_g"].values - split["log_pga_g"].mean()) ** 2)
        r2 = 1 - ss_res / ss_tot
        print(f"[{name}] RMSE(log10 g) = {rmse_log:.4f} (ortalama tahmine göre "
              f"faktör olarak: {10**rmse_log:.2f}x)  |  naif RMSE = {naive_rmse_log:.4f}  |  R2 = {r2:.3f}")


if __name__ == "__main__":
    main()
