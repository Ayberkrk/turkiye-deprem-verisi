"""
scripts/compare_picks_to_isc.py'deki özetleme mantığı için birim test:
sentetik (bilinen hatalı) pick çiftleriyle ortalama/medyan hata ve
güven-skoru bölmesinin doğru hesaplandığını doğruluyor.
"""
import pandas as pd

from compare_picks_to_isc import summarize


def test_summarize_computes_known_errors():
    merged = pd.DataFrame([
        dict(abs_error_sec=1.0, confidence=0.9),
        dict(abs_error_sec=3.0, confidence=0.1),
    ])
    summary = summarize(merged, "P")

    assert summary["n_matched"] == 2
    assert summary["mean_abs_error_sec"] == 2.0
    assert summary["median_abs_error_sec"] == 2.0
    assert summary["fraction_over_1s"] == 0.5


def test_summarize_confidence_split_uses_median_not_fixed_threshold():
    # Tüm güven skorları 0.7'nin altında kalsa bile (gerçek veri setinde
    # de böyle, bkz. modül docstring'i), medyan bazlı bölme her zaman
    # her iki grubu da dolu bırakmalı.
    merged = pd.DataFrame([
        dict(abs_error_sec=1.0, confidence=0.5),
        dict(abs_error_sec=2.0, confidence=0.4),
        dict(abs_error_sec=10.0, confidence=0.1),
        dict(abs_error_sec=20.0, confidence=0.05),
    ])
    summary = summarize(merged, "S")

    assert summary["n_high_confidence"] > 0
    assert summary["n_low_confidence"] > 0
    assert summary["mean_abs_error_high_confidence"] < summary["mean_abs_error_low_confidence"]
