"""
`data/processed/` altındaki işlenmiş veri dosyaları için yükleyici
fonksiyonlar.

Veri, bu Python paketiyle birlikte DAĞITILMAZ (~600MB). Önce README'deki
adımla indirin:

    pip install huggingface_hub
    hf download Ayberkkr/turkiye-deprem-verisi --repo-type dataset --local-dir .

Hangi `data/processed/` dizininin kullanılacağı şu öncelik sırasıyla
belirlenir (işlenmiş veri yükleyicilerinde aynı):

1. Fonksiyona doğrudan `path=` verilirse, o dosya yolu aynen kullanılır.
2. `data_dir=` verilirse, o dizin + standart dosya adı kullanılır.
3. `TURKIYE_DEPREM_DATA_DIR` ortam değişkeni ayarlıysa, o dizin kullanılır
   - bir notebook/script içinde tek seferde ayarlayıp her çağrıda
   `data_dir` tekrarlamaktan kurtarır.
4. Hiçbiri yoksa, çalışma dizinine göre `data/processed/` (repo kökünden
   çalıştıran kullanıcılar için mevcut/varsayılan davranış - script'lerin
   zaten kullandığı `PROCESSED = Path("data/processed")` kalıbıyla aynı).

Bu sıralama sayesinde repo kökü dışında (başka bir proje klasörü, farklı
dizinden açılan bir notebook) çalışan kullanıcılar da veriyi indirdikleri
gerçek dizini bir kere belirtip kullanabiliyor.
"""
import os
from pathlib import Path

import pandas as pd

DEFAULT_PROCESSED = Path("data/processed")
ENV_VAR = "TURKIYE_DEPREM_DATA_DIR"

_HF_DOWNLOAD_HINT = (
    "Önce veriyi indirin:\n"
    "    pip install huggingface_hub\n"
    "    hf download Ayberkkr/turkiye-deprem-verisi --repo-type dataset --local-dir .\n"
    "(bkz. README.md > 'Veriyi indirme')"
)


def _resolve_processed_dir(data_dir: Path | str | None) -> Path:
    if data_dir is not None:
        return Path(data_dir)
    env = os.environ.get(ENV_VAR)
    if env:
        return Path(env)
    return DEFAULT_PROCESSED


def _require(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"{path} bulunamadı.\n{_HF_DOWNLOAD_HINT}")
    return path


def load_catalog(path: Path | str | None = None, data_dir: Path | str | None = None) -> pd.DataFrame:
    """Ana veri setini yükler (84.080 olay): katalog + istasyon eşleştirmesi
    + zemin sınıfı + dalga formu öznitelikleri. Bkz. docs/schema.md.
    """
    path = Path(path) if path is not None else _resolve_processed_dir(data_dir) / "turkiye_deprem_veriseti_v3.parquet"
    return pd.read_parquet(_require(path))


def load_event_station_table(path: Path | str | None = None, data_dir: Path | str | None = None) -> pd.DataFrame:
    """Her satırı TEK BİR (event_id, station) çiftini temsil eden tabloyu
    yükler; PGA-mesafe gibi ilişkileri incelemek için `load_catalog()`
    yerine bunu kullanın (bkz. docs/schema.md).
    """
    path = Path(path) if path is not None else _resolve_processed_dir(data_dir) / "event_station_table.csv"
    return pd.read_csv(_require(path))


def load_waveform_features(path: Path | str | None = None, data_dir: Path | str | None = None) -> pd.DataFrame:
    """Her dalga formu dosyası için hesaplanan sinyal özniteliği ve kalite
    kontrol (QC) alanlarını yükler (bkz. docs/schema.md).
    """
    path = Path(path) if path is not None else _resolve_processed_dir(data_dir) / "waveform_features.csv"
    return pd.read_csv(_require(path))


def load_stations(path: Path | str | None = None, data_dir: Path | str | None = None) -> pd.DataFrame:
    """İstasyon tablosunu yükler; path/data_dir/ortam değişkeni önceliği
    diğer işlenmiş veri yükleyicileriyle aynıdır.
    """
    path = Path(path) if path is not None else _resolve_processed_dir(data_dir) / "koeri_stations.csv"
    return pd.read_csv(_require(path))


def load_benchmark(
    task: str, split: str, holdout: str | None = None, benchmarks_dir: Path | str | None = None
) -> pd.DataFrame:
    """Resmi benchmark bölmesini yükler; bölmeleri yeniden oluşturmaz.

    benchmarks_dir verilirse doğrudan benchmark kökü olarak kullanılır;
    aksi halde çalışma dizinine göre benchmarks/ kullanılır. Benchmark'lar
    data/processed/ altında olmadığından TURKIYE_DEPREM_DATA_DIR burada
    kullanılmaz; repo dışındaki notebook'larda benchmarks_dir belirtin.

    Geçersiz görev/bölme/holdout birleşimleri dosya okunmadan ValueError
    verir. Zaman holdout'unda val bölmesi yoktur.
    """
    tasks = ("ground_motion", "phase_picking", "early_warning")
    if task not in tasks:
        raise ValueError(f"Geçerli task seçenekleri: {', '.join(tasks)}")
    holdouts = (None, "station", "time") if task == "ground_motion" else (None,)
    if holdout not in holdouts:
        raise ValueError(f"Geçerli holdout seçenekleri ({task}): {holdouts}")
    splits = ("train", "test") if holdout == "time" else ("train", "val", "test")
    if split not in splits:
        raise ValueError(f"Geçerli split seçenekleri ({task}, holdout={holdout}): {', '.join(splits)}")
    directory = Path(benchmarks_dir) if benchmarks_dir is not None else Path("benchmarks")
    directory /= task
    if holdout is not None:
        directory /= f"holdout_by_{holdout}"
    return pd.read_csv(_require(directory / f"{split}.csv"))
