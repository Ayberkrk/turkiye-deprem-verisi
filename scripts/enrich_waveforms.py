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

v3 notları: deprem mühendisliği için doğrudan kullanılabilecek ek
öznitelikler eklendi:
- sa_g_0_1s / 0_2s / 0_5s / 1_0s / 2_0s: %5 sönümlü tek serbestlik
  dereceli (SDOF) sistem için sözde-ivme tepki spektrumu (pseudo-spectral
  acceleration), Newmark-beta (ortalama ivme, beta=1/4, gamma=1/2)
  yöntemiyle sayısal integrasyonla hesaplanıyor (bkz. `sdof_displacement_history`
  docstring'i: bu varyant koşulsuz kararlı olduğu için istasyonlar arası
  değişen örnekleme hızlarında güvenli).
- arias_intensity_ms, cav_ms: Arias şiddeti ve kümülatif mutlak hız,
  ivme kaydının tamamı üzerinden.
- duration_5_95_sec: Arias şiddetinin %5'inden %95'ine ulaşma süresi
  (anlamlı sarsıntı süresi, significant duration).
- fas_dominant_freq_hz, fas_mean_freq_hz: Fourier genlik spektrumunun
  tepe frekansı ve genlik-ağırlıklı ortalama frekansı.
Bu değerler yalnızca güçlü hareket/broadband ivme kaydı elde edilebildiği
(response_removed_ok=True) durumlarda hesaplanıyor.

v4 notları: yatay bileşen tanımları eklendi. `pga_g`/`sa_g_*` düşey
bileşen dahil tek bir (en büyük genlikli) bileşenden geliyor; oysa
GMPE'ler yatay harekete göre kalibre edilir ve bu değerlerle doğrudan
kıyaslanamaz. Mevcut sütunlar geriye dönük uyumluluk için değişmedi,
yanlarına şunlar eklendi:
- pga_h1_g / pga_h2_g / pga_v_g: bileşen bazlı tepe ivme
  (`horizontal_channels` h1 ve h2'nin hangi kanallar olduğunu söyler).
- pga_geomean_g, pgv_geomean_cms: iki yatay tepe değerin geometrik
  ortalaması.
- pga_rotd50_g, pgv_rotd50_cms, sa_rotd50_g_*: yönelimden bağımsız
  RotD50 (Boore 2010) - sensörün kurulum açısına bağlı olmadığı için
  güncel GMPE'lerin (NGA-West2 vb.) kullandığı tanım.
İki yatay bileşen yoksa veya zaman pencereleri örtüşmüyorsa bu alanlar
boş kalır.

v5 notları: tepki çıkarımından sonra ivme ve hız kayıtlarına sıfır fazlı
bir yüksek geçiren (high-pass) Butterworth filtre uygulanıyor. Filtresiz
halde zayıf kayıtlarda PGV, sinyalin değil düşük frekanslı gürültünün
(integrasyonla büyüyen) tepe değerini veriyordu: 40 kayıtlık bir
örneklemde en zayıf PGA çeyreğinde filtresiz PGV filtrelinin medyanda
~1,7 katıydı; PGA ve Sa ise %1'den az değişiyor. Köşe frekansı sabit
değil: büyük depremlerin gerçek uzun periyotlu içeriği kesilmesin diye
kayıt penceresine düşen en büyük katalog depreminin büyüklüğüne göre
seçiliyor (bkz. `highpass_corner_hz`). Kullanılan değerler
`highpass_corner_hz` ve `window_max_magnitude` sütunlarında.

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
from scipy.signal import lfilter

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
    "sa_g_0_1s", "sa_g_0_2s", "sa_g_0_5s", "sa_g_1_0s", "sa_g_2_0s",
    "arias_intensity_ms", "cav_ms", "duration_5_95_sec",
    "fas_dominant_freq_hz", "fas_mean_freq_hz",
    "horizontal_channels", "pga_h1_g", "pga_h2_g", "pga_v_g",
    "pga_geomean_g", "pga_rotd50_g", "pgv_geomean_cms", "pgv_rotd50_cms",
    "sa_rotd50_g_0_1s", "sa_rotd50_g_0_2s", "sa_rotd50_g_0_5s",
    "sa_rotd50_g_1_0s", "sa_rotd50_g_2_0s",
    "highpass_corner_hz", "window_max_magnitude",
]

SA_PERIODS_SEC = [0.1, 0.2, 0.5, 1.0, 2.0]
SA_DAMPING_RATIO = 0.05


SA_COLUMN_SUFFIXES = ["0_1s", "0_2s", "0_5s", "1_0s", "2_0s"]

