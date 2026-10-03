"""
`benchmarks/early_warning/` üzerinde fiziksel olarak kalibre edilmiş bir
referans: P varışından sonraki 1/3/5/10 saniyelik pencerede tepe yer
değiştirme (Pd) ve hiposantral mesafeden büyüklük (mw_estimate) tahmini.

`05_early_warning_baseline.py` ham (cihaz tepkisi çıkarılmamış) genliği
tek başına kullanıyor ve naif tahmini neredeyse hiç geçemiyor. İki
eksiği var, burada ikisi de gideriliyor:

1. Genlik fiziksel birimde değil: istasyondan istasyona sensör kazancı
   farklı. Burada cihaz tepkisi çıkarılıp yer değiştirmeye çevriliyor.
2. Mesafe yok: aynı deprem uzak istasyonda daha küçük genlik üretir,
   mesafe bilinmeden genlikten büyüklük çıkarılamaz. Erken uyarı
   sistemlerinde konum büyüklükten önce kestirilir; bu yüzden mesafeyi
   girdi olarak kullanmak görevin tanımına aykırı değil.

Model, erken uyarı literatüründeki standart Pd ilişkisinin doğrusal
hali (Wu ve Zhao, 2006):
    Mw = a * log10(Pd) + b * log10(R_hipo) + c
Pd: düşey bileşende, 0.075 Hz'lik nedensel (tek yönlü) 2. derece
Butterworth yüksek geçiren filtreden sonra pencere içindeki tepe mutlak
yer değiştirme. Filtre bilerek nedensel: sıfır fazlı filtre pencereden
SONRAKİ örnekleri de kullanır, gerçek zamanlı bir sistemde bu mümkün
değildir.

SINIRLAMA: `p_pick_time` otomatik STA/LTA ile üretilmiş (bkz.
docs/benchmarks.md, eşleşen pick'lerin ~%40'ı 1 sn'den fazla hatalı);
pencere başlangıcındaki bu hata skora dahil. Operasyonel bir erken uyarı
sistemi değil, split üzerinde kıyas noktası.

Cihaz tepkileri `data/processed/response_cache/` altından okunur; yoksa
KOERI FDSN servisinden çekilip oraya yazılır (ağ gerekir).

Kullanım:
    python notebooks/06_early_warning_pd_baseline.py
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from obspy import UTCDateTime, read

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from enrich_waveforms import get_station_response  # noqa: E402

warnings.filterwarnings("ignore")

BENCH_DIR = Path("benchmarks/early_warning")
WINDOWS = (1, 3, 5, 10)
PD_HIGHPASS_HZ = 0.075
# Düşey bileşen için kanal önceliği: güçlü hareket sensörü yakın alanda
# doymaz; yoksa broadband'e düşülür.
VERTICAL_CHANNEL_PRIORITY = ("HNZ", "HHZ", "BHZ", "EHZ")


def vertical_trace(stream):
    for channel in VERTICAL_CHANNEL_PRIORITY:
        selected = stream.select(channel=channel)
        if len(selected):
            return selected[0]
    selected = stream.select(component="Z")
    return selected[0] if len(selected) else None


def peak_displacements(disp_trace, p_time, windows=WINDOWS) -> dict[int, float]:
    """Yer değiştirme izinde, P varışından sonraki her pencere için tepe
    mutlak değer (Pd, iz hangi birimdeyse o birimde). Pencerede örnek
    yoksa ya da tepe sıfırsa o pencere atlanır."""
    out = {}
    for w in windows:
        segment = disp_trace.slice(p_time, p_time + w).data
        if len(segment):
            peak = float(np.max(np.abs(segment)))
            if peak > 0:
                out[w] = peak
    return out


def record_pd(file_path: str, station: str, p_pick_time: str) -> dict[int, float]:
    """Bir kaydın her pencere için Pd değeri (metre); işlenemezse boş sözlük."""
    try:
        st = read(file_path)
        st.merge(method=1, fill_value="interpolate")
        st.sort(keys=["channel"])
        tr = vertical_trace(st)
        if tr is None:
            return {}
        tr = tr.copy()
        tr.remove_response(inventory=get_station_response(station), output="DISP", water_level=60)
        tr.detrend("demean")
        tr.taper(max_percentage=0.05)
        tr.filter("highpass", freq=PD_HIGHPASS_HZ, corners=2, zerophase=False)
    except Exception:
        return {}
    return peak_displacements(tr, UTCDateTime(p_pick_time))


def build_features(split: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Her satır için log10(Pd) (pencere başına bir sütun) ve log10(R).
    İşlenemeyen satır sayısını da döner."""
    rows, n_failed = [], 0
    for row in split.itertuples():
        pds = record_pd(row.file, row.station, row.p_pick_time)
        if not pds or not row.hypocentral_distance_km > 0:
            n_failed += 1
            continue
        feats = dict(mw_estimate=row.mw_estimate, log_r=np.log10(row.hypocentral_distance_km))
        feats.update({f"log_pd_{w}": np.log10(pd_value) for w, pd_value in pds.items()})
        rows.append(feats)
    return pd.DataFrame(rows), n_failed


def fit_ols(train: pd.DataFrame, cols):
    X = np.column_stack([train[cols].values, np.ones(len(train))])
    coefs, *_ = np.linalg.lstsq(X, train["mw_estimate"].values, rcond=None)
    return coefs


def predict(df: pd.DataFrame, cols, coefs) -> np.ndarray:
    return np.column_stack([df[cols].values, np.ones(len(df))]) @ coefs


def mae(y_true, y_pred) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def main():
    train_split = pd.read_csv(BENCH_DIR / "train.csv")
    test_split = pd.read_csv(BENCH_DIR / "test.csv")
    if "hypocentral_distance_km" not in train_split.columns:
        print("benchmarks/early_warning/ mesafe sütunu içermiyor - önce "
              "`python scripts/build_benchmarks.py` çalıştırın.")
        return

    print("Dalga formları okunup cihaz tepkisi çıkarılıyor (birkaç dakika sürer)...")
    train, train_failed = build_features(train_split)
    test, test_failed = build_features(test_split)
    print(f"train: {train_failed} satır işlenemedi ({len(train_split)} satırdan)")
    print(f"test:  {test_failed} satır işlenemedi ({len(test_split)} satırdan)\n")

    for w in WINDOWS:
        cols = [f"log_pd_{w}", "log_r"]
        tr, te = train.dropna(subset=cols), test.dropna(subset=cols)
        if len(tr) < 10 or len(te) == 0:
            print(f"[{w}s penceresi] yetersiz kullanılabilir kayıt, atlanıyor.")
            continue
        coefs = fit_ols(tr, cols)
        y = te["mw_estimate"].values
        err = mae(y, predict(te, cols, coefs))
        naive_err = mae(y, np.full(len(te), tr["mw_estimate"].mean()))
        print(f"[{w}s penceresi] Mw = {coefs[0]:.3f}*log10(Pd) + {coefs[1]:.3f}*log10(R) + {coefs[2]:.3f}"
              f"  |  train n={len(tr)}, test n={len(te)} -> MAE(Mw) = {err:.3f}  (naif: {naive_err:.3f})")

    print()
    print("SINIRLAMA: P varışı otomatik pick'ten geliyor ve hatalı olabiliyor;")
    print("operasyonel bir erken uyarı sistemi değil, split üzerinde kıyas noktası.")
    print("Detaylar: docs/benchmarks.md.")


if __name__ == "__main__":
    main()
