"""
Veri setinin nasıl kullanılacağını gösteren basit bir örnek.

Bu bir model değil, verinin gerçekten çalıştığını gösteren bir kullanım
kılavuzu. Jupyter'e ihtiyaç duymadan doğrudan çalışır:
`python notebooks/01_baseline_example.py`

Üretir:
- outputs/magnitude_over_time.png  : yıllara göre büyüklük dağılımı
- outputs/example_waveform.png     : gerçek bir depremin dalga formu
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # ekran gerektirmeden dosyaya kaydet
import matplotlib.pyplot as plt
import pandas as pd
from obspy import read

PROCESSED = Path("data/processed")
OUT_DIR = Path("notebooks/outputs")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def plot_magnitude_over_time():
    df = pd.read_parquet(PROCESSED / "turkiye_deprem_veriseti_v3.parquet")

    # En tutarlı ölçek olan moment magnitude'a odaklan (bkz. docs/schema.md)
    mw = df[df["magnitude_scale_group"] == "moment_magnitude"]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.scatter(df["time_utc"], df["magnitude"], s=4, alpha=0.3, label="Tüm ölçekler (karışık)")
    ax.scatter(mw["time_utc"], mw["magnitude"], s=10, color="crimson", label="Sadece Mw (moment magnitude)")
    ax.set_xlabel("Tarih")
    ax.set_ylabel("Büyüklük")
    ax.set_title("Türkiye Deprem Kataloğu (1990-2026)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "magnitude_over_time.png", dpi=120)
    print(f"Kaydedildi: {OUT_DIR / 'magnitude_over_time.png'}")

    print(f"\nÖzet istatistik:")
    print(f"  Toplam olay: {len(df)}")
    print(f"  Gerçek dalga formu olan olay: {df['has_waveform'].sum()}")
    print(f"  Güçlü hareket istasyonuna <50km mesafede olan olay: "
          f"{(df['nearest_strong_motion_distance_km'] < 50).sum()}")


def plot_example_waveform():
    waveform_files = sorted((PROCESSED / "waveforms").glob("*.mseed"))
    if not waveform_files:
        print("Örnek dalga formu bulunamadı, atlanıyor.")
        return

    # En büyük depremin dosyasını seç (en görsel/anlamlı örnek için)
    df = pd.read_parquet(PROCESSED / "turkiye_deprem_veriseti_v3.parquet")
    big_event = df[df["has_waveform"]].nlargest(1, "magnitude").iloc[0]
    candidates = [f for f in waveform_files if f.name.startswith(big_event["event_id"])]
    f = candidates[0] if candidates else waveform_files[0]

    st = read(str(f))
    fig = st.plot(handle=True, size=(900, 500))
    fig.savefig(OUT_DIR / "example_waveform.png", dpi=120)
    print(f"Kaydedildi: {OUT_DIR / 'example_waveform.png'} "
          f"(kaynak: {f.name}, büyüklük={big_event['magnitude']})")


if __name__ == "__main__":
    plot_magnitude_over_time()
    plot_example_waveform()