# Kayıt penceresinden önce olmuş bir depremin kodası pencereye
# taşabildiği için, pencere başından bu kadar geriye de bakılıyor.
WINDOW_LOOKBACK_SEC = 120
DEFAULT_HIGHPASS_HZ = 0.05
HIGHPASS_CORNERS = 4


def highpass_corner_hz(magnitude) -> float:
    """Büyüklüğe göre yüksek geçiren filtre köşe frekansı (Hz).

    Kaynağın köşe frekansı büyüklükle düşer (M5 civarında ~1 Hz, M7.5+
    için ~0.03 Hz mertebesinde); filtre köşesi bunun altında kalmalı ki
    gerçek sinyal kesilmesin, ama gereğinden düşük seçilirse zayıf
    kayıtlarda gürültü hız integraline sızıyor. Gerçek veride ölçülen:
    0.1 Hz, M<5.5 kayıtlarda PGV'yi yakınsatıyor ama M7.5+ yakın alan
    kayıtlarında PGV'nin ~%40'ını kesiyor; 0.03 Hz'de bu kayıp ~%1.
    Büyüklük bilinmiyorsa ikisinin arası bir varsayılan kullanılıyor."""
    if magnitude is None or np.isnan(magnitude):
        return DEFAULT_HIGHPASS_HZ
    if magnitude >= 6.5:
        return 0.03
    if magnitude >= 5.5:
        return 0.05
    return 0.1


def window_max_magnitude(catalog_times_ns, catalog_magnitudes, window_start_ns, window_end_ns,
                         lookback_sec: float = WINDOW_LOOKBACK_SEC):
    """Kayıt penceresine (ve hemen öncesine) düşen en büyük katalog
    depreminin büyüklüğü; yoksa None. catalog_times_ns artan sıralı
    olmalı. Dosyanın etiketlendiği olayın büyüklüğü yerine bu
    kullanılıyor, çünkü artçı dizilerinde küçük bir olayın penceresi çok
    daha büyük bir depremin sarsıntısını içerebiliyor."""
    lo = np.searchsorted(catalog_times_ns, window_start_ns - int(lookback_sec * 1e9), side="left")
    hi = np.searchsorted(catalog_times_ns, window_end_ns, side="right")
    if hi <= lo:
        return None
    return float(np.max(catalog_magnitudes[lo:hi]))


def load_catalog_times_and_magnitudes():
    """Pencere büyüklüğü araması için (zaman, büyüklük) dizileri; katalog
    henüz üretilmemişse None (filtre varsayılan köşe frekansına düşer)."""
    import pandas as pd

    for name in ["turkiye_deprem_katalogu_genisletilmis.parquet", "usgs_catalog_turkey.parquet"]:
        path = PROCESSED / name
        if path.exists():
            cat = pd.read_parquet(path, columns=["time_utc", "magnitude"]).dropna()
            cat["time_utc"] = pd.to_datetime(cat["time_utc"], utc=True)
            cat = cat.sort_values("time_utc")
            times_ns = cat["time_utc"].dt.tz_convert(None).to_numpy("datetime64[ns]").astype("int64")
            return times_ns, cat["magnitude"].to_numpy(float)
    return None


def apply_highpass(stream, corner_hz: float):
    """Stream'e yerinde sıfır fazlı yüksek geçiren filtre uygular. Sıfır
    faz (ileri-geri) şart: tek yönlü filtre dalga biçimini kaydırıp tepe
    değerleri ve faz varış zamanlarını bozar."""
    stream.detrend("demean")
    stream.taper(max_percentage=0.05)
    stream.filter("highpass", freq=corner_hz, corners=HIGHPASS_CORNERS, zerophase=True)
    return stream
ROTD_ANGLES_RAD = np.deg2rad(np.arange(0, 180))


