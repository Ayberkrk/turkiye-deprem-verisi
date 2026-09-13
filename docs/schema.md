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
| cluster_size | int | Bu depremi kaç ayrı (kaynak, kayıt) çiftinin bildirdiği |
| cluster_max_time_diff_sec | float | Kümedeki kayıtlar arasındaki en büyük zaman farkı (saniye) |
| cluster_max_distance_km | float | Kümedeki kayıtlar arasındaki en büyük konum farkı (km) |
| cluster_max_magnitude_diff | float | Kümedeki kayıtlar arasındaki en büyük büyüklük farkı |
| dedup_confidence | float (0-1) | Kümenin eşleşme güven skoru. Tek kaynaklı kümelerde 1.0. Zaman/mesafe/büyüklük farkı arttıkça düşer. |

Deduplikasyon yöntemi (v2): bir olay, zaman farkı <=30sn, büyüklüğe göre
ölçeklenen bir mesafe eşiği (50-150km, büyük depremlerde daha geniş) ve
büyüklük farkı <=1.5 olan bir kümeye katılabilir. AYNI KAYNAKTAN gelen bir
olay zaten o kümedeyse katılamaz (bir kurum aynı depremi iki kez
bildirmez; bu kural v1'deki en büyük yanlış-birleşme kaynağını ortadan
kaldırıyor). Birden fazla aday küme uyuyorsa en iyi eşleşen seçilir.
Detaylar için `DATA_CARD.md`.

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
| max_pga_g, max_pgv_cms | Dalga formu varsa, en yüksek PGA (g) ve PGV (cm/s). Öncelikle güçlü hareket (strong-motion) kayıtlarından hesaplanır; hiç yoksa broadband/short-period'a düşülür (bkz. pga_from_strong_motion). |
| pga_from_strong_motion | Bu satırdaki max_pga_g/max_pgv_cms gerçekten bir güçlü hareket sensöründen mi geldi (True) yoksa broadband/short-period'dan mı düştü (False) |
| best_snr_db | Dalga formu varsa, en iyi sinyal/gürültü oranı (dB) |
| has_phase_pick | Otomatik P-dalgası okuması başarılı oldu mu |

Not: bir olay için tek bir `max_pga_g` değeri, o olay için indirilen
BİRDEN FAZLA istasyon arasındaki en yüksek değeri temsil eder ve
`nearest_strong_motion_distance_km` başka bir istasyona ait olabilir. PGA
ile mesafeyi aynı istasyondan karşılaştırmak için (ör. azalım grafiği)
`event_station_table.csv` kullanılmalı.

## `data/processed/waveforms/{event_id}_{station}.mseed`

M≥4.5 (mw_estimate bazlı) depremler için KOERI istasyonlarından çekilmiş,
çok bileşenli ham dalga formu. Olay anından 10 saniye önce başlayıp 200
saniye sonrasına kadar kaydı içerir. Kaynak katalog: genişletilmiş/deduplike
katalog (`turkiye_deprem_katalogu_genisletilmis.parquet`); sadece USGS'in
bildirdiği olaylarla sınırlı değildir (bkz. `scripts/fetch_waveforms_bulk.py`).

