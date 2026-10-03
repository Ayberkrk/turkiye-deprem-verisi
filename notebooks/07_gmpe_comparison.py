"""
`ground_motion` benchmark'ındaki gözlemleri, bu veriyle kalibre
EDİLMEMİŞ, yayınlanmış bir yer hareketi modeliyle kıyaslar: Akkar,
Sandıkkaya ve Bommer (2014), hiposantral mesafe sürümü
(`scripts/gmpe.py`).

`02`/`03` referansları bu verinin train bölmesinde eğitiliyor; "skor
iyi" demek verinin kendi içinde tutarlı olduğunu gösterir ama verinin
DOĞRU olduğunu göstermez. Bağımsız bir model iki soruya cevap verir:
1. Veri setindeki PGA değerleri literatürle aynı mertebede mi (birim,
   tepki çıkarımı, mesafe gibi sistematik bir hata var mı)?
2. Bu veride eğitilen bir model, hazır bir GMPE'yi ne kadar geçiyor?

Model moment büyüklüğü (Mw) bekler; yalnızca `mw_estimate` dolu olan
kayıtlar kullanılır (mb/md tipindeki olaylar dışarıda). Faylanma tipi
veri setinde olmadığı için doğrultu atımlı kabul edilir. Modelin
geçerlilik aralığı 200 km'ye kadar; sonuçlar hem tüm kayıtlar hem bu
aralık için raporlanır. Model yatay geometrik ortalama için
tanımlandığından kıyas `pga_geomean_g` ile yapılır.

Kullanım:
    python notebooks/07_gmpe_comparison.py
"""
import sys
from importlib import import_module
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))
from gmpe import ASB14_SIGMA_LN, akkar2014_pga_g  # noqa: E402

baseline = import_module("02_ground_motion_baseline")

BENCH_DIR = Path("benchmarks/ground_motion")
TARGET = "pga_geomean_g"
MAX_VALID_DISTANCE_KM = 200.0


def usable_rows(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["mw_estimate", "hypocentral_distance_km", "vs30_ms", TARGET])
    return df[df[TARGET] > 0].copy()


def residuals_log10(df: pd.DataFrame) -> np.ndarray:
    """log10(gözlenen) - log10(model). Negatif: model fazla tahmin ediyor."""
    predicted = akkar2014_pga_g(df["mw_estimate"].values, df["hypocentral_distance_km"].values,
                                df["vs30_ms"].values, "rhypo")
    return np.log10(df[TARGET].values) - np.log10(predicted)


def summarize(label: str, residuals: np.ndarray):
    print(f"  {label:<34} n={len(residuals):4d}  yanlılık={residuals.mean():+.3f}  "
          f"std={residuals.std():.3f}  RMSE={np.sqrt(np.mean(residuals ** 2)):.3f}")


def main():
    tau, phi = ASB14_SIGMA_LN["rhypo"]
    model_sigma_log10 = np.sqrt(tau ** 2 + phi ** 2) / np.log(10)
    print(f"Hedef: {TARGET} (log10 g birimi). Modelin kendi toplam sigması: {model_sigma_log10:.3f}\n")

    splits = {name: usable_rows(pd.read_csv(BENCH_DIR / f"{name}.csv")) for name in ["train", "val", "test"]}
    for name, df in splits.items():
        res = residuals_log10(df)
        in_range = (df["hypocentral_distance_km"] <= MAX_VALID_DISTANCE_KM).values
        print(f"[{name}]")
        summarize("tüm kayıtlar (Mw mevcut)", res)
        summarize(f"R <= {MAX_VALID_DISTANCE_KM:.0f} km (geçerlilik aralığı)", res[in_range])

    all_rows = pd.concat(splits.values())
    res_all = pd.Series(residuals_log10(all_rows), index=all_rows.index)
    print("\nYanlılığın büyüklüğe ve mesafeye göre dağılımı (tüm bölmeler):")
    for column, bins in [("mw_estimate", [4, 4.75, 5.25, 6, 8]),
                         ("hypocentral_distance_km", [0, 50, 100, 200, 400])]:
        grouped = res_all.groupby(pd.cut(all_rows[column], bins), observed=True).agg(["mean", "count"])
        for interval, row in grouped.iterrows():
            print(f"  {column} {str(interval):<14} yanlılık={row['mean']:+.3f}  n={int(row['count'])}")

    # Aynı test satırlarında, bu veride eğitilmiş doğrusal modelle kıyas.
    train, test = splits["train"], splits["test"]
    prepared_train = baseline._prepare(train.assign(**{baseline.TARGET: train[TARGET]}))
    prepared_test = baseline._prepare(test.assign(**{baseline.TARGET: test[TARGET]}))
    coefs = baseline._fit_ols(prepared_train)
    ols_rmse = baseline._rmse(prepared_test["log_pga_g"].values, baseline._predict(prepared_test, coefs))
    gmpe_res = residuals_log10(test)
    print(f"\nAynı test satırlarında (n={len(test)}) RMSE: "
          f"Akkar 2014 (uydurma yok) = {np.sqrt(np.mean(gmpe_res ** 2)):.3f}, "
          f"yanlılığı çıkarılmış = {gmpe_res.std():.3f}, "
          f"bu veride eğitilmiş doğrusal model = {ols_rmse:.3f}")


if __name__ == "__main__":
    main()