def sdof_displacement_history(accel: np.ndarray, dt: float, period_sec: float,
                              damping: float = SA_DAMPING_RATIO) -> np.ndarray:
    """%5 sönümlü bir SDOF sistemin göreli yer değiştirme geçmişini
    Newmark-beta yöntemiyle hesaplar. Ortalama ivme varyantı (beta=1/4,
    gamma=1/2) kullanılıyor; bu varyant her dt/T oranında koşulsuz
    kararlıdır (istasyonlar arası örnekleme hızı 20-100Hz arasında
    değiştiği için bu önemli). Referans: Chopra, "Dynamics of
    Structures", Newmark's Method (doğrusal sistemler).

    Doğrusal sistemde ortalama ivme yöntemi, her adımda dengeyi sağlayan
    yamuk kuralına özdeştir; [u, v] durumu için
        x[i+1] = A x[i] + B (p[i] + p[i+1])
    doğrusal özyinelemesini verir. Bu özyineleme örnek örnek Python
    döngüsü yerine eşdeğer ikinci derece IIR filtresi olarak
    çalıştırılıyor (aynı cebir, u0=v0=0 başlangıcı dahil; ~100 kat
    hızlı, bu da RotD50 için iki bileşenin ayrı ayrı çözülmesini
    mümkün kılıyor)."""
    wn = 2 * np.pi / period_sec
    k, c = wn ** 2, 2 * damping * wn
    h = dt / 2
    p = -np.asarray(accel, dtype=float)  # etkin yük: taban ivmesinden kaynaklanan atalet kuvveti

    lhs = np.array([[1.0, -h], [h * k, 1.0 + h * c]])
    rhs = np.array([[1.0, h], [-h * k, 1.0 - h * c]])
    A = np.linalg.solve(lhs, rhs)
    B = np.linalg.solve(lhs, np.array([0.0, h]))

    # u = [1, 0] x için transfer fonksiyonu; pay katsayılarındaki baştaki
    # sıfır, x[i+1]'in q[i]'ye bağlı olmasından gelen bir örneklik gecikme.
    b = [0.0, B[0], A[0, 1] * B[1] - A[1, 1] * B[0]]
    a = [1.0, -(A[0, 0] + A[1, 1]), A[0, 0] * A[1, 1] - A[0, 1] * A[1, 0]]
    q = np.append(p[:-1] + p[1:], 0.0)
    return lfilter(b, a, q)


def newmark_sdof_psa(accel: np.ndarray, dt: float, period_sec: float, damping: float = SA_DAMPING_RATIO) -> float:
    """Verilen periyottaki sözde-ivme tepki değeri (pseudo-spectral
    acceleration): PSA = wn^2 * max(|göreli yer değiştirme|). accel
    birimi ne ise (burada m/s^2) dönüş değeri de o birimdedir."""
    wn = 2 * np.pi / period_sec
    u = sdof_displacement_history(accel, dt, period_sec, damping)
    return wn ** 2 * float(np.max(np.abs(u))) if len(u) else 0.0


def rotd50(h1: np.ndarray, h2: np.ndarray) -> float:
    """İki dik yatay bileşenin yönelimden bağımsız RotD50 değeri (Boore
    2010): hareket 0-179 derece arasındaki her açıya döndürülür, her
    açıdaki tepe mutlak değer alınır, bunların medyanı döndürülür.
    Sensörün kurulum açısından bağımsızdır; tek bileşenin tepe değeri
    ise aynı hareket için sensör nasıl döndürüldüyse ona göre değişir."""
    peaks = [np.max(np.abs(h1 * np.cos(t) + h2 * np.sin(t))) for t in ROTD_ANGLES_RAD]
    return float(np.median(peaks))


def aligned_horizontals(stream):
    """Stream'deki iki yatay bileşeni ortak zaman penceresine kırpılmış
    (channel1, channel2, data1, data2, dt) olarak döndürür; tam iki
    yatay bileşen yoksa, örnekleme hızları farklıysa veya pencereler
    örtüşmüyorsa None. Döndürme (RotD) iki bileşenin örnek örnek aynı
    ana karşılık gelmesini gerektirdiği için hizalama şart."""
    horizontals = sorted(
        (tr for tr in stream if not tr.stats.channel.endswith("Z")), key=lambda tr: tr.stats.channel
    )
    if len(horizontals) != 2:
        return None
    tr1, tr2 = horizontals
    if tr1.stats.sampling_rate != tr2.stats.sampling_rate:
        return None
    start = max(tr1.stats.starttime, tr2.stats.starttime)
    end = min(tr1.stats.endtime, tr2.stats.endtime)
    if end <= start:
        return None
    d1 = tr1.slice(start, end).data.astype(float)
    d2 = tr2.slice(start, end).data.astype(float)
    n = min(len(d1), len(d2))
    if n < 2:
        return None
    return tr1.stats.channel, tr2.stats.channel, d1[:n], d2[:n], 1.0 / tr1.stats.sampling_rate


