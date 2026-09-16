# Veri Lisansları

Bu depodaki kod MIT lisanslıdır (bkz. `LICENSE`). Ancak **veri
katmanları farklı kaynaklardan geldiği için her birinin kendi lisansı
geçerlidir.** Bir veri dosyasını kullanmadan/yeniden dağıtmadan önce
aşağıdaki tabloyu kontrol edin.

| Katman | Kaynak | Lisans | Kısıtlama |
|---|---|---|---|
| `usgs_catalog_turkey.parquet` | USGS ComCat | **Public Domain** | Yok, sadece "USGS" atfı rica edilir |
| `turkiye_deprem_katalogu_genisletilmis.parquet` (EMSC katkılı satırlar) | EMSC | Belirsiz - bkz. not | Atıf zorunlu. EMSC'nin şartlar sayfası ([seismicportal.eu/terms.html](https://www.seismicportal.eu/terms.html)) genel materyaller için "kişisel/akademik/ticari olmayan kullanım" diyor, ama "bazı veri setleri CC-BY-4.0" diyor - katalog/olay verisinin hangi kategoriye girdiği kaynakta net değil. Ticari kullanımdan önce EMSC ile doğrudan teyit edin. |
| `turkiye_deprem_katalogu_genisletilmis.parquet` (ISC katkılı satırlar) | ISC Bulletin | Açık FDSN olay servisi | Atıf zorunlu; ISC "akademik ve ticari kullanımda her zaman atıf" şartı koyuyor. Kaynakta ([isc.ac.uk/iscbulletin/citing.php](https://www.isc.ac.uk/iscbulletin/citing.php)) toplu yeniden dağıtım için ayrı bir açık lisans belirtilmiyor. |
| `koeri_stations.csv`, `*.mseed` | KOERI / ORFEUS-EIDA | **Ticari kullanım kısıtlı** | **Sadece akademik/ticari olmayan kullanım.** EIDA veri politikası ([orfeus-eu.org/data/eida/acknowledgements](https://www.orfeus-eu.org/data/eida/acknowledgements/)): "Data available through EIDA are free of use and cannot be reused in unaltered form for commercial use." KOERI'nin kendi sitesi de aynı şartı koyuyor: veri **ticari amaçla kullanılamaz**, Boğaziçi Üniversitesi Rektörlüğü'nden yazılı izin gerekir. Bu depo/HF üzerinden bu veriyi indiren kimse, ticari bir üründe kullanmadan önce bu izni almalı. |
| `koeri_stations.csv` (vs30_ms, nehrp_site_class sütunları) | USGS Global Vs30 Mosaic | **Public Domain** | Yok, sadece "USGS" atfı rica edilir |
| `stead_turkiye_*.csv/hdf5` (varsa) | STEAD (Stanford) | **CC-BY-4.0** | Atıf zorunlu, orijinal STEAD makalesine referans verin |
| ISC-GEM'den türetilen değerler (varsa, sadece doğrulama amaçlı) | ISC-GEM | CC-BY-SA 3.0 | **Share-Alike**: bu veriyi doğrudan içeren herhangi bir çıktı aynı lisansla paylaşılmalı. Bu yüzden ISC-GEM verisi bu depoya ham olarak dahil edilmez, yalnızca doğrulama/karşılaştırma için kullanılır. |
| `mw_estimate` sütunu (formül) | Şahin ve diğerleri, 2018, Uygulamalı Yerbilimleri Dergisi | Akademik telif | Veri değil, bir formül; kullanan çalışmalar makaleye atıf vermeli. Tam kaynak `DATA_CARD.md`'nin Atıf bölümünde. |
| *(bu depoya dahil DEĞİL)* AFAD deprem kataloğu (`deprem.afad.gov.tr`) | AFAD | Belirsiz | Dokümante edilmemiş bir JSON servisi (`apiv2/event/filter`) var ama yayınlanmış kullanım şartı/lisansı yok. Bkz. `DATA_CARD.md` - "Bilinçli olarak eklenmeyen bir kaynak". |
| *(bu depoya dahil DEĞİL)* TADAS ivme/dalga formu verisi (`tadas.afad.gov.tr`) | AFAD | Kayıtlı kullanıcıya özel | Kimlik doğrulaması gerektiren bir portal; bu depodaki gibi anonim/otomatik toplu indirme için açık bir servis sunmuyor. Bkz. `DATA_CARD.md`. |

## Genel ilke

- Kod her zaman MIT.
- Kendi ürettiğimiz/birleştirdiğimiz orijinal metadata (Türkiye filtresi,
  bölge etiketleri gibi) CC-BY-4.0 ile paylaşılır.
- Bir kaynağın lisansı share-alike (CC-BY-SA, ODbL) ise, o kaynağın verisi
  bu depoya ham olarak eklenmez; sadece türetilmiş/agregat bilgi kullanılır.
- **Ticari kullanım öncesi mutlaka yukarıdaki tabloyu kontrol edin.**
  Bu depo/HF üzerinden erişilen veri katmanlarından en az biri
  (KOERI/ORFEUS-EIDA dalga formu ve istasyon verisi) **ticari kullanım
  için kaynak kurumdan ayrı yazılı izin** gerektiriyor; bu depo o izni
  vermez/temsil etmez. Akademik/araştırma amaçlı kullanım için bu
  kısıtlama geçerli değildir.
