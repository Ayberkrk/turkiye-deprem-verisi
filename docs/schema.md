# Veri Şeması

## `data/processed/turkiye_deprem_katalogu_genisletilmis.parquet`

USGS, EMSC ve ISC'nin FDSN olay servislerinden çekilip deduplike edilmiş
genişletilmiş katalog. `scripts/expand_catalog.py` tarafından üretilir.

| Kolon | Tip | Açıklama |
|---|---|---|
| source_event_id | string | Temsilci kaynağın kendi olay kimliği |
| time_utc | datetime (UTC) | Olay zamanı |
| magnitude | float | Büyüklük |
| mag_type | string | Büyüklük tipi (mb, ml, mw, md vb.) |
| longitude, latitude | float | Episantr koordinatı |
| depth_km | float | Odak derinliği (km) |
| source | string | Temsilci kaydın geldiği kurum (usgs/isc/emsc, öncelik bu sırayla) |
| reported_by | string | Bu depremi hangi kurumların da bildirdiği (virgülle ayrık) |
| magnitude_agreement_std | float | Birden fazla kurum bildirdiyse, bildirdikleri büyüklüklerin standart sapması. 0'a yakın değer kurumların hemfikir olduğunu gösterir. |
| magnitude_report_count | int | Bu depremi kaç kurumun bildirdiği |

Deduplikasyon yöntemi: 30 saniye zaman + 100km mesafe penceresi içindeki
kayıtlar aynı fiziksel deprem sayılır. Bilinen sınırlama: yoğun artçı
deprem dizilerinde (örn. 6 Şubat 2023 sonrası) kümelerin ~%0.51'inde aynı
kurumdan iki farklı olay yanlışlıkla aynı kümeye düşmüş olabilir
(zincirleme eşleşme etkisi). Detaylar için `DATA_CARD.md`.

## `data/processed/event_id_cluster_map.csv`

Her orijinal (kaynak, olay kimliği) çiftinin hangi temsilci kayda
devredildiğini gösterir. Bir USGS olayı deduplikasyon sırasında başka bir
olayla aynı kümeye düşerse, kendi kimliği ana veri setinden kaybolur ama
dalga formu dosyaları hâlâ eski kimlikle diskte durur; `build_dataset.py`
dalga formu sayımını doğru yapmak için bu eşlemeyi kullanır.

| Kolon | Açıklama |
|---|---|
| source | Kaynak kurum (usgs/isc/emsc) |
| source_event_id | Orijinal olay kimliği |
| representative_event_id | Kümenin hayatta kalan (temsilci) kimliği |

## `data/processed/usgs_catalog_turkey.parquet`

Sadece USGS'ten gelen ham katalog (genişletilmiş kataloğun bir girdisi).

| Kolon | Tip | Açıklama |
|---|---|---|
| event_id | string | USGS olay kimliği |
| magnitude | float | Büyüklük |
| mag_type | string | Büyüklük tipi (mb, ml, mw vb.) |
| place | string | USGS'in ürettiği yer tanımı (serbest metin) |
| longitude, latitude | float | Episantr koordinatı |
| depth_km | float | Odak derinliği (km) |
| status | string | "reviewed" / "automatic" |
| source | string | Veriyi bildiren ağ kodu |
| time_utc | datetime (UTC) | Olay zamanı |

## `data/processed/koeri_stations.csv`

| Kolon | Tip | Açıklama |
|---|---|---|
| network | string | Her zaman "KO" (KOERI) |
| station | string | İstasyon kodu |
| latitude, longitude | float | İstasyon konumu |
| elevation | float | Rakım (m) |
| start_date | string | İstasyonun kayıt başlangıç tarihi |
| channel_codes | string | İstasyondaki tüm kanal kodları (virgülle ayrık) |
| instrument_types | string | `strong_motion` / `broadband` / `short_period` (birden fazla olabilir) |
| has_strong_motion | bool | Gerçek güçlü hareket (mühendislik sınıfı) sensörü var mı. 277 istasyondan 128'i True |
| vs30_ms | float | Zemin sınıfı hızı (m/s). Kaynak: USGS Global Vs30 Mosaic (public domain) |
| nehrp_site_class | string | NEHRP zemin sınıfı: A (sert kaya) - E (yumuşak zemin) |