İstasyon seçimi: en yakınından başlanarak, olay başına 4 başarılı kayda
ulaşılana kadar (en fazla 12 aday, 400km'ye kadar) sırayla denenir - ilk
4 istasyondan bazıları veri vermezse 5., 6., ... istasyona geçilir.
İstasyonun olay anında ilgili kanalın (HH/HN/EH/BH) gerçekten aktif olup
olmadığı `koeri_channels.csv`'den kontrol edilir (bir istasyonda BUGÜN bir
sensör olması, 2005'te de olduğu anlamına gelmez).

ObsPy ile okunur: `from obspy import read; st = read("dosya.mseed")`

Hangi olay/istasyon çiftinin denendiği ve sonucu (`ok` / `no_data`) için
`waveform_fetch_log.csv` dosyasına bakın.

## `data/processed/koeri_channels.csv`

`koeri_stations.csv`'nin kanal bazlı, zaman aralıklı hali
(`scripts/fetch_orfeus_eida.py`). Bir istasyonun genel özet bilgisi
zamanla değişebilir (yeni sensör eklenir, eskisi kaldırılır); bu tablo
her kanalın gerçek başlangıç/bitiş tarihini tutar.

| Kolon | Açıklama |
|---|---|
| network, station, location, channel | Kimlik bilgisi |
| instrument_type | `strong_motion` / `broadband` / `short_period` |
| latitude, longitude, sample_rate_hz | Kanal konumu ve örnekleme hızı |
| start_date, end_date | Kanalın aktif olduğu tarih aralığı (end_date boşsa hâlâ aktif) |

## `data/processed/waveform_features.csv`

Her dalga formu dosyası için hesaplanan sinyal özniteliği ve kalite
kontrol (QC) alanları (`scripts/enrich_waveforms.py`).

| Kolon | Açıklama |
|---|---|
| file | Dalga formu dosya yolu |
| event_id, station | Olay ve istasyon kimliği |
| network, location | SEED ağ/lokasyon kodu |
| channel_used, instrument_type_used | PGA/PGV hesabında hangi kanal ve sensör tipinin (`strong_motion`/`broadband`/`short_period`) kullanıldığı. Güçlü hareket kanalı varsa öncelikli, yoksa broadband'e düşülür. |
| pga_g | Tepe yer ivmesi (g), cihaz tepkisi çıkarılmış, `channel_used`'dan |
| pgv_cms | Tepe yer hızı (cm/s), cihaz tepkisi çıkarılmış |
| snr_db | Sinyal/gürültü oranı (dB), P varışından önce/sonraki pencerelerin RMS oranı |
| p_pick_time, s_pick_time | Otomatik faz okuması (STA/LTA). S sezgisel bir tahmindir, yayın kalitesinde değil. |
| p_pick_confidence, s_pick_confidence | STA/LTA tetikleme gücüne dayalı kaba güven skoru (0-1) |
| sampling_rate_hz, duration_sec | Kaydın örnekleme hızı ve süresi |
| num_gaps, gap_fraction | MiniSEED içindeki boşluk (gap) sayısı ve kaydın ne kadarının boşluk olduğu |
| is_clipped | Dijitizör doygunluğu (clipping) şüphesi |
| has_three_components | Üç farklı bileşen (Z/N/E gibi) mevcut mu |
| response_removed_ok | Cihaz tepkisi çıkarımı (instrument response removal) başarılı oldu mu |
| usable_for_engineering | PGA güçlü hareket sensöründen geldi VE kritik bir QC sorunu yok |
| usable_for_phase_picking | P faz okuması var VE Z bileşeni/boşluk sorunu yok |
| qc_flags | Tespit edilen kalite sorunlarının virgülle ayrılmış listesi (ör. `clipping_şüphesi`, `has_gaps`, `eksik_bileşen`) |
| sa_g_0_1s ... sa_g_2_0s | %5 sönümlü SDOF sistem için sözde-ivme tepki spektrumu (g), periyotlar: 0.1/0.2/0.5/1.0/2.0 saniye (Newmark-beta, ortalama ivme yöntemi) |
| arias_intensity_ms | Arias şiddeti (m/s) |
| cav_ms | Kümülatif mutlak hız - CAV (m/s) |
| duration_5_95_sec | Arias şiddetinin %5-%95 arasına ulaşma süresi (anlamlı sarsıntı süresi) |
| fas_dominant_freq_hz, fas_mean_freq_hz | Fourier genlik spektrumunun tepe frekansı ve genlik-ağırlıklı ortalama frekansı |

## `data/processed/event_station_table.csv`

Her satırı TEK BİR (event_id, station) çiftini temsil eden, PGA-mesafe
gibi ilişkileri fiziksel olarak tutarlı biçimde incelemek için üretilen
tablo (`scripts/build_event_station_table.py`).

| Kolon | Açıklama |
|---|---|
| event_id, station, network, location, channel_used, instrument_type_used | Kimlik ve sensör bilgisi |
| event_latitude, event_longitude, depth_km | Olay konumu |
| station_latitude, station_longitude | İstasyon konumu |
| epicentral_distance_km | Yüzeydeki (episantr) mesafe |
| hypocentral_distance_km | Odak noktasına (hiposantr) gerçek mesafe, derinlik dahil |
| magnitude, mag_type | Olay büyüklüğü ve tipi |
| mw_estimate, time_utc | Ölçek-homojen büyüklük tahmini ve olay zamanı |
| pga_g, pgv_cms, snr_db | Bu istasyondaki sinyal öznitelikleri |
| sa_g_0_1s ... sa_g_2_0s, arias_intensity_ms, cav_ms, duration_5_95_sec | Mühendislik öznitelikleri, bkz. waveform_features.csv |
| fas_dominant_freq_hz, fas_mean_freq_hz | Fourier spektrum özeti |
| p_pick_time, s_pick_time, p_pick_confidence, s_pick_confidence | Faz okuması |
| vs30_ms, nehrp_site_class, has_strong_motion | İstasyonun zemin/sensör bilgisi |
| response_removed_ok, usable_for_engineering, usable_for_phase_picking, qc_flags | Kalite bayrakları |
| file | Dalga formu dosya yolu |

## `data/processed/isc_analyst_picks.csv`

ISC Bulletin'den (`includearrivals=True` ile) çekilmiş, uzman tarafından
doğrulanmış (analyst-reviewed) gerçek P/S pick'leri (`scripts/fetch_isc_picks.py`).
Sadece gerçek dalga formu indirilmiş olaylar için çekilir. `enrich_waveforms.py`'nin
otomatik STA/LTA pick'lerinin aksine, bunlar bir sismoloji uzmanı
tarafından doğrulanmış gerçek etiketlerdir - phase-picking modelleri için
gerçek bir ground-truth kaynağı.

| Kolon | Açıklama |
|---|---|
| event_id, station | Kimlik bilgisi |
| phase_type | `P` veya `S` |
| phase_hint | ISC'nin ham faz etiketi (ör. `Pn`, `Pg`, `Sg`) |
| pick_time | Uzman tarafından doğrulanmış varış zamanı |
| source | Her zaman `isc_analyst` |

Sınırlama: ISC Bulletin'in nihai (reviewed) hale gelmesi genelde birkaç
ay sürer, bu yüzden çok yeni olaylarda pick bulunamayabilir; her olay
ISC'ye bildirilmiş/işlenmiş olmayabilir.

## `benchmarks/`

Üç ML görevi (ground_motion, phase_picking, early_warning) için olay
bazlı train/val/test bölmeleri. Detaylar için `docs/benchmarks.md`.

## `data/processed/waveform_fetch_log.csv`

| Kolon | Açıklama |
|---|---|
| event_id | Olay kimliği (genişletilmiş katalogdaki temsilci kimlik) |
| station | Denenen KOERI istasyon kodu |
| distance_km | Olay-istasyon mesafesi |
| magnitude | Olay büyüklüğü (ham) |
| event_source | Olayın hangi kurum tarafından bildirildiği (`reported_by`, ör. `emsc,isc`) |
| status | `ok` (dosya kaydedildi) / `no_data` (istasyonda o an veri yok) / `error: ...` |
| file | Başarılıysa dosya yolu |

## `data/processed/validation_report.json`, `validation_report.md`

`scripts/validate_dataset.py`'nin her çalıştırmada ürettiği kalite özeti:
hangi kontrolün geçtiği/kaldığı ve detayı. Yayınlanan her sürümün kalite
durumunu arşivlemek için kullanılır.
