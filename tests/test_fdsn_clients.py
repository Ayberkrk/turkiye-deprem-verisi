"""FDSN servis keşfi import sırasında değil, ilk istekte yapılmalı."""
import importlib
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

MODULES = [
    ("enrich_waveforms", "KOERI"),
    ("fetch_waveforms_bulk", "KOERI"),
    ("fetch_orfeus_eida", "KOERI"),
    ("fetch_isc_picks", "ISC"),
]
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


@pytest.mark.parametrize("module_name,provider", MODULES)
def test_import_does_not_create_client_or_use_network(module_name, provider, tmp_path):
    # Ayrı süreç, conftest veya önceki testlerin import önbelleğini kullanmaz.
    code = f'''
import sys
from unittest.mock import patch
sys.path.insert(0, {str(SCRIPTS)!r})
def block_network(event, args):
    if event in ("socket.connect", "socket.getaddrinfo", "socket.sendto"):
        raise AssertionError("Network access during import: " + event)
sys.addaudithook(block_network)
with patch("obspy.clients.fdsn.Client", side_effect=AssertionError("Client during import")):
    __import__({module_name!r})
'''
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("module_name,provider", MODULES)
def test_client_is_created_once_on_first_use(module_name, provider, monkeypatch):
    module = importlib.import_module(module_name)
    monkeypatch.setattr(module, "_client", None)
    factory = Mock()
    monkeypatch.setattr(module, "Client", factory)
    factory.assert_not_called()
    first = module.get_client()
    assert first is factory.return_value
    assert module.get_client() is first
    factory.assert_called_once_with(provider)


@pytest.mark.parametrize("module_name,provider", MODULES)
def test_failed_discovery_can_be_retried(module_name, provider, monkeypatch):
    module = importlib.import_module(module_name)
    monkeypatch.setattr(module, "_client", None)
    client = object()
    factory = Mock(side_effect=[RuntimeError("offline"), client])
    monkeypatch.setattr(module, "Client", factory)
    with pytest.raises(RuntimeError, match="offline"):
        module.get_client()
    assert module._client is None
    assert module.get_client() is client
    assert module.get_client() is client
    assert factory.call_count == 2
    factory.assert_called_with(provider)


def test_station_response_uses_lazy_client_and_memory_cache(monkeypatch, tmp_path):
    import enrich_waveforms as module

    monkeypatch.setattr(module, "RESPONSE_CACHE_DIR", tmp_path)
    monkeypatch.setattr(module, "_response_cache", {})
    monkeypatch.setattr(module, "_client", None)
    factory = Mock()
    monkeypatch.setattr(module, "Client", factory)
    response = module.get_station_response("TEST")
    assert module.get_station_response("TEST") is response
    factory.assert_called_once_with("KOERI")
    factory.return_value.get_stations.assert_called_once_with(network="KO", station="TEST", level="response")
    response.write.assert_called_once_with(str(tmp_path / "TEST.xml"), format="STATIONXML")


def test_disk_response_does_not_create_client(monkeypatch, tmp_path):
    import enrich_waveforms as module
    import obspy

    monkeypatch.setattr(module, "RESPONSE_CACHE_DIR", tmp_path)
    monkeypatch.setattr(module, "_response_cache", {})
    (tmp_path / "TEST.xml").write_text("synthetic inventory placeholder")
    reader = Mock()
    monkeypatch.setattr(obspy, "read_inventory", reader)
    factory = Mock(side_effect=AssertionError("Unnecessary discovery"))
    monkeypatch.setattr(module, "Client", factory)
    monkeypatch.setattr(module, "_client", None)
    assert module.get_station_response("TEST") is reader.return_value
    factory.assert_not_called()


def test_waveform_request_keeps_parameters(monkeypatch, tmp_path):
    import fetch_orfeus_eida as module
    from obspy import UTCDateTime

    monkeypatch.setattr(module, "OUT_DIR", tmp_path)
    monkeypatch.setattr(module, "_client", None)
    stream = Mock()
    stream.__len__ = Mock(return_value=1)
    factory = Mock()
    factory.return_value.get_waveforms.return_value = stream
    monkeypatch.setattr(module, "Client", factory)
    t0 = UTCDateTime("2020-01-01")
    module.fetch_one_waveform("KO", "TEST", t0, duration_sec=90)
    factory.assert_called_once_with("KOERI")
    factory.return_value.get_waveforms.assert_called_once_with(
        network="KO", station="TEST", location="*", channel="HN*,HH*", starttime=t0, endtime=t0 + 90,
    )
    stream.write.assert_called_once_with(str(tmp_path / "KO_TEST_2020-01-01.mseed"), format="MSEED")