## `data/processed/turkiye_deprem_veriseti_v3.parquet`

Genişletilmiş katalog, istasyon eşleştirmesi, zemin sınıfı ve dalga formu
özniteliklerinin birleşimi. Projenin ana, kullanıma hazır çıktısı.

| Kolon | Açıklama |
|---|---|
| (genişletilmiş katalog sütunlarının tamamı) | bkz. yukarıdaki tablo |
| magnitude_scale_group | `moment_magnitude` / `local_magnitude` / `body_wave_magnitude` / `duration_magnitude` / `surface_wave_magnitude` / `diger`. Farklı büyüklük ölçekleri doğrudan karşılaştırılamaz, bu sütunla filtreleyin. |
| mw_estimate | ML tipi kayıtlar için ampirik dönüşümle tahmini Mw (bkz. build_dataset.py). mb/md/ms için boş. |
| nearest_station, nearest_station_distance_km | En yakın KOERI istasyonu (tip fark etmez) |
| nearest_strong_motion_station, nearest_strong_motion_distance_km | En yakın gerçek güçlü hareket istasyonu. Mühendislik analizi için bunu kullanın. |
| nearest_sm_vs30_ms, nearest_sm_site_class | En yakın güçlü hareket istasyonunun zemin sınıfı |
| has_waveform, num_waveform_files | Bu olay için gerçekten indirilmiş dalga formu var mı, kaç istasyondan |
| max_pga_g, max_pgv_cms | Dalga formu varsa, en yüksek PGA (g) ve PGV (cm/s) |
| best_snr_db | Dalga formu varsa, en iyi sinyal/gürültü oranı (dB) |
| has_phase_pick | Otomatik P-dalgası okuması başarılı oldu mu |

## `data/processed/waveforms/{event_id}_{station}.mseed`

M≥4.5 depremler için, en yakın (≤400km) KOERI istasyonlarından çekilmiş,
3 bileşenli ham dalga formu. Olay anından 10 saniye önce başlayıp 200
saniye sonrasına kadar kaydı içerir.
ObsPy ile okunur: `from obspy import read; st = read("dosya.mseed")`

Hangi olay/istasyon çiftinin denendiği ve sonucu (`ok` / `no_data`) için
`waveform_fetch_log.csv` dosyasına bakın.

## `data/processed/waveform_features.csv`

Her dalga formu dosyası için hesaplanan sinyal öznitelikleri
(`scripts/enrich_waveforms.py`).

| Kolon | Açıklama |
|---|---|
| file | Dalga formu dosya yolu |
| event_id, station | Olay ve istasyon kimliği |
| pga_g | Tepe yer ivmesi (g), cihaz tepkisi çıkarılmış |
| pgv_cms | Tepe yer hızı (cm/s), cihaz tepkisi çıkarılmış |
| snr_db | Sinyal/gürültü oranı (dB), P varışından önce/sonraki pencerelerin RMS oranı |
| p_pick_time | Otomatik STA/LTA ile bulunan P-dalgası varış zamanı |
| s_pick_time | Yatay bileşen enerjisinde P'den sonraki ilk büyük tetiklenme (kaba S-dalgası adayı, sezgisel yöntem, yayın kalitesinde değil) |

## `data/processed/waveform_fetch_log.csv`

| Kolon | Açıklama |
|---|---|
| event_id | Olay kimliği |
| station | Denenen KOERI istasyon kodu |
| distance_km | Olay-istasyon mesafesi |
| magnitude | Olay büyüklüğü |
| status | `ok` (dosya kaydedildi) / `no_data` (istasyonda o an veri yok) / `error: ...` |
| file | Başarılıysa dosya yolu |
