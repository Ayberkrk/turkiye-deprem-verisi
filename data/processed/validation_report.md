# Veri Doğrulama Raporu

Üretim zamanı: 2026-10-03T07:56:34.025907+00:00

Toplam olay: 84100, toplam dalga formu dosyası: 5413

| Kontrol | Durum | Detay |
|---|---|---|
| Ana deprem kataloğu boş değil | OK |  |
| İstasyon tablosu boş değil | OK |  |
| Dalga formu özellik tablosu boş değil | OK |  |
| event_id benzersiz | OK |  |
| Eksik değer yok (kritik sütunlar) | OK |  |
| Büyüklük makul aralıkta (0-10) | OK |  |
| Koordinatlar Türkiye kutusunda (lat 34-44, lon 24-46) | OK |  |
| Derinlik negatif değil | OK |  |
| İstasyon koordinatları eksik değil | OK |  |
| has_waveform ile num_waveform_files tutarlı | OK |  |
| PGA değeri her satırda pozitif ya da sıfır | OK |  |
| Her dalga formu dosyası için en fazla 1 öznitelik satırı | OK |  |
| mw_estimate sadece local/moment magnitude gruplarında dolu | OK |  |
| Vs30 makul fiziksel aralıkta (100-2000 m/s) | OK |  |
| NEHRP zemin sınıfı geçerli değerlerde (A-E) | OK |  |
| Büyüklük tutarlılık sapması negatif değil | OK |  |
| reported_by sütunu boş değil | OK |  |
| Dalga formu dosyaları listelendiği kadar var | OK |  |
| Tüm dalga formu dosyaları okunabilir | OK |  |
| event-station epicentral mesafesi koordinatlarla tutarlı (<=1km fark) | OK |  |
| hypocentral mesafe >= epicentral mesafe | OK |  |
| Aşırı büyük PGA değeri yok (>4g şüpheli) | OK |  |
| Aşırı büyük PGV değeri yok (>500 cm/s şüpheli) | OK |  |
| usable_for_engineering yalnızca strong_motion kayıtlarda True | OK |  |
| pga_geomean_g iki yatay bileşenin tepe değerleri arasında | OK |  |
| pga_rotd50_g fiziksel üst sınırın (hypot(h1, h2)) altında | OK |  |
| pga_g, bileşen bazlı tepe değerlerin (h1/h2/v) maksimumuna eşit | OK |  |
| S faz okuması her zaman P'den sonra | OK |  |
| dedup_confidence 0-1 aralığında | OK |  |
| Düşük güvenli (<0.5) çok kaynaklı küme sayısı makul seviyede (<%1) | OK |  |
| Başarılı waveform_fetch_log kayıt sayısı, waveform dosya sayısıyla tutarlı | OK |  |
