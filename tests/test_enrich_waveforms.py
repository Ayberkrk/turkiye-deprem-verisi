"""
scripts/enrich_waveforms.py'deki sayısal integrasyon ve mühendislik
metrikleri, kapalı-form (analitik) çözümlerle karşılaştırılarak
doğrulanıyor. v5 CHANGELOG'unda belirtilen "Newmark-beta katsayılarında
bir hata... rezonans testiyle doğrulandı" notunun kalıcı bir regresyon
testi hali.
"""
import numpy as np
import pytest
from obspy import Stream, Trace, UTCDateTime

from enrich_waveforms import (
    DEFAULT_HIGHPASS_HZ,
    aligned_horizontals,
    apply_highpass,
    arias_and_cav,
    highpass_corner_hz,
    horizontal_peak_measures,
    newmark_sdof_psa,
    rotd50,
    sa_rotd50,
    sdof_displacement_history,
    window_max_magnitude,
)


def test_newmark_psa_matches_resonance_analytical_solution():
    # Rezonansta (uyarım frekansı = doğal frekans), hafif sönümlü bir
    # SDOF sistemin kararlı-durum tepki genliği analitik olarak
    # PSA = a0 / (2*damping) formülüyle veriliyor (Chopra, Dynamics of
    # Structures). Kararlı duruma yaklaşmak için sönüm süresinin
    # (~1/(damping*wn)) birçok katı kadar sinyal veriyoruz.
    period_sec = 1.0
    damping = 0.05
    wn = 2 * np.pi / period_sec
    dt = 0.001
    duration = 40.0
    t = np.arange(0, duration, dt)
    a0 = 1.0
    accel = a0 * np.sin(wn * t)

    psa = newmark_sdof_psa(accel, dt, period_sec, damping)
    expected = a0 / (2 * damping)
    assert psa == pytest.approx(expected, rel=0.01)


def test_newmark_psa_zero_input_gives_zero_response():
    accel = np.zeros(500)
    assert newmark_sdof_psa(accel, dt=0.01, period_sec=1.0) == pytest.approx(0.0, abs=1e-9)


def test_newmark_psa_short_period_stiffer_system_smaller_displacement():
    # Aynı ivme genliği için çok kısa periyotlu (çok rijit) bir sistem,
    # rezonanstan uzak olduğu için kararlı-durum genliği çok daha küçük
    # kalır.
    dt = 0.005
    t = np.arange(0, 20.0, dt)
    accel = np.sin(2 * np.pi / 1.0 * t)
    psa_at_resonance = newmark_sdof_psa(accel, dt, period_sec=1.0)
    psa_off_resonance = newmark_sdof_psa(accel, dt, period_sec=0.05)
    assert psa_off_resonance < psa_at_resonance


def test_arias_and_cav_match_constant_acceleration_analytical_solution():
    # Sabit a0 ivmesi, T süresince: Arias = pi/(2g) * a0^2 * T,
    # CAV = a0 * T (kapalı-form, integral tanımından doğrudan çıkar).
    a0, duration_sec, dt = 2.0, 5.0, 0.01
    accel = np.full(int(duration_sec / dt), a0)

    arias, cav, dur_5_95 = arias_and_cav(accel, dt)

    g = 9.81
    expected_arias = round(np.pi / (2 * g) * a0 ** 2 * duration_sec, 6)
    expected_cav = round(a0 * duration_sec, 4)
    assert arias == pytest.approx(expected_arias, rel=1e-4)
    assert cav == pytest.approx(expected_cav, rel=1e-4)
    # Sabit ivme altında enerji birikimi doğrusal olduğu için %5-%95
    # aralığı toplam sürenin %90'ına karşılık gelmeli.
    assert dur_5_95 == pytest.approx(0.9 * duration_sec, abs=dt * 2)


def test_arias_zero_signal_has_no_duration():
    arias, cav, dur_5_95 = arias_and_cav(np.zeros(1000), dt=0.01)
    assert arias == 0.0
    assert cav == 0.0
    assert dur_5_95 is None


