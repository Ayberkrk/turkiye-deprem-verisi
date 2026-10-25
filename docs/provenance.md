# Veri kökeni ve yeniden üretilebilirlik

`python scripts/build_provenance.py` pipeline sonunda
`data/processed/provenance_manifest.json` üretir. Manifest; kaynak kodun Git
commit ve çalışma ağacı durumunu, Python sürümünü, isteğe bağlı açık build
metaverisini, build zamanını, pipeline bağımlılık sürümlerini, dahil edilen
veri çıktılarının boyut ve SHA-256 özetlerini, veri katmanlarının sorgu
ayarları/kaynak/lisans başvurularını ve tablolarda mevcut olan kaynak kökeni
sütunlarını kaydeder.

Metadata dosyası verilmediğinde güncel UTC build zamanı yazılır. Tekrarlanabilir
manifest üretmek için `build_time_utc` değerini de içeren JSON metadata dosyası
verin. Aynı dosyalar, aynı Git bilgisi, bağımlılık sürümleri ve aynı metadata
ile manifest içeriği deterministiktir. Özel build bilgisi vermek için JSON
nesnesi içeren bir dosya kullanın:

```json
{
  "dataset_release": "5.15.0",
  "build_time_utc": "2026-10-25T10:00:00+00:00",
  "source_query_window": "1990-01-01/2026-12-31",
  "pipeline_run_id": "release-5.15.0"
}
```

```bash
python scripts/build_provenance.py --metadata-json build-metadata.json
```

Analyst-reviewed ISC pick adımı atlandıysa durumu açıkça kaydedin:

```bash
python scripts/build_provenance.py --skip-isc-picks
```

Ham kaynak olay yanıtlarının `expanded_catalog_raw_cache.parquet` önbelleği
mevcutsa o da hashlenir; dosya Hugging Face'ten indirilmiş veri kopyalarında
bulunmayabileceği için zorunlu tutulmaz. Manifestin hashlediği dosyalar ana katalog tabloları, istasyon/kanal tabloları,
dalga formu özellikleri ve indirme günlüğü, doğrulama raporları, benchmark
bölmeleri ve varsa her bir ham dalga formu dosyasıdır. Hash işlemi dosyaları
1 MiB parçalar halinde okuyarak belleği dosya boyutundan bağımsız tutar. Tam
dalga formu arşivinin hashlenmesi disk okuması gerektirir; büyük arşivlerde
işlem zaman alabilir. Herhangi bir zorunlu çıktı yoksa manifest oluşturma
hata koduyla durur; eksik veya kısmi çıktı için başarılı manifest yazılmaz.

Kaynak sorgu ayarları manifestte kaynak başına kayıtlıdır: USGS/EMSC/ISC için
yıllık aralıklar, kutu sınırı ve minimum büyüklük; KOERI için ağ, olay filtresi,
istasyon/mesafe sınırları ve dalga formu penceresi; Vs30 için ArcGIS servis
uç noktası ve istasyon-koordinat sorgusu. EMSC ve ISC uçları ObsPy FDSN
alias yönlendirmesiyle çözülür; bu nedenle gerçek uç noktayı sorgu anında
kullanılan ObsPy sürümüyle birlikte değerlendirin.

## Kaynak lisansı ve kökeni

Manifest, `LICENSE-DATA.md`'deki sınıflandırmaları veri katmanı başına
yansıtır: USGS katalog ve Vs30 katmanları public domain; EMSC şartları
belirsiz; ISC için atıf gerekli ve toplu yeniden dağıtım lisansı belirtilmemiş;
KOERI/EIDA verisi ticari olmayan yeniden kullanımla sınırlı. Kaynak referansları
ve dosya/sütun kökeni her kaynak nesnesinde listelenir. Kaynak durumu mevcut
tablolarda görülen kayıt/satır sayılarına dayanır; başarısız sorgu kaydı
bulunmadığı için sıfır gözlem, tek başına servis hatası kanıtı değildir. Olay
kataloğu kökeni `event_id_cluster_map.csv` içindeki `source` alanından akış
halinde sayılır; istasyon Vs30 ve dalga formu sayıları da ilgili CSV/dizin
üzerinden sayılır.

Bu manifest **lisans vermez** ve dış kaynaktan izin alındığını göstermez.
Yeniden kullanım ve yeniden dağıtım öncesi `LICENSE-DATA.md`'yi, kaynak
kurumların koşullarını ve gerektiğinde yazılı izin gereksinimini kontrol edin.

## Başarısız kaynak çekimleri

`scripts/download_usgs.py` yıllık sorguları tek tek yazar ve yalnızca bütün
yıllar başarıyla sorgulandığında geçici parquet dosyasını atomik olarak nihai
kataloğa taşır. Başarısız yıl varsa yıllar raporlanır, komut sıfır dışı çıkış
kodu verir ve önceki katalog korunur; eksik yıl içeren kısmi katalog
yayımlanmaz. Bütün yıllar başarılı olsa bile tamamı sıfır kayıt döndürürse
mevcut katalog korunur ve komut başarısız olur. Bu kontrol diğer kaynakların
kısmi yanıt vermediğini tek başına kanıtlamaz; EMSC/ISC indirme uyarılarını ve
manifestteki kaynak gözlemlerini de inceleyin.

Pipeline önce benchmark bölmelerini üretir, ardından doğrulama raporunu ve
son olarak provenance manifestini üretir. Böylece doğrulama, aynı çalışmada
oluşturulan bölmeleri denetler ve manifest son ürünleri hashler.

## Sürümler arası fark

Önceki manifesti varsayılan manifestle karşılaştırmak için:

```bash
python scripts/build_provenance.py --compare-to previous-provenance.json
```

Fark çıktısı eklenen, kaldırılan ve hash/boyutu değişen dosyaları; ayrıca her
kaynak için gözlemlenen satır/dalga formu sayısı farklarını ayrı verir. Dosya
değişikliği veri anlamının veya bilimsel kalitenin değiştiğini tek başına
kanıtlamaz. Kaynak sayısı farkı da doğruluk değerlendirmesi değildir; bu rapor
sürüm incelemesine yardımcı olan bir envanterdir.
