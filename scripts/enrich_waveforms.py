"""
Her dalga formu dosyası için PGA, PGV, sinyal/gürültü oranı (SNR) ve
P-dalgası varış zamanını hesaplar; S-dalgası için basit bir tahmin üretir.

Yöntem notları:
- PGA/PGV, aletin ham sayım (count) çıktısından değil, cihaz tepkisi
  (instrument response) çıkarılmış gerçek fiziksel birimlerden hesaplanır.
  İstasyon tepki bilgisi KOERI'den istasyon bazında çekilip diskte
  önbelleğe alınır, böylece her dosya için tekrar ağ isteği yapılmaz.
- P-dalgası varışı, dikey (Z) bileşende klasik STA/LTA tetikleyicisiyle
  bulunur. S-dalgası için ayrı, güvenilir bir otomatik okuyucu
  uygulanmadı; onun yerine yatay bileşenlerdeki enerjinin P varışından
  sonraki en büyük ikinci tetiklenmesi kaba bir S adayı olarak işaretlenir.
  Bu bir sezgisel yöntemdir, yayın kalitesinde faz okuma değildir.
- SNR, P varışından önceki pencerenin RMS'i ile sonraki pencerenin RMS'i
  oranından (dB) hesaplanır.

Kullanım:
    python scripts/enrich_waveforms.py
"""
import csv
import warnings
from pathlib import Path

import numpy as np
from obspy import read
from obspy.clients.fdsn import Client
from obspy.signal.trigger import classic_sta_lta, trigger_onset

warnings.filterwarnings("ignore")

PROCESSED = Path("data/processed")
WAVEFORM_DIR = PROCESSED / "waveforms"
OUT_PATH = PROCESSED / "waveform_features.csv"
RESPONSE_CACHE_DIR = PROCESSED / "response_cache"
RESPONSE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

client = Client("KOERI")
_response_cache = {}


def get_station_response(station: str):
    """Bir istasyonun tepki bilgisini diskten oku, yoksa ağdan çek ve önbelleğe al."""
    if station in _response_cache:
        return _response_cache[station]

    cache_file = RESPONSE_CACHE_DIR / f"{station}.xml"
    if cache_file.exists():
        from obspy import read_inventory

        inv = read_inventory(str(cache_file))
    else:
        inv = client.get_stations(network="KO", station=station, level="response")
        inv.write(str(cache_file), format="STATIONXML")

    _response_cache[station] = inv
    return inv


def compute_features(mseed_path: Path):
    st = read(str(mseed_path))
    st.merge(method=1, fill_value="interpolate")
    station = st[0].stats.station

    try:
        inv = get_station_response(station)
    except Exception:
        return None

    result = dict(pga_g=None, pgv_cms=None, snr_db=None, p_pick_time=None, s_pick_time=None)

    # PGA (yer çekimi biriminde, g) ve PGV (cm/s) hesabı için tepki çıkarımı
    try:
        st_acc = st.copy()
        st_acc.remove_response(inventory=inv, output="ACC", water_level=60)
        pga_ms2 = max(np.max(np.abs(tr.data)) for tr in st_acc)
        result["pga_g"] = round(pga_ms2 / 9.81, 5)
    except Exception:
        pass

    try:
        st_vel = st.copy()
        st_vel.remove_response(inventory=inv, output="VEL", water_level=60)
        pgv_ms = max(np.max(np.abs(tr.data)) for tr in st_vel)
        result["pgv_cms"] = round(pgv_ms * 100, 4)
    except Exception:
        pass

    # P-dalgası tespiti: dikey bileşende STA/LTA
    z_trace = None
    for tr in st:
        if tr.stats.channel.endswith("Z"):
            z_trace = tr
            break
    if z_trace is not None and z_trace.stats.npts > 200:
        sr = z_trace.stats.sampling_rate
        cft = classic_sta_lta(z_trace.data, int(1 * sr), int(10 * sr))
        onsets = trigger_onset(cft, 3.5, 0.5)
        if len(onsets) > 0:
            p_idx = onsets[0][0]
            result["p_pick_time"] = str(z_trace.stats.starttime + p_idx / sr)

            # SNR: P'den önceki 5 saniye vs P'den sonraki 5 saniye (RMS oranı)
            noise_window = z_trace.data[max(0, p_idx - int(5 * sr)):p_idx]
            signal_window = z_trace.data[p_idx:p_idx + int(5 * sr)]
            if len(noise_window) > 10 and len(signal_window) > 10:
                noise_rms = np.sqrt(np.mean(noise_window.astype(float) ** 2))
                signal_rms = np.sqrt(np.mean(signal_window.astype(float) ** 2))
                if noise_rms > 0:
                    result["snr_db"] = round(20 * np.log10(signal_rms / noise_rms), 2)

            # S-dalgası adayı: yatay bileşen enerjisinde P'den sonraki ikinci tetiklenme
            horizontals = [tr for tr in st if not tr.stats.channel.endswith("Z")]
            if len(horizontals) >= 2:
                n = min(len(horizontals[0].data), len(horizontals[1].data))
                energy = np.sqrt(
                    horizontals[0].data[:n].astype(float) ** 2 + horizontals[1].data[:n].astype(float) ** 2
                )
                cft_h = classic_sta_lta(energy, int(1 * sr), int(10 * sr))
                onsets_h = trigger_onset(cft_h, 3.5, 0.5)
                after_p = [o for o in onsets_h if o[0] > p_idx + int(1 * sr)]
                if after_p:
                    s_idx = after_p[0][0]
                    result["s_pick_time"] = str(z_trace.stats.starttime + s_idx / sr)

    return result


def main():
    files = sorted(WAVEFORM_DIR.glob("*.mseed"))
    print(f"{len(files)} dalga formu dosyası bulundu.")

    already_done = set()
    if OUT_PATH.exists():
        import pandas as pd

        already_done = set(pd.read_csv(OUT_PATH)["file"])

    is_new = not OUT_PATH.exists()
    with open(OUT_PATH, "a", newline="") as f:
        writer = None
        for i, path in enumerate(files):
            if str(path) in already_done:
                continue
            try:
                features = compute_features(path)
            except Exception as e:
                print(f"[ATLANDI] {path.name}: {e}")
                continue
            if features is None:
                continue
            event_id, station_from_name = path.stem.rsplit("_", 1)
            row = dict(file=str(path), event_id=event_id, station=station_from_name, **features)
            if writer is None:
                writer = csv.DictWriter(f, fieldnames=list(row.keys()))
                if is_new:
                    writer.writeheader()
                    is_new = False
            writer.writerow(row)
            f.flush()
            if i % 25 == 0:
                print(f"[{i}/{len(files)}] işlendi")

    print(f"Tamamlandı -> {OUT_PATH}")


if __name__ == "__main__":
    main()