def _newmark_loop_reference(accel, dt, period_sec, damping=0.05):
    # Vektörize edilmeden önceki, Chopra'daki artımsal formülasyonun
    # örnek örnek uygulaması. sdof_displacement_history'nin aynı cebiri
    # (u0=v0=0 başlangıcı ve sıfırdan farklı ilk örnek dahil) ürettiğini
    # kanıtlamak için burada referans olarak tutuluyor.
    wn = 2 * np.pi / period_sec
    k, m, c = wn ** 2, 1.0, 2 * damping * wn
    beta, gamma = 0.25, 0.5
    n = len(accel)
    p = -m * accel
    u, v, a = np.zeros(n), np.zeros(n), np.zeros(n)
    a[0] = p[0] / m
    k_hat = k + gamma * c / (beta * dt) + m / (beta * dt ** 2)
    coef_v = m / (beta * dt) + gamma * c / beta
    coef_a = m / (2 * beta) + dt * (gamma / (2 * beta) - 1) * c
    for i in range(n - 1):
        d_p = (p[i + 1] - p[i]) + coef_v * v[i] + coef_a * a[i]
        du = d_p / k_hat
        dv = gamma / (beta * dt) * du - gamma / beta * v[i] + dt * (1 - gamma / (2 * beta)) * a[i]
        da = du / (beta * dt ** 2) - v[i] / (beta * dt) - a[i] / (2 * beta)
        u[i + 1], v[i + 1], a[i + 1] = u[i] + du, v[i] + dv, a[i] + da
    return u


@pytest.mark.parametrize("dt", [0.01, 0.02, 0.05])
@pytest.mark.parametrize("period_sec", [0.1, 0.5, 2.0])
def test_displacement_history_matches_stepwise_newmark(dt, period_sec):
    rng = np.random.default_rng(0)
    accel = rng.normal(size=3000) + 0.7  # ilk örnek ve ortalama sıfır değil

    u = sdof_displacement_history(accel, dt, period_sec)
    expected = _newmark_loop_reference(accel, dt, period_sec)

    assert u.shape == expected.shape
    assert np.max(np.abs(u - expected)) <= 1e-9 * np.max(np.abs(expected))


def test_rotd50_of_linearly_polarized_motion_is_peak_over_sqrt2():
    # Tek bir doğrultuda (phi) salınan hareket theta açısına döndürülünce
    # tepe değeri A*|cos(theta-phi)| olur; theta 0-180 arasında düzgün
    # dağıldığında |cos|'un medyanı cos(45) = 1/sqrt(2).
    t = np.linspace(0, 10, 2001)
    signal = 3.0 * np.sin(2 * np.pi * 1.5 * t)
    phi = np.deg2rad(20.0)

    result = rotd50(signal * np.cos(phi), signal * np.sin(phi))

    assert result == pytest.approx(3.0 / np.sqrt(2), rel=0.02)


def test_rotd50_of_circularly_polarized_motion_equals_amplitude():
    # Dairesel harekette her yönde aynı tepe değer görülür.
    t = np.linspace(0, 10, 4001)
    h1, h2 = 2.0 * np.cos(2 * np.pi * t), 2.0 * np.sin(2 * np.pi * t)

    assert rotd50(h1, h2) == pytest.approx(2.0, rel=1e-3)


def test_rotd50_does_not_depend_on_sensor_orientation():
    rng = np.random.default_rng(1)
    h1, h2 = rng.normal(size=5000), 0.4 * rng.normal(size=5000)
    # 180 açının tam sayı katı kadar döndürme, aynı açı kümesini yeniden üretir.
    angle = np.deg2rad(37.0)
    r1 = h1 * np.cos(angle) + h2 * np.sin(angle)
    r2 = -h1 * np.sin(angle) + h2 * np.cos(angle)

    assert rotd50(r1, r2) == pytest.approx(rotd50(h1, h2), rel=1e-12)
    # Tek bileşenin tepe değeri ise yönelime bağlıdır.
    assert np.max(np.abs(r1)) != pytest.approx(np.max(np.abs(h1)), rel=1e-3)


def test_sa_rotd50_of_linearly_polarized_motion_is_psa_over_sqrt2():
    dt = 0.01
    t = np.arange(0, 20.0, dt)
    signal = np.sin(2 * np.pi * t) * np.exp(-0.1 * t)
    phi = np.deg2rad(60.0)

    result = sa_rotd50(signal * np.cos(phi), signal * np.sin(phi), dt, period_sec=0.5)

    assert result == pytest.approx(newmark_sdof_psa(signal, dt, 0.5) / np.sqrt(2), rel=0.02)


def _trace(channel, data, starttime=0.0, sampling_rate=100.0):
    return Trace(
        data=np.asarray(data, dtype=float),
        header=dict(network="KO", station="TEST", channel=channel,
                    sampling_rate=sampling_rate, starttime=UTCDateTime(starttime)),
    )


def test_horizontal_peak_measures_reports_components_geomean_and_vertical():
    stream = Stream([
        _trace("HNE", [0.0, 4.0, -1.0, 0.0]),
        _trace("HNN", [0.0, 0.0, -9.0, 0.0]),
        _trace("HNZ", [0.0, 2.0, 0.0, 0.0]),
    ])

    measures = horizontal_peak_measures(stream)

    assert measures["channels"] == "HNE,HNN"
    assert (measures["h1"], measures["h2"], measures["v"]) == (4.0, 9.0, 2.0)
    assert measures["geomean"] == pytest.approx(6.0)
    assert measures["h1"] <= measures["rotd50"] * np.sqrt(2) + 1e-9
    assert measures["rotd50"] <= np.hypot(4.0, 9.0)


