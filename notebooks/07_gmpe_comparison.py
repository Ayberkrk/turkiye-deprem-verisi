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
tanımlandığından ana kıyas `pga_geomean_g` üzerindedir; RotD50 sonucu
ayrıca tanı amaçlı gösterilir.

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
TARGETS = ("pga_geomean_g", "pga_rotd50_g")
MAX_VALID_DISTANCE_KM = 200.0
BOOTSTRAP_REPLICATES = 1000
MIN_GROUP_EVENTS = 5


def usable_rows(df: pd.DataFrame, target: str = TARGET) -> pd.DataFrame:
    required = ["event_id", "mw_estimate", "hypocentral_distance_km", "vs30_ms", target]
    df = df.dropna(subset=required)
    return df[df[target] > 0].copy()


def residuals_log10(df: pd.DataFrame, target: str = TARGET) -> np.ndarray:
    """log10(gözlenen) - log10(model). Negatif: model fazla tahmin ediyor."""
    predicted = akkar2014_pga_g(df["mw_estimate"].values, df["hypocentral_distance_km"].values,
                                df["vs30_ms"].values, "rhypo")
    return np.log10(df[target].values) - np.log10(predicted)


def grouped_bootstrap_mean_ci(residuals, groups, n_boot: int = BOOTSTRAP_REPLICATES,
                              seed: int = 20261025, confidence: float = 0.95):
    """Row-weighted mean CI from event-cluster resampling; returns None for <2 events."""
    residuals = np.asarray(residuals, dtype=float)
    groups = np.asarray(groups)
    if residuals.ndim != 1 or groups.ndim != 1 or len(residuals) != len(groups):
        raise ValueError("residuals and groups must be one-dimensional arrays of equal length")
    if n_boot < 1:
        raise ValueError("n_boot must be positive")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")
    _, inverse = np.unique(groups, return_inverse=True)
    event_count = int(inverse.max() + 1) if len(inverse) else 0
    if event_count < 2:
        return None

    sums = np.bincount(inverse, weights=residuals, minlength=event_count)
    counts = np.bincount(inverse, minlength=event_count)
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        sampled = rng.integers(0, event_count, size=event_count)
        means[i] = sums[sampled].sum() / counts[sampled].sum()
    tail = (1.0 - confidence) / 2.0
    low, high = np.quantile(means, [tail, 1.0 - tail])
    return float(low), float(high)


def summarize(label: str, frame: pd.DataFrame, residuals: np.ndarray, *, seed: int = 20261025):
    ci = grouped_bootstrap_mean_ci(residuals, frame["event_id"].values, seed=seed)
    ci_text = "yok (tek olay)" if ci is None else f"95% olay-bootstrap GA=[{ci[0]:+.3f}, {ci[1]:+.3f}]"
    print(f"  {label:<34} n={len(residuals):4d} olay={frame['event_id'].nunique():4d} "
          f"yanlılık={residuals.mean():+.3f} ({ci_text})  "
          f"std={residuals.std():.3f}  RMSE={np.sqrt(np.mean(residuals ** 2)):.3f}")


def subgroup_diagnostics(frame: pd.DataFrame, residuals: np.ndarray, *, seed: int = 20261025):
    """Print residuals by available magnitude, distance, and Vs30 strata."""
    strata = [
        ("mw_estimate", [-np.inf, 4.75, 5.25, 6.0, np.inf]),
        ("hypocentral_distance_km", [0.0, 50.0, 100.0, 200.0, np.inf]),
        ("vs30_ms", [0.0, 300.0, 500.0, 750.0, 1000.0, np.inf]),
    ]
    residual_series = pd.Series(residuals, index=frame.index)
    for column, bins in strata:
        print(f"  Alt gruplar: {column}")
        categories = pd.cut(frame[column], bins=bins, include_lowest=True)
        for interval, indices in categories.groupby(categories, observed=True).groups.items():
            subset = frame.loc[indices]
            values = residual_series.loc[indices].to_numpy()
            events = subset["event_id"].nunique()
            if events < MIN_GROUP_EVENTS:
                ci_text = f"GA yok (<{MIN_GROUP_EVENTS} olay)"
            else:
                ci = grouped_bootstrap_mean_ci(values, subset["event_id"].values, seed=seed)
                ci_text = f"95% olay-bootstrap GA=[{ci[0]:+.3f}, {ci[1]:+.3f}]"
            print(f"    {interval}: kayıt={len(subset):4d}, olay={events:3d}, "
                  f"yanlılık={values.mean():+.3f}, {ci_text}")


def main():
    tau, phi = ASB14_SIGMA_LN["rhypo"]
    model_sigma_log10 = np.sqrt(tau ** 2 + phi ** 2) / np.log(10)
    print(f"Hedef: {TARGET} (log10 g birimi). Modelin kendi toplam sigması: {model_sigma_log10:.3f}\n")

    raw_splits = {name: pd.read_csv(BENCH_DIR / f"{name}.csv") for name in ["train", "val", "test"]}
    for target in TARGETS:
        if target not in raw_splits["train"].columns:
            print(f"\nHedef {target} yok; atlandı.")
            continue
        splits = {name: usable_rows(df, target) for name, df in raw_splits.items()}
        print(f"\n=== Hedef: {target} ===")
        for name, df in splits.items():
            res = residuals_log10(df, target)
            in_range = (df["hypocentral_distance_km"] <= MAX_VALID_DISTANCE_KM).values
            print(f"[{name}]")
            summarize("tüm kayıtlar (Mw mevcut)", df, res, seed=100 + len(name))
            summarize(f"R <= {MAX_VALID_DISTANCE_KM:.0f} km (geçerlilik aralığı)",
                      df.loc[in_range], res[in_range], seed=200 + len(name))

        test = splits["test"]
        test_res = residuals_log10(test, target)
        print("\nTest bölmesinde alt grup tanıları (betimleyici; nedensel yorum değildir):")
        subgroup_diagnostics(test, test_res)

    # GMPE ve doğrusal model kıyası, geomean hedefi ve aynı satırlarda yapılır.
    train = usable_rows(raw_splits["train"], TARGET)
    test = usable_rows(raw_splits["test"], TARGET)
    if train.empty or test.empty:
        return
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
