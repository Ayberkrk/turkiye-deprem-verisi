from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from download_usgs import write_catalog_by_year


def year_frame(year: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event_id": [f"event-{year}"],
            "time_ms": [int(pd.Timestamp(f"{year}-06-01", tz="UTC").timestamp() * 1000)],
            "magnitude": [4.2],
            "mag_type": ["ml"],
            "place": ["Türkiye"],
            "longitude": [29.0],
            "latitude": [40.0],
            "depth_km": [7.0],
            "status": ["reviewed"],
            "source": ["us"],
        }
    )


def test_years_are_written_incrementally_to_one_parquet_file(tmp_path: Path) -> None:
    output = tmp_path / "catalog.parquet"
    calls = []

    def fetcher(year: int) -> pd.DataFrame:
        calls.append(year)
        return year_frame(year)

    rows, failed = write_catalog_by_year(
        [2001, 2002], output, fetcher=fetcher, sleep_fn=lambda _: None, pause_seconds=0
    )

    table = pq.read_table(output)
    assert calls == [2001, 2002]
    assert rows == 2
    assert failed == []
    assert table.column("event_id").to_pylist() == ["event-2001", "event-2002"]
    assert table.schema.field("time_utc").type.tz == "UTC"


def test_failed_year_prevents_partial_catalog_and_preserves_previous_output(tmp_path: Path) -> None:
    output = tmp_path / "catalog.parquet"
    output.write_bytes(b"previous-complete-output")
    before = output.read_bytes()

    def fetcher(year: int) -> pd.DataFrame:
        if year == 2002:
            raise RuntimeError("simulated source outage")
        return year_frame(year)

    with pytest.raises(RuntimeError, match=r"failed years: 2002.*Existing output preserved"):
        write_catalog_by_year(
            [2001, 2002], output, fetcher=fetcher, sleep_fn=lambda _: None, pause_seconds=0
        )

    assert output.read_bytes() == before
    assert sorted(path.name for path in tmp_path.iterdir()) == ["catalog.parquet"]


def test_all_failed_years_are_reported_and_do_not_create_output(tmp_path: Path) -> None:
    output = tmp_path / "catalog.parquet"

    def fail(year: int) -> pd.DataFrame:
        raise RuntimeError(f"failure {year}")

    with pytest.raises(RuntimeError, match=r"failed years: 1990, 1991"):
        write_catalog_by_year(
            [1990, 1991], output, fetcher=fail, sleep_fn=lambda _: None, pause_seconds=0
        )

    assert not output.exists()
    assert list(tmp_path.iterdir()) == []


def test_all_successful_empty_years_do_not_publish_an_empty_catalog(tmp_path: Path) -> None:
    output = tmp_path / "catalog.parquet"

    with pytest.raises(RuntimeError, match="zero rows for every year"):
        write_catalog_by_year(
            [2001, 2002],
            output,
            fetcher=lambda _year: pd.DataFrame(),
            sleep_fn=lambda _: None,
            pause_seconds=0,
        )

    assert not output.exists()
    assert list(tmp_path.iterdir()) == []


def test_all_empty_years_preserve_existing_catalog(tmp_path: Path) -> None:
    output = tmp_path / "catalog.parquet"
    output.write_bytes(b"previous-complete-output")
    before = output.read_bytes()

    with pytest.raises(RuntimeError, match="zero rows for every year"):
        write_catalog_by_year(
            [2001], output, fetcher=lambda _year: pd.DataFrame(),
            sleep_fn=lambda _: None, pause_seconds=0
        )

    assert output.read_bytes() == before
    assert sorted(path.name for path in tmp_path.iterdir()) == ["catalog.parquet"]
