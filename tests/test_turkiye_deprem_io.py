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


@pytest.mark.parametrize("task,holdout,splits", [
    ("ground_motion", None, ("train", "val", "test")),
    ("phase_picking", None, ("train", "val", "test")),
    ("early_warning", None, ("train", "val", "test")),
    ("ground_motion", "station", ("train", "val", "test")),
    ("ground_motion", "time", ("train", "test")),
])
def test_load_benchmark_combinations(tmp_path, task, holdout, splits):
    from turkiye_deprem import load_benchmark

    directory = tmp_path / task
    if holdout is not None:
        directory /= f"holdout_by_{holdout}"
    directory.mkdir(parents=True)
    for split in splits:
        expected = pd.DataFrame({"event_id": [f"{task}-{holdout}-{split}"], "value": [1.5]})
        expected.to_csv(directory / f"{split}.csv", index=False)
        pd.testing.assert_frame_equal(
            load_benchmark(task, split, holdout=holdout, benchmarks_dir=str(tmp_path)), expected
        )


@pytest.mark.parametrize("task,split,holdout", [
    ("unknown", "train", None), ("../ground_motion", "train", None),
    ("ground_motion", "../train", None), ("ground_motion", "validation", None),
    ("ground_motion", "val", "time"), ("ground_motion", "train", "unknown"),
    ("phase_picking", "train", "station"), ("early_warning", "train", "time"),
])
def test_load_benchmark_rejects_invalid_combinations(tmp_path, task, split, holdout):
    from turkiye_deprem import load_benchmark

    with pytest.raises(ValueError, match="Geçerli"):
        load_benchmark(task, split, holdout=holdout, benchmarks_dir=tmp_path)


def test_load_benchmark_default_ignores_processed_env(tmp_path, monkeypatch):
    from turkiye_deprem import load_benchmark

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(ENV_VAR, str(tmp_path / "unrelated"))
    directory = tmp_path / "benchmarks" / "early_warning"
    directory.mkdir(parents=True)
    (directory / "train.csv").write_text("event_id\nsynthetic\n")
    assert load_benchmark("early_warning", "train").event_id.tolist() == ["synthetic"]


def test_load_benchmark_missing_file_has_download_hint(tmp_path):
    from turkiye_deprem import load_benchmark

    with pytest.raises(FileNotFoundError, match="hf download"):
        load_benchmark("ground_motion", "test", benchmarks_dir=tmp_path)


def test_load_stations_resolution_precedence(tmp_path, monkeypatch):
    from turkiye_deprem import load_stations

    monkeypatch.chdir(tmp_path)
    for name in ("data/processed", "env", "explicit"):
        directory = tmp_path / name
        directory.mkdir(parents=True)
        (directory / "koeri_stations.csv").write_text(f"station\n{name}\n")
    monkeypatch.delenv(ENV_VAR, raising=False)
    assert load_stations().station.tolist() == ["data/processed"]
    monkeypatch.setenv(ENV_VAR, str(tmp_path / "env"))
    assert load_stations().station.tolist() == ["env"]
    assert load_stations(data_dir=tmp_path / "explicit").station.tolist() == ["explicit"]
    assert load_stations(path="env/koeri_stations.csv", data_dir=tmp_path / "explicit").station.tolist() == ["env"]


def test_load_stations_missing_file_has_download_hint(tmp_path):
    from turkiye_deprem import load_stations

    with pytest.raises(FileNotFoundError, match="hf download"):
        load_stations(data_dir=tmp_path)
