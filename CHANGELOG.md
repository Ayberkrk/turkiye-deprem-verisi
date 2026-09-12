# Değişiklik Geçmişi

Bu dosya, veri setinde ve pipeline'da yapılan önemli değişiklikleri
sürüm sürüm listeler.

## v3 (güncel)

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
