"""
Hugging Face veri görüntüleyicisi ve `datasets.load_dataset` için,
CSV tabanlı tabloların parquet kopyalarını üretir.

Neden gerekli: Hugging Face, bir veri setindeki tüm config'leri tek bir
dosya biçimiyle okuyor. Ana katalog parquet olduğu için CSV'lere işaret
eden config'ler (benchmark bölmeleri, olay-istasyon tablosu) parquet
okuyucuyla açılmaya çalışılıp hata veriyordu. Asıl dosyalar (CSV) yerinde
duruyor; bu script yalnızca Hub'a yüklenen `parquet/` klasörünü üretir.

Çıktı (varsayılan `hf_parquet/`, git'te takip edilmez):
    parquet/event_station/train.parquet
    parquet/<görev>/{train,validation,test}.parquet

Kullanım:
    python scripts/export_hf_parquet.py [çıktı_dizini]
"""
import sys
from pathlib import Path

import pandas as pd

PROCESSED = Path("data/processed")
BENCH_DIR = Path("benchmarks")
TASKS = ["ground_motion", "phase_picking", "early_warning"]
# Hugging Face'in standart bölme adı "validation"; depodaki dosya adı "val".
SPLIT_NAMES = {"train": "train", "val": "validation", "test": "test"}


def to_parquet_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Tamamı boş sütunları metin tipine çevirir. Bu sütunlar parquet'e
    "null" tipiyle yazılır ve bölmeler arasında şema uyuşmazlığına yol
    açabilir (bir bölmede tamamı boş, diğerinde dolu olan bir sütun)."""
    df = df.copy()
    for col in df.columns:
        if df[col].isna().all():
            df[col] = df[col].astype("string")
    return df


def aligned_split_frames(frames: dict) -> dict:
    """Aynı config'in bölmelerini ortak bir şemaya getirir: bir sütun
    bölmelerin birinde metin, diğerinde tamamı boşsa (pandas onu float
    okur) hepsinde metin yapılır."""
    frames = {name: df.copy() for name, df in frames.items()}
    for col in next(iter(frames.values())).columns:
        kinds = {name: df[col].dropna().map(type).unique().tolist() for name, df in frames.items()}
        if any(str in types for types in kinds.values()):
            for name in frames:
                frames[name][col] = frames[name][col].astype("string")
    return {name: to_parquet_frame(df) for name, df in frames.items()}


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("hf_parquet")
    root = out_dir / "parquet"

    table = aligned_split_frames({"train": pd.read_csv(PROCESSED / "event_station_table.csv")})["train"]
    (root / "event_station").mkdir(parents=True, exist_ok=True)
    table.to_parquet(root / "event_station" / "train.parquet", index=False)
    print(f"event_station: {len(table)} satır")

    for task in TASKS:
        frames = aligned_split_frames(
            {hf_name: pd.read_csv(BENCH_DIR / task / f"{name}.csv") for name, hf_name in SPLIT_NAMES.items()}
        )
        (root / task).mkdir(parents=True, exist_ok=True)
        for hf_name, df in frames.items():
            df.to_parquet(root / task / f"{hf_name}.parquet", index=False)
        print(f"{task}: " + ", ".join(f"{name}={len(df)}" for name, df in frames.items()))

    print(f"Hazır -> {root}/")


if __name__ == "__main__":
    main()
