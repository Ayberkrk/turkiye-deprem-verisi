# Değişiklik Geçmişi

Bu dosya, veri setinde ve pipeline'da yapılan önemli değişiklikleri
sürüm sürüm listeler.

## v5.1

- `build_benchmarks.py`'deki `early_warning` görevinin "en az 10s kayıt
  süresi" filtresi ölü kodmuş: `event_station_table.csv`'de `duration_sec`
  sütunu hiç yoktu (`build_event_station_table.py`'nin çıkış sütunları
  arasında eksikti), bu yüzden koşul her zaman False'du ve filtre asla
  çalışmadı. `duration_sec` artık tabloya taşınıyor ve filtre gerçekten
  uygulanıyor. Fixes #7
- `enrich_waveforms.py`'nin modül docstring'i Sa(T) hesaplamasında
  kullanılan Newmark-beta varyantını yanlış tanımlıyordu ("doğrusal ivme,
  beta=1/6" diyordu; kod ve `newmark_sdof_psa` fonksiyonunun kendi
  docstring'i doğru şekilde "ortalama ivme, beta=1/4" kullanıyor).
  Hesaplama doğruydu, sadece özet açıklama düzeltildi. Fixes #8

## v5 (güncel)

Dalga formu hacmini artırma, mühendislik özniteliklerini genişletme ve
resmi ML benchmark'ları ekleme turu:

### Eklenenler

- `fetch_waveforms_bulk.py`: istasyon deneme algoritması "en yakın 4'ü dene" yerine "4 başarılı kayda ulaşana kadar en fazla 12 istasyonu sırayla dene" oldu. Aynı network bütçesiyle dosya sayısını ~2.960'tan **5.413**'e çıkardı.
- `fetch_orfeus_eida.py`: kanal bazlı, zaman aralıklı yeni bir tablo (`koeri_channels.csv`) eklendi; bir istasyonda bugün bir sensör olması geçmişte de olduğu anlamına gelmiyordu, artık olay anındaki gerçek aktiflik kontrol ediliyor.
- `enrich_waveforms.py`: mühendislik öznitelikleri eklendi - Sa(0.1/0.2/0.5/1.0/2.0s) response spectrum (Newmark-beta), Arias intensity, CAV, anlamlı sarsıntı süresi (D5-95), Fourier spektrum özeti.
- Yeni `scripts/fetch_isc_picks.py`: gerçek dalga formu indirilen olaylar için ISC Bulletin'den uzman tarafından doğrulanmış (analyst-reviewed) P/S pick'leri çekiliyor (`isc_analyst_picks.csv`, 185 olay/384 pick) - otomatik STA/LTA pick'lerine gerçek bir karşılaştırma/doğrulama kaynağı sağlıyor.
- Yeni `scripts/build_benchmarks.py`: üç ML görevi (ground_motion, phase_picking, early_warning) için olay bazlı train/val/test bölmeleri + istasyon bazlı ve zaman bazlı ileri seviye holdout'lar. Detaylar `docs/benchmarks.md`.
- Sonuç: 5.413 dalga formu dosyası, 1.104 benzersiz olay için (önceki sürümde 2.960/1.068'di).

### Düzeltilen hatalar

- `fetch_waveforms_bulk.py`'de yeni bir kolon (`event_source`) eklenirken benzer bir CSV şema uyumsuzluğu daha yaşandı; `enrich_waveforms.py`'deki gibi bir migrasyon fonksiyonu eklendi.
- Newmark-beta katsayılarında bir hata Sa değerlerinin sonsuza ıraksamasına yol açıyordu; doğru formülle yeniden yazıldı ve rezonans testiyle doğrulandı.
- Boş bir pandas DataFrame'i boolean olmayan (bool dtype dışı) bir maskeyle filtrelemenin tüm sütunları düşürdüğü bir pandas tuhaflığı, istasyon aktiflik kontrolü öncesine boş-kontrolü eklenerek giderildi.

## v4

GitHub issue takibiyle (6 madde) gelen iyileştirmeler:

### Eklenenler

- Deduplikasyon yöntemi geliştirildi: sabit 30sn/100km eşiği yerine büyüklüğe göre ölçeklenen mesafe eşiği (50-150km) ve büyüklük farkı (<=1.5) koşulu eklendi; aynı kaynaktan gelen iki farklı olay artık asla aynı kümeye birleştirilmiyor. Her küme için `dedup_confidence`, `cluster_size`, `cluster_max_time_diff_sec`, `cluster_max_distance_km`, `cluster_max_magnitude_diff` sütunları eklendi.
- `fetch_waveforms_bulk.py` artık genişletilmiş/deduplike katalog üzerinden çalışıyor (önceden sadece USGS kataloğu kullanılıyordu); M>=4.5 filtresi ham büyüklük yerine ölçek-homojen `mw_estimate` üzerinden uygulanıyor. Waveform arama kapsamı artık EMSC/ISC kaynaklı olayları da içeriyor.
- `enrich_waveforms.py`'de güçlü hareket (strong-motion) ve broadband/short-period kayıtlar ayrıştırıldı: PGA/PGV öncelikle güçlü hareket kanalından hesaplanıyor, hangi kanal/sensör tipinin kullanıldığı (`instrument_type_used`, `channel_used`) her satırda saklanıyor.
- Waveform kalite kontrol (QC) metrikleri eklendi: `num_gaps`, `gap_fraction`, `is_clipped`, `has_three_components`, `sampling_rate_hz`, `duration_sec`, `response_removed_ok`, `p_pick_confidence`, `s_pick_confidence`, `usable_for_engineering`, `usable_for_phase_picking`, `qc_flags`.
- Yeni `scripts/build_event_station_table.py`: her deprem-istasyon çiftini ayrı bir satırda tutan `event_station_table.csv` üretiliyor; böylece PGA-mesafe gibi analizler aynı istasyondan gelen değerleri karşılaştırıyor. README'deki PGA-mesafe grafiği bu tablodan yeniden üretildi.
- `validate_dataset.py` genişletildi: event-station mesafesinin koordinatlardan yeniden hesaplanıp doğrulanması, aşırı PGA/PGV outlier kontrolü, P/S faz sıralaması kontrolü, dedup küme kalitesi kontrolü ve makine tarafından okunabilir `validation_report.json`/`validation_report.md` çıktısı eklendi.
- `build_dataset.py`: olay bazlı `max_pga_g`/`max_pgv_cms` artık öncelikle güçlü hareket kayıtlarından hesaplanıyor (`pga_from_strong_motion` bayrağıyla işaretli).
- Sonuç: 84.100 benzersiz deprem, 2.960 gerçek dalga formu dosyası (1.068 benzersiz olay için, önceki sürümde 1.005'ti).

### Düzeltilen hatalar

- EMSC/ISC olay kimlikleri (`smi:ISC/evid=...`, `quakeml:eu.emsc/event/...`) ":" ve "/" karakterleri içerdiği için doğrudan dosya adında kullanılınca `FileNotFoundError` veriyordu (işletim sistemi "/" karakterini var olmayan bir alt dizin sanıyordu). `fetch_waveforms_bulk.py`'ye tersine çevrilebilir bir dosya adı kodlaması (`sanitize_event_id`/`desanitize_event_id`) eklendi.
- `waveform_fetch_log.csv`'ye yeni bir sütun (`event_source`) eklenirken eski satırların şemasıyla çakışıp dosyanın bozulmasına (satır başına tutarsız sütun sayısı) yol açan bir şema uyumluluğu sorunu giderildi; `enrich_waveforms.py`'deki gibi bir şema kontrolü/otomatik göç eklendi.

## v3

### Eklenenler

- Katalog USGS'ten EMSC ve ISC ile genişletildi, deduplike edildi: 15.782 kayıttan 83.598 benzersiz depreme çıkıldı.
- Her deprem için hangi kurumların bildirdiği (`reported_by`) ve büyüklük tutarlılığı (`magnitude_agreement_std`, `magnitude_report_count`) eklendi.
- KOERI istasyonları kanal seviyesinde çekilerek gerçek güçlü hareket sensörü olanlar ayırt edildi (277 istasyondan 128'i).
- Her istasyona USGS Global Vs30 Mosaic'ten zemin sınıfı (Vs30, NEHRP A-E) eklendi.
- Dalga formu eşiği M≥5.0'dan M≥4.5'e düşürüldü, istasyon sayısı 2'den 4'e çıkarıldı, mesafe sınırı 250km'den 400km'ye genişletildi.
- Her dalga formu için PGA, PGV, sinyal/gürültü oranı ve otomatik P/S faz okuması hesaplandı (`waveform_features.csv`).
- Karışık büyüklük ölçekleri (`md`, `mb`, `ml`, `mw` vb.) tek bir `magnitude_scale_group` sütununda gruplandı; ML tipi kayıtlar için ampirik bir Mw tahmini (`mw_estimate`) eklendi.
- `validate_dataset.py` ile yayın öncesi bütünlük kontrolleri eklendi (Vs30 aralığı, NEHRP sınıfı, büyüklük tutarlılığı dahil, toplam 15 kontrol).
- `notebooks/01_baseline_example.py` ile veri setinin çalıştığını gösteren örnek eklendi, 83.598 olayla güncellendi.
- `event_id_cluster_map.csv`: deduplikasyon sırasında bir kümeye devredilen olayların dalga formu dosyalarının doğru olaya sayılmasını sağlayan eşleme dosyası eklendi.
- `scripts/run_all.sh` ile tüm pipeline'ı tek komutla çalıştırma imkanı eklendi.
- Lisans dosyası `LICENSE-CODE`'dan `LICENSE`'a yeniden adlandırıldı (GitHub'ın otomatik lisans algılaması için).
- Sonuç: 2.793 gerçek dalga formu dosyası, 1.005 benzersiz olay için.

### Bilinçli olarak eklenmeyenler

- STEAD: belirsiz Türkiye kapsamı, düşük mühendislik değeri.
- PEER NGA-West2: gerekli görülmedi, ORFEUS/EIDA zaten gerçek Türkiye verisi sağlıyor.
- Fay hattı eşleştirmesi: MTA'nın kendi verisi ticari kullanım ve değişiklik yasağı içeriyor; GEM'in versiyonu teknik olarak mümkün ama fayda/lisans riski oranı düşük bulundu.

## v2

- KOERI istasyon envanteri ve M≥5.0 depremler için ilk dalga formu arşivi (327 dosya) eklendi.
- En yakın istasyon ve en yakın güçlü hareket istasyonu ayrı ayrı hesaplandı.

## v1

- İlk sürüm: USGS deprem kataloğu (15.782 kayıt) ve KOERI istasyon listesi.
