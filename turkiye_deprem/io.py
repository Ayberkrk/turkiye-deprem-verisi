"""
`data/processed/` altındaki işlenmiş veri dosyaları için yükleyici
fonksiyonlar.

Veri, bu Python paketiyle birlikte DAĞITILMAZ (~600MB). Önce README'deki
adımla indirin:

    pip install huggingface_hub
    hf download Ayberkkr/turkiye-deprem-verisi --repo-type dataset --local-dir .

Hangi `data/processed/` dizininin kullanılacağı şu öncelik sırasıyla
belirlenir (her yükleyicide aynı):

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
    """Ana veri setini yükler (84.100 olay): katalog + istasyon eşleştirmesi
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