def horizontal_peak_measures(stream) -> dict:
    """Bileşen bazlı tepe değerler (h1, h2, v), yatay geometrik ortalama
    ve RotD50; stream'in biriminde. Hesaplanamayan alanlar None."""
    out = dict(channels=None, h1=None, h2=None, v=None, geomean=None, rotd50=None)
    verticals = [tr for tr in stream if tr.stats.channel.endswith("Z")]
    if len(verticals) == 1:
        out["v"] = float(np.max(np.abs(verticals[0].data)))

    horizontals = sorted(
        (tr for tr in stream if not tr.stats.channel.endswith("Z")), key=lambda tr: tr.stats.channel
    )
    if len(horizontals) != 2:
        return out
    out["channels"] = ",".join(tr.stats.channel for tr in horizontals)
    out["h1"], out["h2"] = (float(np.max(np.abs(tr.data))) for tr in horizontals)
    out["geomean"] = float(np.sqrt(out["h1"] * out["h2"]))

    pair = aligned_horizontals(stream)
    if pair is not None:
        out["rotd50"] = rotd50(pair[2], pair[3])
    return out


def sa_rotd50(h1: np.ndarray, h2: np.ndarray, dt: float, period_sec: float,
              damping: float = SA_DAMPING_RATIO) -> float:
    """RotD50 sözde-ivme tepki değeri. SDOF sistem doğrusal olduğu için
    döndürülmüş ivmenin tepkisi, iki bileşenin tepkilerinin aynı açıyla
    döndürülmüş haline eşittir; bu yüzden 180 açı için 180 değil, sadece
    2 integrasyon yeterli."""
    wn = 2 * np.pi / period_sec
    u1 = sdof_displacement_history(h1, dt, period_sec, damping)
    u2 = sdof_displacement_history(h2, dt, period_sec, damping)
    return wn ** 2 * rotd50(u1, u2)


def arias_and_cav(accel_ms2: np.ndarray, dt: float):
    """Arias şiddeti (m/s), kümülatif mutlak hız (CAV, m/s) ve %5-%95
    anlamlı sarsıntı süresini (saniye) tek geçişte hesaplar."""
    g = 9.81
    cumulative_energy = np.cumsum(accel_ms2 ** 2) * dt
    arias = (np.pi / (2 * g)) * cumulative_energy[-1]
    cav = float(np.sum(np.abs(accel_ms2)) * dt)

    total = cumulative_energy[-1]
    duration_5_95 = None
    if total > 0:
        frac = cumulative_energy / total
        idx_5 = np.searchsorted(frac, 0.05)
        idx_95 = np.searchsorted(frac, 0.95)
        duration_5_95 = round((idx_95 - idx_5) * dt, 3)

    return round(float(arias), 6), round(cav, 4), duration_5_95


def fourier_spectrum_summary(accel_ms2: np.ndarray, dt: float):
    """Fourier genlik spektrumunun tepe frekansı ve genlik-ağırlıklı
    ortalama frekansı (Hz). Sinyal içeriğinin baskın olduğu frekans
    aralığını özetlemek için; tam spektrum diskte tutulmuyor, sadece bu
    iki özet değer saklanıyor (depolama alanından tasarruf için)."""
    n = len(accel_ms2)
    spectrum = np.abs(np.fft.rfft(accel_ms2 - np.mean(accel_ms2)))
    freqs = np.fft.rfftfreq(n, d=dt)
    if len(freqs) < 2 or spectrum.sum() == 0:
        return None, None
    dominant = float(freqs[np.argmax(spectrum)])
    mean_freq = float(np.sum(freqs * spectrum) / np.sum(spectrum))
    return round(dominant, 3), round(mean_freq, 3)


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


