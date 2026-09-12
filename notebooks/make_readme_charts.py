"""
README.md için 3 görsel üretir: coğrafi dağılım haritası, büyüklük-mesafe
azalım grafiği (attenuation) ve büyüklük-zaman dağılımı. Üçüncüsü
01_baseline_example.py'de zaten üretiliyor, burada tekrar üretilmiyor.

Kullanım:
    python notebooks/make_readme_charts.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

PROCESSED = Path("data/processed")
OUT_DIR = Path("notebooks/outputs")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def plot_station_map():
    df = pd.read_parquet(PROCESSED / "turkiye_deprem_veriseti_v3.parquet")
    stations = pd.read_csv(PROCESSED / "koeri_stations.csv")

    fig, ax = plt.subplots(figsize=(9, 6))
    sc = ax.scatter(
        df["longitude"], df["latitude"], c=df["magnitude"], cmap="YlOrRd",
        s=3, alpha=0.4, vmin=3, vmax=7,
    )
    ax.scatter(
        stations["longitude"], stations["latitude"], marker="^", c="steelblue",
        s=25, edgecolor="black", linewidth=0.3, label="KOERI istasyonu",
    )
    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label("Büyüklük")
    ax.set_xlabel("Boylam")
    ax.set_ylabel("Enlem")
    ax.set_title("Deprem Kataloğu ve İstasyon Ağı (83.598 olay, 277 istasyon)")
    ax.legend(loc="lower left")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "station_map.png", dpi=130)
    print(f"Kaydedildi: {OUT_DIR / 'station_map.png'}")


def plot_pga_vs_distance():
    df = pd.read_parquet(PROCESSED / "turkiye_deprem_veriseti_v3.parquet")
    has_pga = df[df["max_pga_g"].notna() & (df["max_pga_g"] > 0)]

    fig, ax = plt.subplots(figsize=(8, 5.5))
    sc = ax.scatter(
        has_pga["nearest_strong_motion_distance_km"], has_pga["max_pga_g"],
        c=has_pga["magnitude"], cmap="viridis", s=18, alpha=0.75,
    )
    ax.set_yscale("log")
    ax.set_xlabel("Kaynak-istasyon mesafesi (km)")
    ax.set_ylabel("Tepe yer ivmesi, PGA (g)")
    ax.set_title(f"Gerçek Ölçülmüş PGA - Mesafe İlişkisi ({len(has_pga)} kayıt)")
    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label("Büyüklük")
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "pga_vs_distance.png", dpi=130)
    print(f"Kaydedildi: {OUT_DIR / 'pga_vs_distance.png'}")


if __name__ == "__main__":
    plot_station_map()
    plot_pga_vs_distance()
