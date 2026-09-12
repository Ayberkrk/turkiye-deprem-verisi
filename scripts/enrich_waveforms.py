"""
Her dalga formu dosyası için PGA, PGV, sinyal/gürültü oranı (SNR), P/S
faz okuması ve temel kalite kontrol (QC) metriklerini hesaplar.

v2 notları:
- Güçlü hareket (strong-motion, kanal kodu ikinci harfi "N") ve
  broadband/short-period (H/L/E) kayıtlar artık ayrı işleniyor. PGA/PGV
  öncelikle güçlü hareket bileşenlerinden hesaplanıyor; dosyada güçlü
  hareket kanalı yoksa broadband'den hesaplanıp bu açıkça `instrument_type_used`
  alanında işaretleniyor. Bunun nedeni: bir broadband sismometreden
  hesaplanan PGA, mühendislik tasarımı için güvenilir kabul edilmez, ama
  hâlâ kabaca "bu depremde bu istasyonda ne kadar sallandı" bilgisini
  taşıyabilir - bu yüzden atılmıyor, sadece etiketleniyor.
- Kalite kontrol (QC) alanları eklendi: gap/overlap oranı, clipping
  şüphesi, üç bileşenin var olup olmadığı, örnekleme hızı, süre, tepki
  çıkarımının başarılı olup olmadığı ve nihai bir `usable_for_engineering`
  / `usable_for_phase_picking` bayrağı. Amaç: dosyanın "okunabilir olması"
  ile "analiz için güvenilir olması" arasındaki farkı açık hale getirmek.

Yöntem notları (değişmedi):
- PGA/PGV, aletin ham sayım (count) çıktısından değil, cihaz tepkisi
  (instrument response) çıkarılmış gerçek fiziksel birimlerden hesaplanır.
  İstasyon tepki bilgisi KOERI'den istasyon bazında çekilip diskte
  önbelleğe alınır, böylece her dosya için tekrar ağ isteği yapılmaz.
- P-dalgası varışı, dikey (Z) bileşende klasik STA/LTA tetikleyicisiyle
  bulunur. S-dalgası için ayrı, güvenilir bir otomatik okuyucu
  uygulanmadı; onun yerine yatay bileşenlerdeki enerjinin P varışından
  sonraki en büyük ikinci tetiklenmesi kaba bir S adayı olarak işaretlenir.
  Bu bir sezgisel yöntemdir, yayın kalitesinde faz okuma değildir. Bu
  yüzden ayrıca bir `p_pick_confidence`/`s_pick_confidence` (STA/LTA tepe
  değerine dayalı, 0-1 arası kaba bir güven skoru) hesaplanıyor.
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

# Bu şema versiyonuyla üretilmemiş eski bir waveform_features.csv varsa
# (ör. QC/instrument_type_used sütunları eksikse) atlamak yerine yeniden
# üretmek gerekir; main() bunu kontrol eder.
EXPECTED_COLUMNS = [
    "file", "event_id", "station", "network", "location", "channel_used",
    "instrument_type_used", "pga_g", "pgv_cms", "snr_db", "p_pick_time",
    "s_pick_time", "p_pick_confidence", "s_pick_confidence",
    "sampling_rate_hz", "duration_sec", "num_gaps", "gap_fraction",
    "is_clipped", "has_three_components", "response_removed_ok",
    "usable_for_engineering", "usable_for_phase_picking", "qc_flags",
]


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


def desanitize_event_id(safe_id: str) -> str:
    """fetch_waveforms_bulk.py'deki sanitize_event_id'nin tersi. EMSC/ISC
    olay kimlikleri ":" ve "/" içerdiği için dosya adında güvenli bir
    biçime kodlanmıştı; dosya adından gerçek event_id'yi geri çıkarmak
    için burada tersine çeviriyoruz (kod çözme sırası kodlama sırasının
    tersi olmalı)."""
    return safe_id.replace("-e-", "=").replace("-s-", "/").replace("-c-", ":")


def _instrument_type_of(channel_code: str) -> str:
    if len(channel_code) < 2:
        return "bilinmiyor"
    second = channel_code[1]
    if second == "N":
        return "strong_motion"
    if second == "H":
        return "broadband"
    if second in ("L", "E"):
        return "short_period"
    return "bilinmiyor"


def _is_clipped(trace) -> bool:
    """Dijitizör doygunluğu (clipping) şüphesi: örneklerin çok büyük bir
    kısmı, sinyalin mutlak maksimumuna çok yakınsa (aynı tepe değerinde
    tekrar tekrar takılıp kalmışsa) muhtemelen kırpılmıştır."""
    data = trace.data.astype(float)
    if len(data) < 10:
        return False
    peak = np.max(np.abs(data))
    if peak == 0:
        return False
    near_peak = np.sum(np.abs(data) >= 0.999 * peak)
    return bool(near_peak > max(5, 0.01 * len(data)))


def compute_features(mseed_path: Path):
    st_raw = read(str(mseed_path))
    qc_flags = []

    # Gap/overlap kontrolü, merge'den ÖNCE yapılmalı; merge sonrasında
    # boşluklar interpolasyonla dolduruluyor ve iz kaybolabiliyor.
    gaps = st_raw.get_gaps()
    num_gaps = len(gaps)
    total_gap_sec = sum(abs(g[6]) for g in gaps) if gaps else 0.0
    span_sec = max((tr.stats.endtime - tr.stats.starttime) for tr in st_raw) if len(st_raw) else 0.0
    gap_fraction = round(total_gap_sec / span_sec, 4) if span_sec > 0 else 0.0
    if num_gaps > 0:
        qc_flags.append("has_gaps")

    st = st_raw.copy()
    st.merge(method=1, fill_value="interpolate")
    station = st[0].stats.station
    network = st[0].stats.network
    location = st[0].stats.location

    channel_codes = {tr.stats.channel for tr in st}
    instrument_types_present = {_instrument_type_of(c) for c in channel_codes}
    has_three_components = len({c[-1] for c in channel_codes}) >= 3
    if not has_three_components:
        qc_flags.append("eksik_bileşen")

    sampling_rates = {round(tr.stats.sampling_rate, 3) for tr in st}
    sampling_rate_hz = max(sampling_rates) if sampling_rates else None
    if len(sampling_rates) > 1:
        qc_flags.append("örnekleme_hızı_tutarsız")
    duration_sec = round(span_sec, 2)

    is_clipped = any(_is_clipped(tr) for tr in st)
    if is_clipped:
        qc_flags.append("clipping_şüphesi")

    try:
        inv = get_station_response(station)
        response_available = True
    except Exception:
        inv = None
        response_available = False
        qc_flags.append("tepki_bilgisi_yok")

    # Güçlü hareket kanalları varsa PGA/PGV öncelikle onlardan hesaplanır;
    # yoksa broadband/short-period kanallara düşülür ve bu açıkça işaretlenir.
    if "strong_motion" in instrument_types_present:
        instrument_type_used = "strong_motion"
        pga_stream = st.select(channel="HN*") if st.select(channel="HN*") else st
    elif "broadband" in instrument_types_present:
        instrument_type_used = "broadband"
        pga_stream = st.select(channel="HH*") if st.select(channel="HH*") else st
    elif instrument_types_present:
        instrument_type_used = sorted(instrument_types_present)[0]
        pga_stream = st
    else:
        instrument_type_used = "bilinmiyor"
        pga_stream = st

    channel_used = pga_stream[0].stats.channel if len(pga_stream) else None

    result = dict(
        network=network, location=location, channel_used=channel_used,
        instrument_type_used=instrument_type_used,
        pga_g=None, pgv_cms=None, snr_db=None, p_pick_time=None, s_pick_time=None,
        p_pick_confidence=None, s_pick_confidence=None,
        sampling_rate_hz=sampling_rate_hz, duration_sec=duration_sec,
        num_gaps=num_gaps, gap_fraction=gap_fraction, is_clipped=is_clipped,
        has_three_components=has_three_components, response_removed_ok=False,
    )

    response_removed_ok = False
    if response_available and len(pga_stream):
        try:
            st_acc = pga_stream.copy()
            st_acc.remove_response(inventory=inv, output="ACC", water_level=60)
            pga_ms2 = max(np.max(np.abs(tr.data)) for tr in st_acc)
            result["pga_g"] = round(pga_ms2 / 9.81, 5)
            response_removed_ok = True
        except Exception:
            pass

        try:
            st_vel = pga_stream.copy()
            st_vel.remove_response(inventory=inv, output="VEL", water_level=60)
            pgv_ms = max(np.max(np.abs(tr.data)) for tr in st_vel)
            result["pgv_cms"] = round(pgv_ms * 100, 4)
        except Exception:
            pass
    result["response_removed_ok"] = response_removed_ok
    if response_available and not response_removed_ok:
        qc_flags.append("tepki_çıkarımı_başarısız")

    # P-dalgası tespiti: dikey (Z) bileşende STA/LTA. Faz okuması, PGA
    # hesabında hangi kanal grubunun kullanıldığından bağımsız olarak
    # tüm bileşenler (st) üzerinden yapılır.
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
            # STA/LTA tepe değeri ne kadar yüksekse tetiklenme o kadar
            # belirgin demektir; 3.5-15 aralığını kabaca 0-1'e ölçekliyoruz.
            peak_val = float(np.max(cft[onsets[0][0]:onsets[0][1] + 1])) if onsets[0][1] > onsets[0][0] else float(cft[p_idx])
            result["p_pick_confidence"] = round(float(np.clip((peak_val - 3.5) / (15 - 3.5), 0, 1)), 3)

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
                    peak_val_h = float(np.max(cft_h[after_p[0][0]:after_p[0][1] + 1])) if after_p[0][1] > after_p[0][0] else float(cft_h[s_idx])
                    result["s_pick_confidence"] = round(float(np.clip((peak_val_h - 3.5) / (15 - 3.5), 0, 1)), 3)
    else:
        qc_flags.append("Z_bileşeni_yok_veya_kısa")

    # Nihai kullanılabilirlik bayrakları: kritik bir QC sorunu varsa
    # mühendislik/faz-okuma amaçlı "güvenilir" olarak işaretlenmiyor.
    engineering_blockers = {"clipping_şüphesi", "tepki_çıkarımı_başarısız", "tepki_bilgisi_yok", "has_gaps"}
    result["usable_for_engineering"] = (
        result["pga_g"] is not None
        and instrument_type_used == "strong_motion"
        and not (engineering_blockers & set(qc_flags))
    )
    phase_blockers = {"Z_bileşeni_yok_veya_kısa", "has_gaps"}
    result["usable_for_phase_picking"] = (
        result["p_pick_time"] is not None and not (phase_blockers & set(qc_flags))
    )
    result["qc_flags"] = ",".join(qc_flags) if qc_flags else ""

    return result


def main():
    files = sorted(WAVEFORM_DIR.glob("*.mseed"))
    print(f"{len(files)} dalga formu dosyası bulundu.")

    already_done = set()
    if OUT_PATH.exists():
        import pandas as pd

        existing = pd.read_csv(OUT_PATH, nrows=1)
        if list(existing.columns) != EXPECTED_COLUMNS:
            print("[BİLGİ] Mevcut waveform_features.csv eski şemada (QC alanları eksik), "
                  "yeniden oluşturuluyor.")
            OUT_PATH.unlink()
        else:
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
            safe_event_id, station_from_name = path.stem.rsplit("_", 1)
            event_id = desanitize_event_id(safe_event_id)
            row = dict(file=str(path), event_id=event_id, station=station_from_name, **features)
            if writer is None:
                writer = csv.DictWriter(f, fieldnames=EXPECTED_COLUMNS)
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
