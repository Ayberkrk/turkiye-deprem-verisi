# Değişiklik Geçmişi

Bu dosya, veri setinde ve pipeline'da yapılan önemli değişiklikleri
sürüm sürüm listeler.

## v5.8

- `turkiye_deprem` paketindeki yükleyiciler (`load_catalog` vb.) artık
  çalışma dizininden bağımsız çalışabiliyor: `data_dir=` parametresi ve
  `TURKIYE_DEPREM_DATA_DIR` ortam değişkeni ile veri dizini bir kez
  belirtilip her çağrıda tekrarlanmadan kullanılabiliyor. Varsayılan
  (repo kökünden, `data/processed/`) davranış değişmedi. README'ye
  örnek eklendi, testler: `tests/test_turkiye_deprem_io.py`. Fixes #19
- Yeni `notebooks/04_phase_picking_baseline.py`: otomatik STA/LTA
  pick'lerinin, resmi `phase_picking` split'i üzerinde ISC uzman
  pick'lerine göre P/S zamanlama hatasını (güven skoruna göre
  medyan-üstü/altı ayrımıyla) raporluyor - eğitilmiş bir model değil,
  mevcut etiketin split üzerindeki somut hata payı. `docs/benchmarks.md`
  ve `docs/leaderboard.md`'ye sonuç eklendi. Fixes #20
- Yeni `notebooks/05_early_warning_baseline.py`: her P-sonrası pencere
  (1/3/5/10s) için ham (cihaz tepkisi çıkarılmamış) genliğin log10'undan
  Mw tahmini (kapalı-form en küçük kareler), okunamayan dosyaları
  şeffaf şekilde sayıp atlıyor. `docs/benchmarks.md` ve
  `docs/leaderboard.md`'ye sonuç eklendi. Fixes #21
- (not: #18 - `validate_dataset.py`'nin boş temel veri tablolarını artık
  reddettiği, bu depoda başka bir oturumda/PR'da yapıldı, CHANGELOG'a
  daha önce eklenmemişti.)

## v5.7

- Yeni `turkiye_deprem/` Python paketi + kök dizinde `pyproject.toml`:
  `pip install -e .` sonrası `from turkiye_deprem import load_catalog,
  load_event_station_table, load_waveform_features` ile veri
  doğrudan yüklenebiliyor - artık `pd.read_parquet(Path("data/processed")
  / "...")` kalıbını dokümandan kopyalamaya gerek yok. Dosya eksikse
  Hugging Face indirme komutuna işaret eden açık bir hata veriyor.
  `requirements.txt`/CI akışı değişmedi, bu tamamen ek bir kurulum yolu.
  Testler: `tests/test_turkiye_deprem_io.py`.
- `scripts/validate_dataset.py`'nin kontrolleri, `scripts/quick_check.py`'nin
  de kullanabilmesi için saf fonksiyonlara ayrıldı (`structural_checks`,
  `event_station_geometry_checks`, `ground_motion_plausibility_checks`
  vb.). Yeni `tests/test_validate_dataset_checks.py`: her kontrol grubu
  için hem temiz hem sentetik-bozuk-satır senaryosu. Davranış birebir
  korundu (aynı 24 kontrol, aynı sonuç).
- Yeni `scripts/quick_check.py`: `validate_dataset.py`'nin hızlı
  versiyonu - sadece parquet/CSV'leri kontrol eder, 5.413 dalga formu
  dosyasını `obspy.read()` ile açan yavaş kontrolü atlar (obspy'yi hiç
  import etmez). CONTRIBUTING.md'ye ve CI'ye eklendi.
- Yeni `docs/schema.en.md`: `docs/schema.md`'nin İngilizce çevirisi -
  Hugging Face üzerinden gelen global kitle için. İki dosya karşılıklı
  linkli; README'nin İngilizce özetinden de link veriliyor.
- `CITATION.cff`'deki bayat `date-released` (2026-09-12) güncellendi.
- Yeni `.zenodo.json`: GitHub-Zenodo webhook'u (zaten kurulu) bir
  sonraki release'de bu metadata'yı okuyacak. `CITATION.cff`'e mevcut
  Zenodo DOI'si (`10.5281/zenodo.22754706`, v5.3.1 kaydı) `identifiers`
  alanı olarak eklendi; README'ye DOI rozeti, `DATA_CARD.md`'nin Atıf
  bölümüne DOI linki eklendi.

## v5.6

- `scripts/build_dataset.py`'deki `nearest()` fonksiyonu ve
  `scripts/build_event_station_table.py`'deki mesafe/PGA join mantığı
  için regresyon testleri eklendi (`tests/test_nearest_station.py`,
  `tests/test_event_station_join.py`) - bu kod yolu, issue #1'in
  ("PGA-mesafe grafiğinde istasyon eşleşmesini düzelt") kök nedeniydi ve
  o zamandan beri hiçbir hedefli testi yoktu. Join mantığı ayrıca ayrı,
  test edilebilir bir `join_features_with_distances()` fonksiyonuna
  çıkarıldı.
- `haversine_km`, 5 script'te (`build_dataset.py`,
  `build_event_station_table.py`, `expand_catalog.py`,
  `fetch_waveforms_bulk.py`, `validate_dataset.py`) ayrı ayrı kopyalanmış
  halindeydi; artık tek, test edilen `scripts/geo.py` modülünde
  (`tests/test_geo.py`). Fixes #12
