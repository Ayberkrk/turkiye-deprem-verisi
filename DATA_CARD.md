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
| USGS + EMSC + ISC (deduplike) | Deprem kataloğu (konum, büyüklük, derinlik, zaman) | **83.598 benzersiz deprem**, 1990-günümüz, Türkiye sınırları |
| KOERI / ORFEUS-EIDA | İstasyon envanteri + talebe bağlı ham dalga formu | KOERI ağının tamamı (277 istasyon) |
| USGS Global Vs30 Mosaic | Zemin sınıfı (Vs30, NEHRP A-E) | 277/277 istasyon için |
| KOERI ham dalga formu (M≥4.5) | 3 bileşenli miniSEED kayıtları | **2.793 dosya, 1.005 benzersiz olay için en az 1 gerçek kayıt** |
| Sinyal öznitelikleri (PGA/PGV/SNR/faz) | Dalga formu başına hesaplanmış değerler | 2.793 dosyanın tamamı için, `waveform_features.csv` |

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
  bildirdiğinde 30 saniye zaman + 100km mesafe penceresiyle deduplike
  ediliyor. Yoğun artçı deprem dizilerinde bu yöntemin ~%0.51 oranında
  (kümelerin ~424/83.598'i) aynı kurumdan iki farklı olayı yanlışlıkla
  birleştirmiş olma ihtimali var (zincirleme eşleşme etkisi). Bu düşük
  ama sıfır olmayan bir hata payı.
- mw_estimate sütunundaki dönüşüm formülü Marmara Bölgesi için türetilmiş
  (Şahin, Irmak, Livaoğlu, Yavuz, 2018, Uygulamalı Yerbilimleri Dergisi
  17(2):193-201); ulusal ölçekte kaba bir yaklaşıklıktır, kesin bir
  dönüşüm değildir.
- S-dalgası varış zamanı (s_pick_time) basit bir sezgisel yöntemle
  tahmin ediliyor, yayın kalitesinde bir faz okuma değildir.

## Önerilen kullanım alanları

- Deprem büyüklüğü/derinlik tahmini modelleri
- Erken uyarı sistemleri için faz okuma (phase picking) modelleri
- Sismik tehlike haritalama araştırmaları
- (İleri seviye) Gerçek kayıtları referans alarak sentetik ivme kaydı
  üreten üretici modellerin eğitimi

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
