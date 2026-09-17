"""
turkiye_deprem paketindeki yükleyici fonksiyonlar için birim testler:
(1) sentetik bir parquet/CSV'yi doğru okuduklarını, (2) dosya eksikken
Hugging Face indirme talimatına işaret eden açıklayıcı bir hata
verdiklerini doğrular.
"""
import pandas as pd
import pytest

from turkiye_deprem import load_catalog, load_event_station_table, load_waveform_features


def test_load_catalog_reads_parquet(tmp_path):
    path = tmp_path / "catalog.parquet"
    pd.DataFrame({"event_id": ["ev1", "ev2"], "magnitude": [4.5, 5.0]}).to_parquet(path)

    df = load_catalog(path)

    assert len(df) == 2
    assert list(df["event_id"]) == ["ev1", "ev2"]


def test_load_catalog_missing_file_raises_helpful_error(tmp_path):
    missing = tmp_path / "does_not_exist.parquet"

    with pytest.raises(FileNotFoundError, match="hf download"):
        load_catalog(missing)


def test_load_event_station_table_reads_csv(tmp_path):
    path = tmp_path / "event_station_table.csv"
    pd.DataFrame({"event_id": ["ev1"], "station": ["A"], "epicentral_distance_km": [7.04]}).to_csv(
        path, index=False
    )

    df = load_event_station_table(path)

    assert len(df) == 1
    assert df.loc[0, "station"] == "A"


def test_load_event_station_table_missing_file_raises_helpful_error(tmp_path):
    missing = tmp_path / "does_not_exist.csv"

    with pytest.raises(FileNotFoundError, match="hf download"):
        load_event_station_table(missing)


def test_load_waveform_features_reads_csv(tmp_path):
    path = tmp_path / "waveform_features.csv"
    pd.DataFrame({"file": ["a.mseed"], "pga_g": [0.05]}).to_csv(path, index=False)

    df = load_waveform_features(path)

    assert len(df) == 1
    assert df.loc[0, "pga_g"] == pytest.approx(0.05)


def test_load_waveform_features_missing_file_raises_helpful_error(tmp_path):
    missing = tmp_path / "does_not_exist.csv"

    with pytest.raises(FileNotFoundError, match="hf download"):
        load_waveform_features(missing)