def test_horizontal_peak_measures_without_second_horizontal_gives_only_vertical():
    stream = Stream([_trace("BHE", [1.0, -3.0, 2.0]), _trace("BHZ", [0.5, 0.2, -0.1])])

    measures = horizontal_peak_measures(stream)

    assert measures["v"] == 0.5
    assert measures["h1"] is None and measures["geomean"] is None and measures["rotd50"] is None


def test_aligned_horizontals_trims_to_common_window():
    # N bileşeni 0.02s (2 örnek) geç başlıyor: döndürme öncesi iki
    # bileşen aynı ana hizalanmazsa farklı anların örnekleri karıştırılır.
    east = _trace("HNE", np.arange(10.0), starttime=0.0)
    north = _trace("HNN", 100 + np.arange(10.0), starttime=0.02)

    ch1, ch2, d1, d2, dt = aligned_horizontals(Stream([north, east]))

    assert (ch1, ch2) == ("HNE", "HNN")
    assert dt == pytest.approx(0.01)
    np.testing.assert_array_equal(d1, np.arange(2.0, 10.0))
    np.testing.assert_array_equal(d2, 100 + np.arange(8.0))


def test_aligned_horizontals_rejects_mismatched_sampling_or_no_overlap():
    east = _trace("HNE", np.arange(10.0))
    assert aligned_horizontals(Stream([east, _trace("HNN", np.arange(10.0), sampling_rate=50.0)])) is None
    assert aligned_horizontals(Stream([east, _trace("HNN", np.arange(10.0), starttime=60.0)])) is None
    assert aligned_horizontals(Stream([east])) is None


@pytest.mark.parametrize("magnitude, expected", [
    (4.5, 0.1), (5.49, 0.1), (5.5, 0.05), (6.49, 0.05), (6.5, 0.03), (7.8, 0.03),
    (None, DEFAULT_HIGHPASS_HZ), (float("nan"), DEFAULT_HIGHPASS_HZ),
])
def test_highpass_corner_decreases_with_magnitude(magnitude, expected):
    assert highpass_corner_hz(magnitude) == expected


def test_window_max_magnitude_uses_largest_event_in_window_and_lookback():
    sec = 10 ** 9
    times = np.array([0, 100, 400, 1000]) * sec
    mags = np.array([7.8, 4.6, 4.7, 6.0])

    # Pencere [150, 360]: 100. saniyedeki M4.6 geriye bakış payıyla (120s) dahil,
    # 0. saniyedeki M7.8 dışarıda, 400. saniyedeki M4.7 pencere bitiminden sonra.
    assert window_max_magnitude(times, mags, 150 * sec, 360 * sec) == 4.6
    # Pencere biraz erken başlarsa M7.8'in kodası pencereye taşabilir.
    assert window_max_magnitude(times, mags, 110 * sec, 320 * sec) == 7.8
    assert window_max_magnitude(times, mags, 390 * sec, 600 * sec) == 4.7
    assert window_max_magnitude(times, mags, 2000 * sec, 2210 * sec) is None


def test_highpass_removes_drift_but_keeps_signal_peak():
    # 2 Hz'lik sinyalin üstüne, köşe frekansının çok altında (0.005 Hz)
    # ve sinyalden 5 kat büyük bir sürüklenme bindirilmiş: filtresiz tepe
    # değer sürüklenmeyi ölçer, filtreli tepe değer sinyali.
    sr, duration = 100.0, 200.0
    t = np.arange(0, duration, 1 / sr)
    signal = np.sin(2 * np.pi * 2.0 * t) * np.exp(-((t - 100) / 15) ** 2)
    drift = 5.0 * np.sin(2 * np.pi * 0.005 * t)
    stream = Stream([_trace("HNE", signal + drift, sampling_rate=sr)])
    assert np.max(np.abs(stream[0].data)) > 4.0

    apply_highpass(stream, 0.1)

    assert np.max(np.abs(stream[0].data)) == pytest.approx(1.0, rel=0.02)


def test_highpass_is_zero_phase():
    sr = 100.0
    t = np.arange(0, 120.0, 1 / sr)
    pulse = np.exp(-((t - 60.0) / 0.2) ** 2) * np.sin(2 * np.pi * 3.0 * (t - 60.0))
    stream = Stream([_trace("HNE", pulse, sampling_rate=sr)])
    peak_before = np.argmax(np.abs(pulse))

    apply_highpass(stream, 0.1)

    assert np.argmax(np.abs(stream[0].data)) == peak_before
