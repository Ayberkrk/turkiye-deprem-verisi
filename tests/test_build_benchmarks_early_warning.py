"""
Regresyon testi: build_early_warning_task'ın "en az 10 saniyelik kayıt
süresi" filtresi bir zamanlar ölü kodmuş (event_station_table.csv'de
duration_sec sütunu hiç yoktu, bkz. issue #7). Bu test, filtrenin
gerçekten çalıştığını - kısa kayıtları dışladığını, yeterince uzun
kayıtları geçirdiğini - doğrudan kanıtlıyor.
"""
import pandas as pd

from build_benchmarks import build_early_warning_task


def _fake_table():
    return pd.DataFrame([
        dict(event_id="ev_long", station="STA1", file="a.mseed",
             p_pick_time="2023-02-06T01:17:35", magnitude=5.0,
             mag_type="mw", mw_estimate=5.0, duration_sec=210.0),
        dict(event_id="ev_short", station="STA2", file="b.mseed",
             p_pick_time="2023-02-06T01:17:40", magnitude=4.6,
             mag_type="mw", mw_estimate=4.6, duration_sec=5.0),
        dict(event_id="ev_no_mw", station="STA3", file="c.mseed",
             p_pick_time="2023-02-06T01:17:45", magnitude=4.8,
             mag_type="ml", mw_estimate=None, duration_sec=210.0),
    ])


def test_short_duration_events_excluded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "benchmarks").mkdir()
    build_early_warning_task(_fake_table())

    train = pd.read_csv(tmp_path / "benchmarks" / "early_warning" / "train.csv")
    val = pd.read_csv(tmp_path / "benchmarks" / "early_warning" / "val.csv")
    test = pd.read_csv(tmp_path / "benchmarks" / "early_warning" / "test.csv")
    all_ids = set(train["event_id"]) | set(val["event_id"]) | set(test["event_id"])

    assert "ev_long" in all_ids
    assert "ev_short" not in all_ids, (
        "10 saniyeden kısa kayıtlı olay early_warning benchmark'ına "
        "sızmamalı (bkz. issue #7)"
    )
    assert "ev_no_mw" not in all_ids  # mw_estimate eksik, ayrı bir filtre
