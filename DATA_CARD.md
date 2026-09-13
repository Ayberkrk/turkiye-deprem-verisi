# Veri Kartı: Türkiye Deprem Verisi

## Bu veri seti nedir?

Türkiye'yi ilgilendiren deprem kataloğu ve sismik dalga formu verilerinin,
birden fazla açık/uluslararası kaynaktan derlenip **makine öğrenmesi
kullanımına hazır** hale getirilmiş halidir. Amaç: Türkiye'ye özel deprem
yapay zekası (büyüklük tahmini, erken uyarı, sismik risk modelleri vb.)
geliştirmek isteyen araştırmacı/mühendislere, veriyi toplama ve temizleme
işini tek tek kendilerinin yapmasına gerek kalmadan hazır bir başlangıç
noktası sunmak.

## Kaynaklar

| Kaynak | İçerik | Kapsam |
|---|---|---|
| USGS + EMSC + ISC (deduplike) | Deprem kataloğu (konum, büyüklük, derinlik, zaman) | **84.100 benzersiz deprem**, 1990-günümüz, Türkiye sınırları |
| KOERI / ORFEUS-EIDA | İstasyon envanteri + talebe bağlı ham dalga formu | KOERI ağının tamamı (277 istasyon) |
| USGS Global Vs30 Mosaic | Zemin sınıfı (Vs30, NEHRP A-E) | 277/277 istasyon için |
| KOERI ham dalga formu (M≥4.5, genişletilmiş katalog üzerinden) | Çok bileşenli miniSEED kayıtları | **5.413 dosya, 1.104 benzersiz olay için en az 1 gerçek kayıt** |
| Sinyal öznitelikleri + mühendislik metrikleri + kalite kontrolü | PGA/PGV/SNR/faz + Sa(T)/Arias/CAV/D5-95 + QC | Tüm indirilen dosyalar için, `waveform_features.csv` |
| ISC uzman (analyst-reviewed) P/S pick'leri | Gerçek dalga formu olan olaylar için, mevcut olduğu kadar | **185 olay, 384 pick**, `isc_analyst_picks.csv` |
| Olay-istasyon tablosu | Her deprem-istasyon çifti için ayrı satır (mesafe+PGA tutarlı) | `event_station_table.csv` |
| ML benchmark bölmeleri | 3 görev için olay bazlı train/val/test | `benchmarks/`, bkz. `docs/benchmarks.md` |

## Bilinen sınırlamalar

- USGS kataloğu, yerel ağların kendi kataloglarına göre küçük büyüklükteki
  depremleri daha az yakalayabilir (küresel ağın hassasiyeti yerel
  ağlardan düşüktür). EMSC/ISC eklenmesi bu boşluğu büyük ölçüde kapatıyor.
- KOERI/EIDA üzerinden çekilen dalga formları istasyonun o tarihte aktif
  olup olmamasına bağlıdır; her olay/istasyon kombinasyonu veri
  içermeyebilir.
