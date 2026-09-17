"""
`data/processed/` altındaki işlenmiş veri dosyaları için yükleyici
fonksiyonlar. `scripts/` altındaki script'lerin zaten kullandığı
`PROCESSED = Path("data/processed")` kalıbıyla aynı: yollar, script'i
(veya burada `python`'ı) çalıştırdığınız dizine göre değil, çalışma
dizinindeki `data/processed/`'a göre çözülür - yani depo kökünden
çalıştırın.

Veri, bu Python paketiyle birlikte DAĞITILMAZ (~600MB). Önce README'deki
adımla indirin:

    pip install huggingface_hub
    hf download Ayberkkr/turkiye-deprem-verisi --repo-type dataset --local-dir .
"""
from pathlib import Path

import pandas as pd

PROCESSED = Path("data/processed")

_HF_DOWNLOAD_HINT = (
    "Önce veriyi indirin:\n"
    "    pip install huggingface_hub\n"
    "    hf download Ayberkkr/turkiye-deprem-verisi --repo-type dataset --local-dir .\n"
    "(bkz. README.md > 'Veriyi indirme')"
)


def _require(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"{path} bulunamadı.\n{_HF_DOWNLOAD_HINT}")
    return path


def load_catalog(path: Path | str | None = None) -> pd.DataFrame:
    """Ana veri setini yükler (84.100 olay): katalog + istasyon eşleştirmesi
    + zemin sınıfı + dalga formu öznitelikleri. Bkz. docs/schema.md.
    """
    path = Path(path) if path is not None else PROCESSED / "turkiye_deprem_veriseti_v3.parquet"
    return pd.read_parquet(_require(path))


def load_event_station_table(path: Path | str | None = None) -> pd.DataFrame:
    """Her satırı TEK BİR (event_id, station) çiftini temsil eden tabloyu
    yükler; PGA-mesafe gibi ilişkileri incelemek için `load_catalog()`
    yerine bunu kullanın (bkz. docs/schema.md).
    """
    path = Path(path) if path is not None else PROCESSED / "event_station_table.csv"
    return pd.read_csv(_require(path))


def load_waveform_features(path: Path | str | None = None) -> pd.DataFrame:
    """Her dalga formu dosyası için hesaplanan sinyal özniteliği ve kalite
    kontrol (QC) alanlarını yükler (bkz. docs/schema.md).
    """
    path = Path(path) if path is not None else PROCESSED / "waveform_features.csv"
    return pd.read_csv(_require(path))