def compute_features(mseed_path: Path, catalog=None):
    """catalog: load_catalog_times_and_magnitudes() çıktısı; None ise
    filtre köşe frekansı varsayılan değere düşer."""
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
    # Boşluklu dosyalarda merge sonrası iz sırası çalıştırmadan çalıştırmaya
    # değişebiliyor; aşağıda "ilk iz"e bakan seçimler (channel_used, Z
    # bileşeni) her çalıştırmada aynı sonucu versin diye sıra sabitleniyor.
    st.sort(keys=["channel"])
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
        sa_g_0_1s=None, sa_g_0_2s=None, sa_g_0_5s=None, sa_g_1_0s=None, sa_g_2_0s=None,
        arias_intensity_ms=None, cav_ms=None, duration_5_95_sec=None,
        fas_dominant_freq_hz=None, fas_mean_freq_hz=None,
        horizontal_channels=None, pga_h1_g=None, pga_h2_g=None, pga_v_g=None,
        pga_geomean_g=None, pga_rotd50_g=None, pgv_geomean_cms=None, pgv_rotd50_cms=None,
        sa_rotd50_g_0_1s=None, sa_rotd50_g_0_2s=None, sa_rotd50_g_0_5s=None,
        sa_rotd50_g_1_0s=None, sa_rotd50_g_2_0s=None,
        highpass_corner_hz=None, window_max_magnitude=None,
    )

    window_mag = None
    if catalog is not None and len(st):
        window_mag = window_max_magnitude(
            catalog[0], catalog[1],
            min(tr.stats.starttime for tr in st).ns, max(tr.stats.endtime for tr in st).ns,
        )
    corner_hz = highpass_corner_hz(window_mag)
    result["highpass_corner_hz"] = corner_hz
    result["window_max_magnitude"] = window_mag

    response_removed_ok = False
    if response_available and len(pga_stream):
        try:
            st_acc = pga_stream.copy()
            st_acc.remove_response(inventory=inv, output="ACC", water_level=60)
            apply_highpass(st_acc, corner_hz)
            pga_ms2 = max(np.max(np.abs(tr.data)) for tr in st_acc)
            result["pga_g"] = round(pga_ms2 / 9.81, 5)
            response_removed_ok = True

            # Mühendislik öznitelikleri: en büyük genliğe sahip bileşen
            # (genelde PGA'yı veren bileşenle aynı) üzerinden hesaplanır.
            try:
                dominant_tr = max(st_acc, key=lambda tr: np.max(np.abs(tr.data)))
                acc_data = dominant_tr.data.astype(float)
                dt = 1.0 / dominant_tr.stats.sampling_rate
                if len(acc_data) > 20:
                    sa_values = [newmark_sdof_psa(acc_data, dt, T) for T in SA_PERIODS_SEC]
                    result["sa_g_0_1s"] = round(sa_values[0] / 9.81, 5)
                    result["sa_g_0_2s"] = round(sa_values[1] / 9.81, 5)
                    result["sa_g_0_5s"] = round(sa_values[2] / 9.81, 5)
                    result["sa_g_1_0s"] = round(sa_values[3] / 9.81, 5)
                    result["sa_g_2_0s"] = round(sa_values[4] / 9.81, 5)

                    arias, cav, dur_5_95 = arias_and_cav(acc_data, dt)
                    result["arias_intensity_ms"] = arias
                    result["cav_ms"] = cav
                    result["duration_5_95_sec"] = dur_5_95

                    dom_freq, mean_freq = fourier_spectrum_summary(acc_data, dt)
                    result["fas_dominant_freq_hz"] = dom_freq
                    result["fas_mean_freq_hz"] = mean_freq
            except Exception:
                pass

            try:
                acc_h = horizontal_peak_measures(st_acc)
                result["horizontal_channels"] = acc_h["channels"]
                for key, col in [("h1", "pga_h1_g"), ("h2", "pga_h2_g"), ("v", "pga_v_g"),
                                 ("geomean", "pga_geomean_g"), ("rotd50", "pga_rotd50_g")]:
                    if acc_h[key] is not None:
                        result[col] = round(acc_h[key] / 9.81, 5)

                pair = aligned_horizontals(st_acc)
                if pair is not None and len(pair[2]) > 20:
                    _, _, h1, h2, dt_h = pair
                    for T, suffix in zip(SA_PERIODS_SEC, SA_COLUMN_SUFFIXES):
                        result[f"sa_rotd50_g_{suffix}"] = round(sa_rotd50(h1, h2, dt_h, T) / 9.81, 5)
            except Exception:
                pass
        except Exception:
            pass

        try:
            st_vel = pga_stream.copy()
            st_vel.remove_response(inventory=inv, output="VEL", water_level=60)
            apply_highpass(st_vel, corner_hz)
            pgv_ms = max(np.max(np.abs(tr.data)) for tr in st_vel)
            result["pgv_cms"] = round(pgv_ms * 100, 4)

            vel_h = horizontal_peak_measures(st_vel)
            if vel_h["geomean"] is not None:
                result["pgv_geomean_cms"] = round(vel_h["geomean"] * 100, 4)
            if vel_h["rotd50"] is not None:
                result["pgv_rotd50_cms"] = round(vel_h["rotd50"] * 100, 4)
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

    catalog = load_catalog_times_and_magnitudes()
    if catalog is None:
        print("[UYARI] Katalog bulunamadı; yüksek geçiren filtre tüm kayıtlarda "
              f"varsayılan {DEFAULT_HIGHPASS_HZ} Hz köşe frekansıyla uygulanacak.")

    is_new = not OUT_PATH.exists()
    with open(OUT_PATH, "a", newline="") as f:
        writer = None
        for i, path in enumerate(files):
            if str(path) in already_done:
                continue
            try:
                features = compute_features(path, catalog)
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