- Sadece USGS kataloğunda 2009-2019 arası olay sayısı belirgin şekilde
  düşüktü (muhtemelen USGS'in raporlama eşiğini o dönem değiştirmesi).
  EMSC/ISC eklenince bu boşluk büyük ölçüde kapandı, ama 2012-2019 arası
  hâlâ komşu yıllara göre biraz daha düşük kayıt sayısına sahip.
- Dalga formu arşivi 1990'ların ortasından öncesini kapsamıyor: KOERI'nin
  dijital güçlü hareket ağı esas olarak 1999 Kocaeli depreminden sonra
  genişledi.
- Genişletilmiş katalog (USGS+EMSC+ISC), aynı depremi birden fazla kurum
  bildirdiğinde zaman + büyüklüğe göre ölçeklenen mesafe + büyüklük farkı
  koşullarına dayalı bir eşleştirmeyle deduplike ediliyor; aynı kaynaktan
  gelen iki ayrı olay hiçbir zaman aynı kümeye birleştirilmiyor (bkz.
  `scripts/expand_catalog.py`). Her küme için bir `dedup_confidence`
  (0-1) skoru üretiliyor; düşük skorlu (yoğun artçı dizilerinde,
  <0.5 güvenli) küme sayısı ~57/84.100 seviyesinde. Sıfır hata payı iddia
  edilmiyor ama v1'e göre (o zaman ~424 kümede risk vardı) belirgin bir
  iyileşme sağlandı.
- mw_estimate sütunundaki dönüşüm formülü Marmara Bölgesi için türetilmiş
  (Şahin, Irmak, Livaoğlu, Yavuz, 2018, Uygulamalı Yerbilimleri Dergisi
  17(2):193-201); ulusal ölçekte kaba bir yaklaşıklıktır, kesin bir
  dönüşüm değildir.
- S-dalgası varış zamanı (s_pick_time) basit bir sezgisel yöntemle
  tahmin ediliyor, yayın kalitesinde bir faz okuma değildir. `isc_analyst_picks.csv`
  içinde, ISC Bulletin'den çekilmiş gerçek uzman pick'leri de bulunuyor
  (mevcut olduğu olaylar için) - bunlar otomatik pick'lerle karşılaştırma/
  doğrulama için kullanılabilir, ama tüm olayları kapsamıyor (ISC
  Bulletin'in nihai hale gelmesi aylar sürebiliyor).
- Sa(T)/Arias/CAV gibi mühendislik metrikleri, ivme kaydı elde
  edilebilen (`response_removed_ok=True`) her satırda hesaplanıyor;
  strong_motion olmayan (broadband/short_period) kayıtlardan
  hesaplananlar da dahil - bunlar için `instrument_type_used` sütununu
  kontrol edin.
- Dalga formu araması artık sadece USGS'in bildirdiği olaylarla sınırlı
  değil; genişletilmiş (USGS+EMSC+ISC) katalog üzerinden, `mw_estimate`
  ölçek-homojen büyüklük değerine göre M>=4.5 filtresi uygulanıyor
  (bkz. `scripts/fetch_waveforms_bulk.py`).

## Güçlü hareket (strong-motion) ve broadband ayrımı

`waveform_features.csv` içindeki her satır, PGA/PGV hesabının hangi kanal
ve sensör tipinden (`instrument_type_used`: `strong_motion` / `broadband`
/ `short_period`) geldiğini açıkça belirtir. Bir istasyonda güçlü hareket
(HN*, ivmeölçer) kanalı varsa PGA/PGV öncelikle ondan hesaplanır; yoksa
broadband (HH*) veya başka bir kanala düşülür ve bu durum satırda ayrı bir
sütunla işaretlenir. **Mühendislik amaçlı çalışmalar (PGA/PGV/tasarım
spektrumu) için `usable_for_engineering == True` olan satırları kullanın**;
bir broadband sismometreden hesaplanan PGA mühendislik tasarımı için
güvenilir kabul edilmez.

## Kalite kontrol (QC) bayrakları

Her dalga formu kaydı için şu QC alanları hesaplanıyor: `num_gaps`,
`gap_fraction` (MiniSEED boşluk oranı), `is_clipped` (dijitizör doygunluk
şüphesi), `has_three_components`, `sampling_rate_hz`, `duration_sec`,
`response_removed_ok` (cihaz tepkisi çıkarımı başarılı mı),
`p_pick_confidence`/`s_pick_confidence` (STA/LTA tetikleme gücüne dayalı
kaba güven skoru) ve özet olarak `usable_for_engineering` /
`usable_for_phase_picking`. Kritik bir QC sorunu (clipping, boşluk, tepki
çıkarımı hatası) varsa kayıt bu iki bayrakta da güvenilir sayılmaz;
sorunun türü `qc_flags` sütununda listelenir. Amaç, "dosya okunabiliyor"
ile "kayıt analiz için güvenilir" arasındaki farkı açık bırakmamak.

## PGA-mesafe ilişkisi için doğru tablo

Olay bazlı `turkiye_deprem_veriseti_v3.parquet` içindeki `max_pga_g`, bir
olay için indirilen BİRDEN FAZLA istasyon arasındaki en yüksek değeri
temsil eder ve `nearest_strong_motion_distance_km` başka bir istasyona ait
olabilir. Mesafe ile PGA'yı aynı istasyondan karşılaştırmak isteyen
çalışmalar (ör. azalım/attenuation analizi) `event_station_table.csv`
dosyasını kullanmalı; bu tabloda her satır tek bir deprem-istasyon
çiftini temsil eder.

## Önerilen kullanım alanları

- Deprem büyüklüğü/derinlik tahmini modelleri
- Erken uyarı sistemleri için faz okuma (phase picking) modelleri
- Sismik tehlike haritalama araştırmaları
- Ground-motion tahmin modelleri (büyüklük+mesafe+Vs30 -> PGA/PGV/Sa(T))
- (İleri seviye) Gerçek kayıtları referans alarak sentetik ivme kaydı
  üreten üretici modellerin eğitimi

Yukarıdaki görevlerin ilk üçü için hazır, olay bazlı train/val/test
bölmeleri `benchmarks/` altında mevcut - bkz. `docs/benchmarks.md`.

## Önerilmeyen kullanım alanları

- Tek başına bina/mülk risk değerlendirmesi (bu veri seti bina verisi
  içermez)
- Bu veriye dayanarak bireysel sigorta/kredi kararı vermek

## Lisans

Bkz. `LICENSE` (kod, MIT) ve `LICENSE-DATA.md` (veri, kaynağa göre değişir).

## Atıf

Bu veri setini kullanırken lütfen hem bu depoya hem de orijinal kaynaklara
(USGS, EMSC, ISC, KOERI) atıf verin. Detaylar `LICENSE-DATA.md` içinde.

`mw_estimate` sütununu kullanan çalışmalar ayrıca şu makaleye atıf
vermelidir:

> Şahin, Y.E., Irmak, T.S., Livaoğlu, H., Yavuz, E. (2018). Marmara
> Bölgesi Orta-Küçük Depremlerinin Mw-ML Dönüşüm Bağıntısı. Uygulamalı
> Yerbilimleri Dergisi, 17(2), 193-201.
