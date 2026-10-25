"""
USGS ComCat'ten Türkiye sınırları içindeki deprem kataloğunu indirir.

Kaynak: USGS FDSN Event Web Service
Lisans: Public domain (ABD federal kurum ürünü) - herhangi bir kısıtlama yok,
        sadece "USGS" kaynak gösterimi rica ediliyor.

Bellek stratejisi (8GB RAM için):
- Tüm zaman aralığını tek seferde çekmek yerine YILLIK parçalara bölüyoruz.
- Her yılın sonucunu diske yazıp bellekten atıyoruz (append modunda parquet).
- Hiçbir noktada tüm katalog aynı anda RAM'de tutulmuyor.

Kullanım:
    python scripts/download_usgs.py
"""
import os
import tempfile
import time
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

# Türkiye'yi kapsayan basit dikdörtgen sınır (kabaca; komşu ülkelerden
# az miktarda sınır ötesi olay da dahil olabilir, build_dataset.py'de
# istenirse ince filtre uygulanır)
BBOX = dict(minlatitude=35.0, maxlatitude=43.0, minlongitude=25.0, maxlongitude=45.5)

START_YEAR = 1990   # Öncesi enstrümantal kayıt kalitesi düşük, isteğe göre değiştirilebilir
END_YEAR = 2026
MIN_MAGNITUDE = 3.0  # Küçük depremler dahil edilmek istenmezse yükseltilebilir

OUT_PATH = Path("data/processed/usgs_catalog_turkey.parquet")
OUTPUT_SCHEMA = pa.schema(
    [
        ("event_id", pa.string()),
        ("magnitude", pa.float64()),
        ("mag_type", pa.string()),
        ("place", pa.string()),
        ("longitude", pa.float64()),
        ("latitude", pa.float64()),
        ("depth_km", pa.float64()),
        ("status", pa.string()),
        ("source", pa.string()),
        ("time_utc", pa.timestamp("ns", tz="UTC")),
    ]
)


def fetch_year(year: int) -> pd.DataFrame:
    params = dict(
        format="geojson",
        starttime=f"{year}-01-01",
        endtime=f"{year}-12-31",
        minmagnitude=MIN_MAGNITUDE,
        **BBOX,
    )
    resp = requests.get(USGS_URL, params=params, timeout=60)
    resp.raise_for_status()
    features = resp.json().get("features", [])
    rows = []
    for f in features:
        p = f["properties"]
        g = f["geometry"]["coordinates"]  # [lon, lat, depth]
        rows.append(
            dict(
                event_id=f["id"],
                time_ms=p.get("time"),
                magnitude=p.get("mag"),
                mag_type=p.get("magType"),
                place=p.get("place"),
                longitude=g[0],
                latitude=g[1],
                depth_km=g[2],
                status=p.get("status"),
                source=p.get("net"),
            )
        )
    return pd.DataFrame(rows)


def normalize_year_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize one annual response to the stable output schema."""
    if frame.empty and "time_ms" not in frame.columns:
        frame = pd.DataFrame(columns=["event_id", "time_ms", "magnitude", "mag_type", "place",
                                      "longitude", "latitude", "depth_km", "status", "source"])
    if "time_utc" not in frame.columns:
        if "time_ms" not in frame.columns:
            raise ValueError("USGS response is missing both time_ms and time_utc")
        frame = frame.copy()
        frame["time_utc"] = pd.to_datetime(frame["time_ms"], unit="ms", utc=True)
        frame = frame.drop(columns=["time_ms"])
    else:
        frame = frame.copy()
        frame["time_utc"] = pd.to_datetime(frame["time_utc"], utc=True)

    for column in OUTPUT_SCHEMA.names:
        if column not in frame.columns:
            frame[column] = pd.NA
    return frame[OUTPUT_SCHEMA.names].sort_values("time_utc").reset_index(drop=True)


def write_catalog_by_year(
    years,
    out_path: Path,
    *,
    fetcher=fetch_year,
    sleep_fn=time.sleep,
    pause_seconds: float = 0.5,
) -> tuple[int, list[int]]:
    """Fetch and write one year at a time, publishing only a complete result.

    A temporary parquet file is atomically moved into place after every year
    succeeds. Failed years are reported and prevent a partial catalog from
    replacing the previous output. Memory use is bounded by one year response.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{out_path.name}.", suffix=".tmp", dir=out_path.parent)
    os.close(fd)
    temporary_path = Path(temporary_name)
    writer = None
    failed_years: list[int] = []
    total_rows = 0
    try:
        writer = pq.ParquetWriter(temporary_path, OUTPUT_SCHEMA)
        for year in years:
            try:
                frame = normalize_year_frame(fetcher(year))
            except Exception as exc:
                failed_years.append(year)
                print(f"[UYARI] {year} yılı çekilemedi: {exc}")
            else:
                if not frame.empty:
                    arrays = {
                        column: pa.array(frame[column].tolist(), type=field.type, from_pandas=True)
                        for column, field in zip(OUTPUT_SCHEMA.names, OUTPUT_SCHEMA, strict=True)
                    }
                    table = pa.Table.from_pydict(arrays, schema=OUTPUT_SCHEMA)
                    writer.write_table(table)
                    total_rows += len(frame)
                print(f"{year}: {len(frame)} olay")
            if pause_seconds:
                sleep_fn(pause_seconds)

        writer.close()
        writer = None
        if failed_years:
            years_text = ", ".join(map(str, failed_years))
            raise RuntimeError(f"USGS catalog incomplete; failed years: {years_text}. Existing output preserved.")
        if total_rows == 0:
            raise RuntimeError("USGS catalog fetch returned zero rows for every year; existing output preserved.")
        os.replace(temporary_path, out_path)
    except Exception:
        try:
            if writer is not None:
                writer.close()
        finally:
            temporary_path.unlink(missing_ok=True)
        raise

    return total_rows, failed_years


def main():
    rows, _ = write_catalog_by_year(range(START_YEAR, END_YEAR + 1), OUT_PATH)
    print(f"\nToplam {rows} deprem kaydı -> {OUT_PATH}")


if __name__ == "__main__":
    main()
