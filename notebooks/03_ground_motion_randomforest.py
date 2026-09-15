"""
`ground_motion` görevinde, `02_ground_motion_baseline.py`'deki basit
doğrusal modelin yanına bir RandomForest ekleyip ikisini kıyaslar.

Amaç: "veride, doğrusal bir denklemin yakalayamadığı ama daha esnek bir
modelin yakalayabileceği bir ilişki kaldı mı?" sorusuna cevap vermek.
RandomForest, birçok karar ağacının ortalamasını alarak doğrusal
olmayan ilişkileri ve öznitelikler arası etkileşimleri (ör. büyüklük
ve mesafenin birlikte etkisi) otomatik yakalayabiliyor - bu yüzden
doğrusal modelden daha iyi çıkması bekleniyor; ne kadar iyi çıktığı,
doğrusal modelin ne kadarını "masada bıraktığının" bir ölçüsü.

`02_ground_motion_baseline.py`'nin aksine bu script scikit-learn
gerektirir (bkz. requirements-dev.txt) - amaç orada "ekstra bağımlılık
gerekmez" sözünü bozmadan, isteyenin daha güçlü bir kıyaslama da
görebilmesini sağlamak.

Kullanım:
    pip install -r requirements-dev.txt
    python notebooks/03_ground_motion_randomforest.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

sys.path.insert(0, str(Path(__file__).parent))
from importlib import import_module

baseline = import_module("02_ground_motion_baseline")

BENCH_DIR = baseline.BENCH_DIR
FEATURES = baseline.FEATURES

# Ağaç sayısı ve derinlik, veri setinin küçüklüğüne (~1400 train satırı)
# göre aşırı öğrenmeyi (overfitting) sınırlamak için mütevazı tutuldu;
# random_state sabit, sonuç her çalıştırmada aynı çıksın diye.
RF_PARAMS = dict(n_estimators=200, max_depth=8, min_samples_leaf=5, random_state=42, n_jobs=-1)


def main():
    train = baseline._prepare(pd.read_csv(BENCH_DIR / "train.csv"))
    val = baseline._prepare(pd.read_csv(BENCH_DIR / "val.csv"))
    test = baseline._prepare(pd.read_csv(BENCH_DIR / "test.csv"))

    ols_coefs = baseline._fit_ols(train)

    rf = RandomForestRegressor(**RF_PARAMS)
    rf.fit(train[FEATURES].values, train["log_pga_g"].values)

    print(f"(train n={len(train)}, val n={len(val)}, test n={len(test)})\n")
    print(f"{'split':<6} {'model':<14} {'RMSE(log10 g)':<15} {'R2':<8}")
    for name, split in [("val", val), ("test", test)]:
        y_true = split["log_pga_g"].values

        ols_pred = baseline._predict(split, ols_coefs)
        rf_pred = rf.predict(split[FEATURES].values)

        for model_name, pred in [("doğrusal (OLS)", ols_pred), ("RandomForest", rf_pred)]:
            rmse = baseline._rmse(y_true, pred)
            ss_res = np.sum((y_true - pred) ** 2)
            ss_tot = np.sum((y_true - y_true.mean()) ** 2)
            r2 = 1 - ss_res / ss_tot
            print(f"{name:<6} {model_name:<14} {rmse:<15.4f} {r2:<8.3f}")

    importances = dict(zip(FEATURES, rf.feature_importances_))
    print("\nRandomForest öznitelik önemi (feature importance):")
    for feat, imp in sorted(importances.items(), key=lambda kv: -kv[1]):
        print(f"  {feat}: {imp:.3f}")


if __name__ == "__main__":
    main()
