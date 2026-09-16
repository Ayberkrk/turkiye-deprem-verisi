"""
Coğrafi mesafe hesapları. Önceden build_dataset.py, build_event_station_table.py,
expand_catalog.py, fetch_waveforms_bulk.py ve validate_dataset.py'de ayrı ayrı
kopyalanmış olan haversine_km burada tek, test edilen bir yerde toplanıyor.
"""
import numpy as np


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))
