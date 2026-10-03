"""
Yayınlanmış yer hareketi tahmin denklemleri (GMPE). Veri setindeki
gözlemleri, bu veriyle kalibre edilmemiş bağımsız bir modelle kıyaslamak
için (bkz. notebooks/07_gmpe_comparison.py).

Akkar, Sandıkkaya ve Bommer (2014), "Empirical ground-motion models for
point- and extended-source crustal earthquakes in Europe and the Middle
East", Bulletin of Earthquake Engineering 12(1):359-387. Türkiye
kayıtlarının ağırlıkta olduğu RESORCE veri tabanından türetildi; nokta
kaynak mesafeleri (episantral, hiposantral) için ayrı katsayı setleri
verdiği için, sonlu fay geometrisi bulunmayan bu veri setine doğrudan
uygulanabiliyor. Geçerlilik aralığı: Mw 4-8, mesafe <= 200 km, Vs30
150-1200 m/s; yatay bileşenlerin geometrik ortalaması.

Katsayılar makaledeki Tablo 4'ten (PGA satırı). Uygulama, OpenQuake
Engine'in bu model için kullandığı doğrulama tablolarıyla
karşılaştırılarak test ediliyor (tests/test_gmpe.py).
"""
import numpy as np

# Mesafe tanımına göre değişen katsayılar (PGA).
_ASB14_BY_DISTANCE = {
    "rhypo": dict(a1=3.26685, a3=-0.04846, a4=-1.47905),
    "repi": dict(a1=2.52977, a3=-0.05496, a4=-1.31001),
}
# Mesafe tanımından bağımsız katsayılar (PGA).
_ASB14_COMMON = dict(a2=0.0029, a5=0.2529, a6=7.5, a7=-0.5096, a8=-0.1091, a9=0.0937,
                     b1=-0.41997, b2=-0.28846, c=2.5, n=3.2)
_ASB14_C1 = 6.75       # büyüklük ölçeklemesinin eğim değiştirdiği menteşe
_ASB14_VREF = 750.0    # referans kaya Vs30 (m/s)
_ASB14_VCON = 1000.0   # bunun üzerinde zemin büyütmesi sabit
# Olaylar arası (tau) ve olay içi (phi) standart sapma, ln birimi.
ASB14_SIGMA_LN = {"rhypo": (0.3472, 0.6475), "repi": (0.3581, 0.6375)}


def akkar2014_pga_g(magnitude, distance_km, vs30_ms, distance_type: str = "rhypo",
                    normal_fault=False, reverse_fault=False):
    """Medyan PGA (g). magnitude moment büyüklüğü (Mw) olmalı.
    distance_type: "rhypo" (hiposantral) veya "repi" (episantral).
    Faylanma tipi verilmezse doğrultu atımlı kabul edilir."""
    c = {**_ASB14_COMMON, **_ASB14_BY_DISTANCE[distance_type]}
    magnitude = np.asarray(magnitude, dtype=float)
    distance_km = np.asarray(distance_km, dtype=float)
    vs30_ms = np.asarray(vs30_ms, dtype=float)

    magnitude_slope = np.where(magnitude <= _ASB14_C1, c["a2"], c["a7"])
    ln_ref = (
        c["a1"]
        + magnitude_slope * (magnitude - _ASB14_C1)
        + c["a3"] * (8.5 - magnitude) ** 2
        + (c["a4"] + c["a5"] * (magnitude - _ASB14_C1)) * np.log(np.sqrt(distance_km ** 2 + c["a6"] ** 2))
        + c["a8"] * np.asarray(normal_fault, dtype=float)
        + c["a9"] * np.asarray(reverse_fault, dtype=float)
    )

    # Zemin büyütmesi: doğrusal Vs30 terimi + yumuşak zeminde, kayadaki
    # PGA büyüdükçe büyütmeyi azaltan doğrusal olmayan terim.
    pga_ref = np.exp(ln_ref)
    v = np.minimum(vs30_ms, _ASB14_VCON) / _ASB14_VREF
    ln_site = c["b1"] * np.log(v)
    nonlinear = c["b2"] * np.log((pga_ref + c["c"] * v ** c["n"]) / ((pga_ref + c["c"]) * v ** c["n"]))
    ln_site = ln_site + np.where(vs30_ms < _ASB14_VREF, nonlinear, 0.0)

    return np.exp(ln_ref + ln_site)