- README/DATA_CARD/LICENSE-DATA'ya AFAD'ın neden bu depoya dahil
  edilmediğini açıklayan bir not eklendi: katalog tarafında dokümante
  edilmemiş/lisanssız bir API, TADAS (ivme/dalga formu) tarafında ise
  kayıtlı kullanıcıya özel bir erişim modeli - ikisi de bu depodaki
  anonim/otomatik indirme pipeline'ıyla uyuşmuyor. Fixes #11

## v5.5

- Yeni `scripts/compare_picks_to_isc.py`: otomatik (STA/LTA) P/S faz
  okumaları, `isc_analyst_picks.csv`'deki 384 uzman pick'iyle eşleştirip
  somut bir hata payı hesaplıyor (P: ortalama 9,3s/medyan 0,6s, S:
  ortalama 51,6s/medyan 9,5s; ayrıca `p_pick_confidence`/
  `s_pick_confidence` skorunun gerçekten öngörücü olduğu doğrulandı -
  medyan-üstü güvenli pick'lerde hata P'de ~7x, S'de ~2,5x daha düşük).
  DATA_CARD.md ve docs/benchmarks.md'deki S-pick uyarısı bu sayılarla
  güncellendi.
- Yeni `notebooks/03_ground_motion_randomforest.py`: `ground_motion`
  görevinde doğrusal baseline'ın yanına bir RandomForest ekleyip
  kıyaslıyor (test RMSE 0.419→0.392, R² 0.657→0.701) - doğrusal modelin
  ilişkinin çoğunu yakaladığını ama tamamını yakalamadığını gösteriyor.
  Ek bağımlılık (scikit-learn) sadece bu script'te, `02_ground_motion_baseline.py`
  bağımlılıksız kalmaya devam ediyor.
- Yeni `docs/leaderboard.md`: üç görev için model sonuçlarının
  toplandığı, PR ile katkı yapılabilen bir skor tablosu.

## v5.4

- `.github/workflows/tests.yml`: v5.3'te `waveforms/` git geçmişinden
  çıkarılınca CI'nin taze checkout'unda bu klasör boş kalıyor,
  `validate_dataset.py` da 5.413 dosya beklerken 0 bulup başarısız
  oluyordu (3 CI çalıştırması kırıktı). Doğrulama adımından önce
  dalga formu dosyalarını Hugging Face Hub'dan indiren bir adım
  eklendi. Fixes #9

## v5.3

- **Git geçmişi yeniden yazıldı** (`git filter-repo`): `data/processed/waveforms/`
  (5.413 dosya, geçmişteki tüm sürümler dahil ~465MB, deponun toplam
  boyutunun %96'sı) tüm commit geçmişinden çıkarıldı. Dalga formu
  dosyaları artık yalnızca Hugging Face Hub'da barındırılıyor
  (`huggingface.co/datasets/Ayberkkr/turkiye-deprem-verisi`) - hiçbir
  veri kaybı yok, sadece git deposu artık bu veriyi taşımıyor. `.git`
  boyutu ~490MB'dan ~13MB'a düştü.
  **Önemli**: `git filter-repo`, HEAD'i yeniden yazılmış haline
  resetlerken çalışma dizinindeki `data/processed/waveforms/` dosyalarını
  da diskten siliyor (sadece git takibini bırakmıyor). Bu operasyonu
  yapan herkes önce dosyaları başka bir yere kopyalamalı/yedeklemeli,
  sonrasında geri kopyalayıp (artık untracked/ignored olarak) yerine
  koymalı.
  Bu geçmiş rewrite olduğu için eski bir klon üzerinde çalışan biri
  `git fetch` sonrası `git reset --hard origin/main` yapmalı, ardından
  `hf download Ayberkkr/turkiye-deprem-verisi --repo-type dataset
  --local-dir .` ile dalga formu dosyalarını yeniden edinmeli.
- `data/processed/*.parquet`, `*.csv` ve `benchmarks/` bilinçli olarak
  geçmişte bırakıldı: toplamları (~14MB) önemsiz, PR'larda diff'lenebilir
  olmaları değerli.

## v5.2

- `tests/`: `scripts/` altındaki saf fonksiyonlar için birim testler
  eklendi (haversine/mesafe eşiği, split determinizmi, Newmark-beta ve
  Arias/CAV'ın analitik çözümlerle doğrulanması, issue #7'nin kalıcı
  regresyon testi).
- `.github/workflows/tests.yml`: her push/PR'da testleri ve
  `validate_dataset.py`'yi çalıştıran CI eklendi.
- Yeni `notebooks/02_ground_motion_baseline.py`: `ground_motion`
  split'leri üzerinde basit bir zayıflama modeli, split'lerin
  öğrenilebilir bir sinyal taşıdığını kanıtlıyor (test R²≈0.66).
- `CONTRIBUTING.md` eklendi.
- İşlenmiş veri artık Hugging Face Hub'da da barındırılıyor
  (`huggingface.co/datasets/Ayberkkr/turkiye-deprem-verisi`); README'ye
  `hf download` ile doğrudan indirme yolu eklendi.
- `data/processed/expanded_catalog_raw_cache.parquet` ve
  `data/processed/isc_picks_progress.csv` depodan çıkarıldı - bunlar
  build-time önbellek/checkpoint dosyaları, dokümante edilmiş bir veri
  ürünü değil (`waveform_fetch_log.csv`'nin aksine, bkz. `docs/schema.md`).

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

## v5

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
