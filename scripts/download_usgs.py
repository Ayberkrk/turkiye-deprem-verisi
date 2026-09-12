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
import time
import requests
import pandas as pd
from pathlib import Path

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

# Türkiye'yi kapsayan basit dikdörtgen sınır (kabaca; komşu ülkelerden
# az miktarda sınır ötesi olay da dahil olabilir, build_dataset.py'de
# istenirse ince filtre uygulanır)
BBOX = dict(minlatitude=35.0, maxlatitude=43.0, minlongitude=25.0, maxlongitude=45.5)

START_YEAR = 1990   # Öncesi enstrümantal kayıt kalitesi düşük, isteğe göre değiştirilebilir
END_YEAR = 2026
MIN_MAGNITUDE = 3.0  # Küçük depremler dahil edilmek istenmezse yükseltilebilir

OUT_PATH = Path("data/processed/usgs_catalog_turkey.parquet")


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


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    all_frames = []
    for year in range(START_YEAR, END_YEAR + 1):
        try:
            df = fetch_year(year)
        except requests.RequestException as e:
            print(f"[UYARI] {year} yılı çekilemedi: {e}")
            continue
        if not df.empty:
            all_frames.append(df)
        print(f"{year}: {len(df)} olay")
        time.sleep(0.5)  # USGS sunucusuna nazik davranalım

    if not all_frames:
        print("Hiç veri çekilemedi.")
        return

    result = pd.concat(all_frames, ignore_index=True)
    result["time_utc"] = pd.to_datetime(result["time_ms"], unit="ms", utc=True)
    result = result.drop(columns=["time_ms"]).sort_values("time_utc").reset_index(drop=True)
    result.to_parquet(OUT_PATH, index=False)
    print(f"\nToplam {len(result)} deprem kaydı -> {OUT_PATH}")


if __name__ == "__main__":
    main()
