"""
scripts/enrich_waveforms.py'deki sayısal integrasyon ve mühendislik
metrikleri, kapalı-form (analitik) çözümlerle karşılaştırılarak
doğrulanıyor. v5 CHANGELOG'unda belirtilen "Newmark-beta katsayılarında
bir hata... rezonans testiyle doğrulandı" notunun kalıcı bir regresyon
testi hali.
"""
import numpy as np
import pytest

from enrich_waveforms import arias_and_cav, newmark_sdof_psa


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
