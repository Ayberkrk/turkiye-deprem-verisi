"""
Veri setini "burada veri var" seviyesinden "modelleri burada adil biçimde
karşılaştırabilirsiniz" seviyesine taşımak için, üç görev için resmi
train/val/test bölmeleri üretir.

Görevler:
1. ground_motion: büyüklük + mesafe + Vs30 -> PGA/PGV (+ Sa(T), Arias, CAV)
2. phase_picking: dalga formu dosyası -> P/S varış zamanı
3. early_warning: P varışından sonraki ilk 1/3/5/10 saniyelik pencere -> Mw

Bölme yöntemi (ÇOK ÖNEMLİ): bölme HER ZAMAN olay (event_id) bazlıdır.
Aynı depremin farklı istasyonlardaki kayıtları asla train ve test'e
dağılmaz - aksi halde model, aynı depremi başka bir açıdan zaten "görmüş"
olur ve test skoru gerçekte olduğundan iyi görünür (data leakage). Bölme,
event_id'nin hash'ine dayalı deterministik bir yöntemle yapılır: aynı
event_id her zaman aynı bölmeye düşer, veri setine yeni olay eklense bile
mevcut olayların bölmesi değişmez.

Ground-motion görevi için ayrıca iki "ileri seviye" holdout üretiliyor:
- istasyon bazlı (bir istasyonun TÜM kayıtları tek bir bölmede kalır;
  modelin "hiç görmediği bir istasyona" genelleyip genelleyemediğini test eder)
- zaman bazlı (belirli bir tarihten sonraki tüm olaylar test'e ayrılır;
  modelin geleceğe genelleyip genelleyemediğini test eder)

Kullanım:
    python scripts/build_benchmarks.py
"""
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

PROCESSED = Path("data/processed")
BENCH_DIR = Path("benchmarks")

TRAIN_FRAC, VAL_FRAC = 0.70, 0.15  # kalan 0.15 test
TIME_SPLIT_CUTOFF = "2022-01-01"  # zaman bazlı holdout için eşik


def event_split(event_id: str) -> str:
    """event_id'nin MD5 hash'ine dayalı deterministik train/val/test
    ataması. Aynı event_id her zaman aynı sonucu verir (Python'ın
    yerleşik hash() fonksiyonu çalıştırmalar arası tutarlı olmadığı için
    hashlib kullanılıyor); veri setine yeni olay eklendiğinde mevcut
    olayların bölmesi değişmez."""
    digest = hashlib.md5(str(event_id).encode()).hexdigest()
    frac = int(digest[:8], 16) / 0xFFFFFFFF
    if frac < TRAIN_FRAC:
        return "train"
    if frac < TRAIN_FRAC + VAL_FRAC:
        return "val"
    return "test"


def station_split(station: str) -> str:
    digest = hashlib.md5(("station_" + str(station)).encode()).hexdigest()
    frac = int(digest[:8], 16) / 0xFFFFFFFF
    if frac < TRAIN_FRAC:
        return "train"
    if frac < TRAIN_FRAC + VAL_FRAC:
        return "val"
    return "test"


def write_splits(df: pd.DataFrame, out_dir: Path, split_col: str = "split"):
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ["train", "val", "test"]:
        subset = df[df[split_col] == name].drop(columns=[split_col])
        subset.to_csv(out_dir / f"{name}.csv", index=False)
    counts = df[split_col].value_counts().to_dict()
    print(f"  -> {out_dir}: " + ", ".join(f"{k}={counts.get(k, 0)}" for k in ["train", "val", "test"]))


