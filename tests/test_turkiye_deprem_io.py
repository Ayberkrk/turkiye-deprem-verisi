"""
turkiye_deprem paketindeki yükleyici fonksiyonlar için birim testler:
(1) sentetik bir parquet/CSV'yi doğru okuduklarını, (2) dosya eksikken
Hugging Face indirme talimatına işaret eden açıklayıcı bir hata
verdiklerini, (3) `data_dir` parametresi ve `TURKIYE_DEPREM_DATA_DIR`
ortam değişkeninin çalışma dizininden BAĞIMSIZ çalıştığını doğrular
(bkz. issue #19).
"""
import pandas as pd
import pytest

from turkiye_deprem import load_catalog, load_event_station_table, load_waveform_features
from turkiye_deprem.io import ENV_VAR


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


def test_load_catalog_data_dir_works_from_different_cwd(tmp_path, monkeypatch):
    # Veri, çalışma dizininden TAMAMEN ayrı bir "indirilmiş veri" klasöründe;
    # cwd ise boş, alakasız bir dizin - repo köküyle hiçbir ilgisi yok.
    data_dir = tmp_path / "indirilen_veri"
    data_dir.mkdir()
    pd.DataFrame({"event_id": ["ev1"], "magnitude": [5.0]}).to_parquet(
        data_dir / "turkiye_deprem_veriseti_v3.parquet"
    )
    other_cwd = tmp_path / "notebook_klasoru"
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)

    df = load_catalog(data_dir=data_dir)

    assert len(df) == 1


def test_load_catalog_env_var_works_without_repeating_data_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "indirilen_veri"
    data_dir.mkdir()
    pd.DataFrame({"event_id": ["ev1", "ev2"], "magnitude": [4.0, 5.0]}).to_parquet(
        data_dir / "turkiye_deprem_veriseti_v3.parquet"
    )
    pd.DataFrame({"file": ["a.mseed"], "pga_g": [0.1]}).to_csv(
        data_dir / "waveform_features.csv", index=False
    )
    monkeypatch.setenv(ENV_VAR, str(data_dir))
    monkeypatch.chdir(tmp_path)

    # data_dir'i tekrar vermeden, iki farklı yükleyici de aynı ortam
    # değişkenini kullanmalı.
    assert len(load_catalog()) == 2
    assert len(load_waveform_features()) == 1


def test_load_catalog_explicit_data_dir_overrides_env_var(tmp_path, monkeypatch):
    env_dir = tmp_path / "env_veri"
    env_dir.mkdir()
    pd.DataFrame({"event_id": ["ev1"], "magnitude": [5.0]}).to_parquet(
        env_dir / "turkiye_deprem_veriseti_v3.parquet"
    )
    override_dir = tmp_path / "override_veri"
    override_dir.mkdir()
    pd.DataFrame({"event_id": ["ev1", "ev2", "ev3"], "magnitude": [4.0, 5.0, 6.0]}).to_parquet(
        override_dir / "turkiye_deprem_veriseti_v3.parquet"
    )
    monkeypatch.setenv(ENV_VAR, str(env_dir))

    df = load_catalog(data_dir=override_dir)

    assert len(df) == 3


def test_load_catalog_missing_file_in_data_dir_raises_helpful_error(tmp_path):
    empty_dir = tmp_path / "bos_dizin"
    empty_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="hf download"):
        load_catalog(data_dir=empty_dir)