def test_isc_main_uses_lazy_client(monkeypatch):
    import fetch_isc_picks as module
    import pandas as pd
    from obspy import UTCDateTime

    event_time = UTCDateTime("2020-01-01")
    targets = pd.DataFrame([dict(event_id="synthetic", time_utc=str(event_time),
                                 latitude=39.0, longitude=32.0, magnitude=4.0, stations={"TEST"})])
    monkeypatch.setattr(module, "load_target_events", lambda: targets)
    monkeypatch.setattr(module, "load_progress", set)
    monkeypatch.setattr(module, "append_picks", Mock())
    monkeypatch.setattr(module, "append_progress", Mock())
    monkeypatch.setattr(module.time, "sleep", Mock())
    monkeypatch.setattr(module, "_client", None)
    factory = Mock()
    factory.return_value.get_events.return_value = []
    monkeypatch.setattr(module, "Client", factory)
    module.main()
    factory.assert_called_once_with("ISC")
    factory.return_value.get_events.assert_called_once_with(
        starttime=event_time - module.TIME_WINDOW_SEC, endtime=event_time + module.TIME_WINDOW_SEC,
        minlatitude=39.0 - module.BBOX_MARGIN_DEG, maxlatitude=39.0 + module.BBOX_MARGIN_DEG,
        minlongitude=32.0 - module.BBOX_MARGIN_DEG, maxlongitude=32.0 + module.BBOX_MARGIN_DEG,
        includearrivals=True,
    )
    module.append_progress.assert_called_once_with("synthetic")


def test_bulk_main_uses_lazy_client(monkeypatch, tmp_path):
    import fetch_waveforms_bulk as module
    import pandas as pd
    from obspy import UTCDateTime

    event_time = pd.Timestamp("2020-01-01", tz="UTC")
    events = pd.DataFrame([dict(event_id="synthetic", time_utc=event_time,
                               latitude=39.0, longitude=32.0, magnitude=4.0)])
    stations = pd.DataFrame([dict(station="TEST", start_date="2010-01-01", latitude=39.0, longitude=32.0)])
    monkeypatch.setattr(module, "WAVEFORM_DIR", tmp_path)
    monkeypatch.setattr(module, "_migrate_log_if_needed", Mock())
    monkeypatch.setattr(module, "load_candidate_events", lambda: events)
    monkeypatch.setattr(module.pd, "read_csv", lambda *a, **k: stations)
    monkeypatch.setattr(module, "load_channel_activity", lambda: None)
    monkeypatch.setattr(module, "load_already_tried", dict)
    monkeypatch.setattr(module, "append_log", Mock())
    monkeypatch.setattr(module.time, "sleep", Mock())
    monkeypatch.setattr(module, "_client", None)
    factory = Mock()
    factory.return_value.get_waveforms.return_value = []
    monkeypatch.setattr(module, "Client", factory)
    module.main()
    factory.assert_called_once_with("KOERI")
    factory.return_value.get_waveforms.assert_called_once_with(
        network="KO", station="TEST", location="*", channel="HH*,HN*,EH*,BH*",
        starttime=UTCDateTime(event_time) - module.WINDOW_BEFORE_SEC,
        endtime=UTCDateTime(event_time) + module.WINDOW_AFTER_SEC,
    )
    assert module.append_log.call_args.args[0]["status"] == "no_data"


@pytest.mark.parametrize("module_name", ["enrich_waveforms", "fetch_waveforms_bulk", "fetch_isc_picks"])
def test_main_discovery_failure_stops_before_output(module_name, monkeypatch, tmp_path):
    # Eski modül düzeyi kurucunun hatası hiçbir dosya/ilerleme yazdırmıyordu.
    module = importlib.import_module(module_name)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "_client", None)
    factory = Mock(side_effect=RuntimeError("discovery failed"))
    monkeypatch.setattr(module, "Client", factory)
    writers = []
    for name in ("append_progress", "append_picks", "append_log", "compute_features"):
        if hasattr(module, name):
            writer = Mock(side_effect=AssertionError("Output before discovery"))
            monkeypatch.setattr(module, name, writer)
            writers.append(writer)
    with pytest.raises(RuntimeError, match="discovery failed"):
        module.main()
    factory.assert_called_once()
    for writer in writers:
        writer.assert_not_called()
    assert list(tmp_path.iterdir()) == []