def build_ground_motion_task(table: pd.DataFrame):
    """Görev: büyüklük + mesafe + zemin sınıfı -> PGA/PGV (+ Sa/Arias/CAV).
    Sadece mühendislik için güvenilir (usable_for_engineering) kayıtlar
    kullanılıyor; broadband'den düşülmüş PGA değerleri bu görevde YOK -
    onlar farklı bir sinyal kalitesini temsil ediyor ve karıştırılırsa
    modelin öğrendiği ilişkiyi bozar (bkz. issue #2)."""
    df = table[table["usable_for_engineering"] == True].copy()  # noqa: E712
    feature_cols = ["event_id", "station", "magnitude", "mag_type", "mw_estimate",
                     "epicentral_distance_km", "hypocentral_distance_km",
                     "vs30_ms", "nehrp_site_class"]
    target_cols = ["pga_g", "pgv_cms", "sa_g_0_1s", "sa_g_0_2s", "sa_g_0_5s",
                    "sa_g_1_0s", "sa_g_2_0s", "arias_intensity_ms", "cav_ms",
                    "duration_5_95_sec"]
    df = df[feature_cols + target_cols + ["time_utc"]].dropna(subset=["pga_g", "epicentral_distance_km"])

    out_dir = BENCH_DIR / "ground_motion"
    print(f"Görev: ground_motion ({len(df)} kayıt, sadece usable_for_engineering)")

    df["split"] = df["event_id"].apply(event_split)
    write_splits(df, out_dir)

    # İleri seviye holdout 1: istasyon bazlı
    df_station = df.drop(columns=["split"]).copy()
    df_station["split"] = df_station["station"].apply(station_split)
    write_splits(df_station, out_dir / "holdout_by_station")

    # İleri seviye holdout 2: zaman bazlı (belirli tarihten sonrası hep test)
    df_time = df.drop(columns=["split"]).copy()
    cutoff = pd.Timestamp(TIME_SPLIT_CUTOFF, tz="UTC")
    times = pd.to_datetime(df_time["time_utc"], utc=True, format="ISO8601")
    df_time["split"] = np.where(times < cutoff, "train", "test")
    # zaman bazlı holdoutta val ayrımı yok, sadece train/test - "test.csv"
    # ve "train.csv" üretmek için write_splits'i basitleştirilmiş çağırıyoruz
    out_time_dir = BENCH_DIR / "ground_motion" / "holdout_by_time"
    out_time_dir.mkdir(parents=True, exist_ok=True)
    for name in ["train", "test"]:
        df_time[df_time["split"] == name].drop(columns=["split"]).to_csv(out_time_dir / f"{name}.csv", index=False)
    counts = df_time["split"].value_counts().to_dict()
    print(f"  -> {out_time_dir} (eşik {TIME_SPLIT_CUTOFF}): "
          f"train={counts.get('train', 0)}, test={counts.get('test', 0)}")


def build_phase_picking_task(table: pd.DataFrame):
    """Görev: dalga formu dosyası -> P/S varış zamanı.
    DÜRÜSTLÜK NOTU: p_pick_time/s_pick_time otomatik STA/LTA ile
    üretilmiştir, S için sezgisel bir yöntem kullanılmıştır (bkz.
    DATA_CARD.md). Bu bir "ground-truth benchmark" değildir; bu split'ler
    yalnızca aynı otomatik etiketlerle bir model eğitmek/karşılaştırmak
    isteyenler için tutarlı bir bölme sağlar."""
    df = table[table["usable_for_phase_picking"] == True].copy()  # noqa: E712
    cols = ["event_id", "station", "file", "p_pick_time", "s_pick_time",
            "p_pick_confidence", "s_pick_confidence", "sampling_rate_hz" if "sampling_rate_hz" in table.columns else None]
    cols = [c for c in cols if c is not None and c in df.columns]
    df = df[cols].dropna(subset=["p_pick_time"])

    out_dir = BENCH_DIR / "phase_picking"
    print(f"Görev: phase_picking ({len(df)} kayıt, sadece usable_for_phase_picking, "
          f"ETİKETLER OTOMATİK - bkz. DATA_CARD.md)")
    df["split"] = df["event_id"].apply(event_split)
    write_splits(df, out_dir)


def build_early_warning_task(table: pd.DataFrame):
    """Görev: P varışından sonraki ilk 1/3/5/10 saniyelik pencere -> Mw.
    Depolama tasarrufu için pencereler ÖNCEDEN KESİLİP diske kopyalanmıyor
    (aynı verinin 4 kopyası anlamına gelirdi); bunun yerine her satırda
    dosya yolu + p_pick_time + kullanılabilecek pencere uzunlukları
    veriliyor, kesme işlemi kullanıcı tarafında (ör. ObsPy ile
    `tr.slice(p_pick_time, p_pick_time+N)`) yapılır. Hedef değer olarak
    mw_estimate kullanılıyor (yalnızca hesaplanabilmiş olaylar için)."""
    df = table[table["mw_estimate"].notna() & table["p_pick_time"].notna()].copy()
    # Pencerenin veri içinde gerçekten mevcut olması için en az 10 saniyelik
    # kayıt süresi olmalı (en uzun pencere seçeneği).
    if "duration_sec" in table.columns:
        df = df.merge(table[["event_id", "station"]], on=["event_id", "station"], how="inner")
    cols = ["event_id", "station", "file", "p_pick_time", "magnitude", "mag_type", "mw_estimate"]
    cols = [c for c in cols if c in df.columns]
    df = df[cols]
    df["available_windows_sec"] = "1,3,5,10"

    out_dir = BENCH_DIR / "early_warning"
    print(f"Görev: early_warning ({len(df)} kayıt, pencereler kesilmedi, "
          f"kullanıcı p_pick_time'dan kendi kesecek)")
    df["split"] = df["event_id"].apply(event_split)
    write_splits(df, out_dir)


def main():
    table_path = PROCESSED / "event_station_table.csv"
    if not table_path.exists():
        print("Önce scripts/build_event_station_table.py çalıştırılmalı.")
        return
    table = pd.read_csv(table_path)

    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    build_ground_motion_task(table)
    build_phase_picking_task(table)
    build_early_warning_task(table)
    print(f"\nTüm benchmark bölmeleri hazır -> {BENCH_DIR}/")


if __name__ == "__main__":
    main()
