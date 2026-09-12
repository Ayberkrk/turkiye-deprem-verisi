# Veri Lisansları

Bu depodaki kod MIT lisanslıdır (bkz. `LICENSE`). Ancak **veri
katmanları farklı kaynaklardan geldiği için her birinin kendi lisansı
geçerlidir.** Bir veri dosyasını kullanmadan/yeniden dağıtmadan önce
aşağıdaki tabloyu kontrol edin.

| Katman | Kaynak | Lisans | Kısıtlama |
|---|---|---|---|
| `usgs_catalog_turkey.parquet` | USGS ComCat | **Public Domain** | Yok, sadece "USGS" atfı rica edilir |
| `turkiye_deprem_katalogu_genisletilmis.parquet` (EMSC katkılı satırlar) | EMSC | **CC-BY-4.0** | Atıf zorunlu (kaynak alanı hangi kurumdan geldiğini gösteriyor) |
| `turkiye_deprem_katalogu_genisletilmis.parquet` (ISC katkılı satırlar) | ISC Bulletin | Açık FDSN olay servisi | Atıf zorunlu; ISC "akademik ve ticari kullanımda her zaman atıf" şartı koyuyor |
| `koeri_stations.csv`, `*.mseed` | KOERI / ORFEUS-EIDA | Açık FDSN veri servisi | Akademik atıf beklenir (KOERI'ye referans) |
| `koeri_stations.csv` (vs30_ms, nehrp_site_class sütunları) | USGS Global Vs30 Mosaic | **Public Domain** | Yok, sadece "USGS" atfı rica edilir |
| `stead_turkiye_*.csv/hdf5` (varsa) | STEAD (Stanford) | **CC-BY-4.0** | Atıf zorunlu, orijinal STEAD makalesine referans verin |
| ISC-GEM'den türetilen değerler (varsa, sadece doğrulama amaçlı) | ISC-GEM | CC-BY-SA 3.0 | **Share-Alike**: bu veriyi doğrudan içeren herhangi bir çıktı aynı lisansla paylaşılmalı. Bu yüzden ISC-GEM verisi bu depoya ham olarak dahil edilmez, yalnızca doğrulama/karşılaştırma için kullanılır. |
| `mw_estimate` sütunu (formül) | Şahin ve diğerleri, 2018, Uygulamalı Yerbilimleri Dergisi | Akademik telif | Veri değil, bir formül; kullanan çalışmalar makaleye atıf vermeli. Tam kaynak `DATA_CARD.md`'nin Atıf bölümünde. |

## Genel ilke

- Kod her zaman MIT.
- Kendi ürettiğimiz/birleştirdiğimiz orijinal metadata (Türkiye filtresi,
  bölge etiketleri gibi) CC-BY-4.0 ile paylaşılır.
- Bir kaynağın lisansı share-alike (CC-BY-SA, ODbL) ise, o kaynağın verisi
  bu depoya ham olarak eklenmez; sadece türetilmiş/agregat bilgi kullanılır.
