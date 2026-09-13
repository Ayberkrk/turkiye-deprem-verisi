"""
KOERI (Kandilli Rasathanesi) istasyon ağının ORFEUS/EIDA açık FDSN servisi
üzerinden istasyon bilgisi ve (istenirse) dalga formu çekilmesi.

Kaynak: ORFEUS/EIDA, KOERI EIDA birincil düğümü
Lisans: Açık FDSN veri servisi - kayıt/izin gerekmiyor, akademik/ticari
        kullanım için standart sismoloji pratiği.

Bellek stratejisi (8GB RAM için):
- İstasyon listesi zaten küçük (KB seviyesi) - doğrudan çekilebilir.
- Dalga formları TOPLU değil, olay/istasyon bazında TEK TEK çekilir.
- Her dalga formu diske yazılır yazılmaz bellekten atılır (RAM'de biriktirilmez).

Kullanım:
    python scripts/fetch_orfeus_eida.py           # sadece istasyon listesini çeker
    python scripts/fetch_orfeus_eida.py --waveform # + örnek bir olay için dalga formu çeker
"""
import argparse
from pathlib import Path

from obspy import UTCDateTime
from obspy.clients.fdsn import Client

OUT_DIR = Path("data/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# KOERI'nin kendi EIDA düğümüne doğrudan bağlan (https://eida.koeri.boun.edu.tr)
# "ORFEUS" genel yönlendiricisi KO ağını her zaman bulamıyor; doğrudan KOERI
# istemcisi kullanmak daha güvenilir.
client = Client("KOERI")


def _instrument_types(channel_codes: set) -> str:
    """
    SEED kanal kodlama kuralına göre (ilk harf = bant/kazanç, ikinci harf =
    enstrüman tipi) istasyonun hangi sensör tiplerine sahip olduğunu döndürür:
    - N: güçlü hareket ivmeölçeri (strong-motion accelerometer) - mühendislik sınıfı
    - H: geniş bant sismometre (broadband) - genel sismoloji
    - L: uzun periyot / kısa periyot sismometre
    Bu bilgi, bir istasyonun PGA/mühendislik analizi için uygun olup
    olmadığını belirlemek için kullanılır.
    """
    types = set()
    for code in channel_codes:
        if len(code) >= 2:
            second = code[1]
            if second == "N":
                types.add("strong_motion")
            elif second == "H":
                types.add("broadband")
            elif second in ("L", "E"):
                types.add("short_period")
    return ",".join(sorted(types)) if types else "bilinmiyor"


def list_koeri_stations():
    """
    KOERI (network kodu: KO) istasyon envanterini KANAL seviyesinde çeker
    (sadece istasyon seviyesi değil) ki her istasyonun gerçek güçlü hareket
    (strong-motion) sensörü olup olmadığını ayırt edebilelim.

    Önemli: `koeri_stations.csv`'deki `start_date`/`has_strong_motion` gibi
    alanlar istasyonun BUGÜNKÜ (envanterdeki en güncel) durumunu özetler.
    Bir istasyonda bugün HN (güçlü hareket) sensörü olması, o istasyonda
    2005'te de böyle bir sensör olduğu anlamına gelmez - kanallar zamanla
    değişir (yeni sensör eklenir, eskisi kaldırılır). Bu yüzden ayrıca
    kanal bazlı, başlangıç/bitiş tarihli bir tablo (`koeri_channels.csv`)
    üretiyoruz; `fetch_waveforms_bulk.py` bir olay anında hangi sensörün
    gerçekten aktif olduğunu bu tablodan kontrol ediyor.
    """
    inventory = client.get_stations(network="KO", level="channel")
    station_rows = []
    channel_rows = []
    for net in inventory:
        for sta in net:
            channel_codes = {ch.code for ch in sta.channels}
            station_rows.append(
                dict(
                    network=net.code,
                    station=sta.code,
                    latitude=sta.latitude,
                    longitude=sta.longitude,
                    elevation=sta.elevation,
                    start_date=str(sta.start_date),
                    channel_codes=",".join(sorted(channel_codes)),
                    instrument_types=_instrument_types(channel_codes),
                    has_strong_motion="N" in {c[1] for c in channel_codes if len(c) >= 2},
                )
            )
            for ch in sta.channels:
                channel_rows.append(
                    dict(
                        network=net.code,
                        station=sta.code,
                        location=ch.location_code or "",
                        channel=ch.code,
                        instrument_type=_instrument_types({ch.code}),
                        latitude=ch.latitude,
                        longitude=ch.longitude,
                        sample_rate_hz=ch.sample_rate,
                        start_date=str(ch.start_date) if ch.start_date else None,
                        end_date=str(ch.end_date) if ch.end_date else None,
                    )
                )

    import pandas as pd

    df = pd.DataFrame(station_rows)
    out_path = OUT_DIR / "koeri_stations.csv"
    df.to_csv(out_path, index=False)
    n_sm = df["has_strong_motion"].sum()
    print(f"{len(df)} KOERI istasyonu bulundu ({n_sm} tanesi güçlü hareket "
          f"sensörüne sahip) -> {out_path}")

    channels_df = pd.DataFrame(channel_rows)
    channels_path = OUT_DIR / "koeri_channels.csv"
    channels_df.to_csv(channels_path, index=False)
    print(f"{len(channels_df)} kanal kaydı (zaman aralıklı) -> {channels_path}")

    return df


def fetch_one_waveform(network, station, event_time_utc, duration_sec=120):
    """
    Tek bir istasyon/olay için dalga formu çeker ve diske yazar.
    RAM'de tutmadan doğrudan miniSEED olarak kaydeder.
    """
    t0 = UTCDateTime(event_time_utc)
    st = client.get_waveforms(
        network=network,
        station=station,
        location="*",
        channel="HN*,HH*",  # güçlü hareket (HN) veya geniş bant (HH) kanalları
        starttime=t0,
        endtime=t0 + duration_sec,
    )
    out_path = OUT_DIR / f"{network}_{station}_{t0.date}.mseed"
    st.write(str(out_path), format="MSEED")
    print(f"Dalga formu kaydedildi -> {out_path} ({len(st)} iz)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--waveform", action="store_true", help="örnek bir dalga formu da çek")
    args = parser.parse_args()

    stations_df = list_koeri_stations()

    if args.waveform and not stations_df.empty:
        # Örnek: ilk istasyon için 2023-02-06 depreminin ilk dakikalarını dene
        first_station = stations_df.iloc[0]["station"]
        try:
            fetch_one_waveform("KO", first_station, "2023-02-06T01:17:00")
        except Exception as e:
            print(f"[UYARI] Örnek dalga formu çekilemedi (istasyon o an aktif olmayabilir): {e}")
