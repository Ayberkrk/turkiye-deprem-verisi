"""
Kayıt pencerelerinin birbirleriyle ve başka depremlerle ilişkisi.

Her dalga formu, olayın origin zamanından 10 sn önce başlayıp 200 sn
sonra biten sabit bir pencere (bkz. fetch_waveforms_bulk.py). Yoğun
artçı dizilerinde art arda gelen olayların pencereleri aynı örnekleri
paylaşıyor. Bunun iki sonucu var:

1. Sızıntı: pencereleri örtüşen iki olay farklı bölmelere düşerse model
   test kaydının bir kısmını eğitimde görmüş olur. Olay bazlı bölme bunu
   önlemez; bu yüzden örtüşen olaylar tek bir grup olarak bölünür.
2. Etiket belirsizliği: pencerede en az kendisi kadar büyük başka bir
   deprem varsa, ölçülen tepe değerin hangi olaya ait olduğu belirsizdir.
"""
import numpy as np
import pandas as pd

RECORD_WINDOW_SEC = 210  # fetch_waveforms_bulk.py: 10 sn önce + 200 sn sonra
WINDOW_BEFORE_SEC = 10
WINDOW_AFTER_SEC = 200
# Pencereden önce olmuş bir depremin kodası pencereye taşabildiği için
# geriye de bakılıyor (enrich_waveforms.py'deki WINDOW_LOOKBACK_SEC ile aynı).
LOOKBACK_SEC = 120


def assign_window_groups(event_times: pd.Series, window_sec: float = RECORD_WINDOW_SEC) -> pd.Series:
    """event_id -> grup anahtarı. Origin zamanları arasındaki fark
    window_sec'i aşmayan ardışık olaylar zincirlenerek aynı gruba girer;
    grup anahtarı zincirdeki ilk olayın kimliğidir. Tek başına kalan bir
    olayın anahtarı kendi kimliği olduğundan, örtüşmesi olmayan olayların
    bölmesi event_id bazlı bölmeyle aynı kalır.

    event_times: index'i event_id, değeri origin zamanı olan Series."""
    ordered = event_times.sort_values(kind="stable")
    gaps = ordered.diff().dt.total_seconds()
    starts_new_group = gaps.isna() | (gaps > window_sec)
    first_ids = pd.Series(np.where(starts_new_group, ordered.index, None), index=ordered.index).ffill()
    return first_ids.rename("window_group").reindex(event_times.index)


def largest_other_event_magnitude(catalog_ids, catalog_times_ns, catalog_magnitudes, event_id, origin_ns,
                                  lookback_sec: float = WINDOW_BEFORE_SEC + LOOKBACK_SEC,
                                  after_sec: float = WINDOW_AFTER_SEC) -> float:
    """Olayın kayıt penceresine (ve hemen öncesine) düşen, KENDİSİ DIŞINDAKİ
    en büyük katalog depreminin büyüklüğü; yoksa NaN. catalog_times_ns
    artan sıralı olmalı. Katalogdaki tüm olaylar (dalga formu indirilmemiş
    küçükler dahil) dikkate alınır."""
    lo = np.searchsorted(catalog_times_ns, origin_ns - int(lookback_sec * 1e9), side="left")
    hi = np.searchsorted(catalog_times_ns, origin_ns + int(after_sec * 1e9), side="right")
    others = [catalog_magnitudes[j] for j in range(lo, hi) if catalog_ids[j] != event_id]
    return float(max(others)) if others else float("nan")


def add_window_context(table: pd.DataFrame, catalog: pd.DataFrame) -> pd.DataFrame:
    """Olay-istasyon tablosuna pencere bağlamı sütunlarını ekler:
    - window_group: pencereleri örtüşen olayların ortak grup anahtarı
    - window_other_max_magnitude: penceredeki en büyük başka deprem
    - label_ambiguous: o deprem en az bu olay kadar büyükse True

    catalog: event_id, time_utc, magnitude sütunlu tüm katalog."""
    table = table.copy()
    times = pd.to_datetime(table["time_utc"], utc=True, format="ISO8601")
    event_times = pd.Series(times.values, index=table["event_id"].values)
    event_times = event_times[~event_times.index.duplicated()]
    groups = assign_window_groups(event_times)

    cat = catalog.dropna(subset=["time_utc", "magnitude"]).copy()
    cat["time_utc"] = pd.to_datetime(cat["time_utc"], utc=True)
    cat = cat.sort_values("time_utc")
    cat_ids = cat["event_id"].to_numpy()
    cat_times = cat["time_utc"].dt.tz_convert(None).to_numpy("datetime64[ns]").astype("int64")
    cat_mags = cat["magnitude"].to_numpy(float)
    other = {
        event_id: largest_other_event_magnitude(cat_ids, cat_times, cat_mags, event_id, origin.value)
        for event_id, origin in event_times.items()
    }

    table["window_group"] = table["event_id"].map(groups)
    table["window_other_max_magnitude"] = table["event_id"].map(other)
    table["label_ambiguous"] = table["window_other_max_magnitude"] >= table["magnitude"]
    return table
