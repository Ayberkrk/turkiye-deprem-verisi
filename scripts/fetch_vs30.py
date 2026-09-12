"""
Her KOERI istasyonu için USGS Global Vs30 Mosaic'ten zemin sınıfı (Vs30)
değerini nokta sorgusu ile çeker. 631MB'lık global raster dosyasını hiç
indirmeden, USGS'in ArcGIS REST "identify" servisiyle tek tek koordinat
sorgusu yapılıyor.

Kaynak: USGS Global Vs30 Mosaic (Public Domain)
https://earthquake.usgs.gov/arcgis/rest/services/eq/vs30_mosaic/MapServer

NEHRP zemin sınıfı eşikleri (Vs30, m/s):
  A: >1500 (sert kaya)      D: 180-360 (sert zemin)
  B: 760-1500 (kaya)         E: <180 (yumuşak zemin)
  C: 360-760 (çok sert zemin)

Kullanım:
    python scripts/fetch_vs30.py
"""
import time
from pathlib import Path

import pandas as pd
import requests

PROCESSED = Path("data/processed")
VS30_URL = "https://earthquake.usgs.gov/arcgis/rest/services/eq/vs30_mosaic/MapServer/identify"


def nehrp_class(vs30: float) -> str:
    if vs30 is None:
        return None
    if vs30 > 1500:
        return "A"
    if vs30 > 760:
        return "B"
    if vs30 > 360:
        return "C"
    if vs30 > 180:
        return "D"
    return "E"


def query_vs30(lat: float, lon: float) -> float:
    params = {
        "geometry": f'{{"x":{lon},"y":{lat}}}',
        "geometryType": "esriGeometryPoint",
        "sr": 4326,
        "layers": "all",
        "tolerance": 2,
        "mapExtent": f"{lon-1},{lat-1},{lon+1},{lat+1}",
        "imageDisplay": "400,400,96",
        "returnGeometry": "false",
        "f": "json",
    }
    resp = requests.get(VS30_URL, params=params, timeout=30)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        return None
    return float(results[0]["attributes"]["Classify.Pixel Value"])


def main():
    stations = pd.read_csv(PROCESSED / "koeri_stations.csv")

    vs30_values, site_classes = [], []
    for i, row in stations.iterrows():
        try:
            vs30 = query_vs30(row["latitude"], row["longitude"])
        except requests.RequestException as e:
            print(f"[UYARI] {row['station']} için Vs30 alınamadı: {e}")
            vs30 = None
        vs30_values.append(vs30)
        site_classes.append(nehrp_class(vs30))
        if i % 50 == 0:
            print(f"[{i}/{len(stations)}] işlendi")
        time.sleep(0.2)

    stations["vs30_ms"] = vs30_values
    stations["nehrp_site_class"] = site_classes
    stations.to_csv(PROCESSED / "koeri_stations.csv", index=False)

    print(f"\nTamamlandı. {stations['vs30_ms'].notna().sum()}/{len(stations)} istasyon için Vs30 eklendi.")
    print(stations["nehrp_site_class"].value_counts())


if __name__ == "__main__":
    main()
