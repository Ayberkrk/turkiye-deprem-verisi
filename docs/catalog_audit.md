# Katalog kapsamı ve eşleşme denetimi

## Coğrafi kapsam

`scripts/expand_catalog.py` kaynak katalogları sabit bir dikdörtgen coğrafi
arama alanıyla sorgular: enlem 35.0–43.0°, boylam 25.0–45.5°. Bu alan,
Türkiye'yi ve çevresindeki deniz/sınır bölgelerinden bazı olayları kapsayan
bir **arama extent'idir**; resmi Türkiye kara sınırı poligonu değildir ve
ülke sınırlarına göre kesin bir dahil etme iddiası olarak yorumlanmamalıdır.

`scripts/validate_dataset.py` daha geniş bir tutarlılık zarfı kullanır:
enlem 34–44° ve boylam 24–46°. Bu, koordinatların beklenen yaklaşık bölgede
olduğunu denetler; kaynak sorgusunun coğrafi filtresiyle aynı kapsamı
tanımlamaz. Arama alanı daraltılır/genişletilirse bu doküman ve ilgili
validasyon açıklaması birlikte güncellenmelidir.

## Eşleşme inceleme örneklemi

`scripts/review_catalog_matches.py`, kaynak sorgularında kullanılan katalog
satırlarından eşleşme kuralını incelemek için deterministik, sınırlı bellekli
bir çift örneklemi üretir. Örneklem, mevcut eşleşme eşiklerini sağlayan
adayların yanında eşiklerin yakınındaki zor negatifleri de içerir. Her
boyutun (zaman farkı, büyüklüğe bağlı mesafe oranı, büyüklük farkı ve aynı/
farklı kaynak) kesişimi ayrı bir strata oluşturur. Her strata'da sabit seed
ile rezervuar örneklemesi yapılır; çıktıdaki `review_weight`, o strata'nın
toplam çift sayısını örnek sayısına böler.

```bash
python scripts/review_catalog_matches.py export \
  --input data/processed/expanded_catalog_raw_cache.parquet \
  --output /tmp/catalog-review.csv \
  --samples-per-stratum 20 \
  --seed 20261025
```

`reviewer_label` alanını her satırda tam olarak `match` veya `non_match`
olarak doldurun. Boş ya da farklı bir değerle skor hesabı reddedilir.

```bash
python scripts/review_catalog_matches.py score --input /tmp/catalog-review.csv
```

Skorlar strata ağırlıklarıyla hesaplanır ve **çift düzeyindeki eşik kapısını**
değerlendirir. Nihai `best_first_clusters` küme atamasının precision/recall
skoru değildir. İnceleme zarfı; 60 saniyeden uzun zaman farkı, 300 km'den uzak
çift veya 3.0'dan büyük büyüklük farkı olan çiftleri içermez; dolayısıyla bu
zarfın dışındaki olası kaçırılmış eşleşmelerin recall'ını ölçmez. Eşiklere
yakın çiftleri incelemeye yardımcı olur, fakat hiçbir örneklem otomatik olarak
etiketlenmiş ground truth değildir. İnsan incelemesi olmadan skor modu
kullanılmamalıdır.

Bu araç yalnızca denetim/raporlama içindir. Üretimde kullanılan eşleşme,
kümelendirme veya veri üretme davranışını değiştirmez.
