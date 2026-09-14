# Benchmark Görevleri

`scripts/build_benchmarks.py` tarafından `benchmarks/` altında üretilen,
üç görev için resmi train/val/test bölmeleri. Amaç: veri setini "burada
veri var" seviyesinden çıkarıp, farklı modellerin aynı bölmeler üzerinde
adil biçimde karşılaştırılabildiği bir zemine taşımak.

## Bölme yöntemi (çok önemli)

Bölme HER ZAMAN olay (`event_id`) bazlıdır. Aynı depremin farklı
istasyonlardaki kayıtları asla train ve test arasında bölünmez - aksi
halde model aynı depremi başka bir açıdan zaten görmüş olur ve test
skoru gerçekte olduğundan iyi çıkar (data leakage). Bölme, `event_id`'nin
MD5 hash'ine dayalı deterministik bir kurala göre yapılıyor: aynı olay
her zaman aynı bölmeye düşer, veri setine yeni olay eklendiğinde
mevcutların bölmesi değişmez. Oranlar: %70 train, %15 val, %15 test.

## 1. ground_motion

**Girdi**: büyüklük, mesafe (episantr + hiposantr), Vs30, NEHRP zemin sınıfı
**Hedef**: PGA, PGV, Sa(0.1/0.2/0.5/1.0/2.0s), Arias intensity, CAV,
anlamlı sarsıntı süresi (D5-95)

Sadece `usable_for_engineering=True` (güçlü hareket sensöründen gelen,
kritik QC sorunu olmayan) kayıtlar kullanılıyor - broadband'den düşülmüş
PGA değerleri bu görevde YOK.

`benchmarks/ground_motion/{train,val,test}.csv` yanında iki ileri seviye
holdout da üretiliyor:

- **`holdout_by_station/`**: bölme istasyon bazlı yapılıyor - bir
  istasyonun TÜM kayıtları tek bir bölmede kalıyor. Modelin hiç
  görmediği bir istasyona (yani bilmediği bir Vs30/zemin koşuluna)
  genelleyip genelleyemediğini test eder.
- **`holdout_by_time/`**: 2022-01-01 öncesi train, sonrası test. Modelin
  geleceğe genelleyip genelleyemediğini test eder. **Bilinen dengesizlik**:
  gerçek dalga formu arşivinin büyük kısmı 2020 sonrası (özellikle 2023
  Kahramanmaraş depremi dizisi) yoğunlaştığı için bu bölmede test seti
  train'den büyük çıkıyor (train≈625, test≈1544). Bu, arşivin doğal
  zaman dağılımını yansıtıyor.

## 2. phase_picking

**Girdi**: dalga formu dosyası
**Hedef**: P ve S varış zamanı

**DÜRÜSTLÜK NOTU**: `p_pick_time`/`s_pick_time` otomatik STA/LTA ile
üretilmiştir (S için ayrıca sezgisel bir yöntemle). Bu **ground-truth bir
benchmark değildir** - sadece aynı otomatik etiketlerle farklı modelleri
tutarlı bir şekilde karşılaştırmak isteyenler için bir bölme sağlar.

`data/processed/isc_analyst_picks.csv` dosyasında, ISC Bulletin'den
çekilmiş, uzman tarafından doğrulanmış (analyst-reviewed) gerçek pick'ler
de bulunuyor (bkz. `scripts/fetch_isc_picks.py`) - bunlar mevcut olduğu
olaylar için gerçek bir ground-truth sağlıyor. Bu dosya, otomatik
pick'lerle karşılaştırma/doğrulama için ayrıca kullanılabilir; tüm
olayları kapsamaz (ISC Bulletin'in nihai hale gelmesi aylar sürebiliyor,
her olay ISC'ye bildirilmiş olmayabilir).

## 3. early_warning

**Girdi**: P varışından sonraki ilk 1/3/5/10 saniyelik pencere
**Hedef**: Mw (mw_estimate)

Pencereler ÖNCEDEN KESİLİP diske kopyalanmıyor (aynı verinin 4 kopyası
depolamak anlamına gelirdi). Bunun yerine her satırda dosya yolu +
`p_pick_time` veriliyor; kesme işlemi kullanıcı tarafında yapılır:

```python
from obspy import read, UTCDateTime
st = read(dosya_yolu)
p_time = UTCDateTime(p_pick_time)
pencere = st.slice(p_time, p_time + 3)  # ilk 3 saniye
```

## Referans (baseline) sonuç

`notebooks/02_ground_motion_baseline.py`, `ground_motion` bölmeleri
üzerinde ek bağımlılık gerektirmeyen basit bir zayıflama (attenuation)
modeli eğitip test ediyor: `log10(PGA_g)`, büyüklük + `log10(hiposantral
mesafe)` + `log10(Vs30)`'un doğrusal bir fonksiyonu olarak modelleniyor
(kapalı-form en küçük kareler, `numpy.linalg.lstsq`). Amaç, split'lerin
gerçekten anlamlı bir sinyal taşıdığını göstermek ve yeni gelenlere bir
kıyas noktası vermek - yayın kalitesinde bir GMPE değildir.

```
python notebooks/02_ground_motion_baseline.py
```

Güncel sonuç (test bölmesi): RMSE(log10 g) ≈ 0.42 (yaklaşık 2.6x'lik bir
faktör hatası), R² ≈ 0.66 - sadece train ortalamasını tahmin eden naif
bir modelin RMSE'sinden (≈0.72) belirgin şekilde düşük. Bu, üç değişkenli
basit bir doğrusal modelin bile PGA'nın büyük kısmını açıklayabildiğini,
yani split'lerin öğrenilebilir bir ilişki taşıdığını gösteriyor.

## Sınırlamalar

- Bölme oranları küçük görev boyutları için (özellikle `holdout_by_station`
  gibi) tam %70/15/15 tutmayabilir - hash bazlı yöntem, tam sayıda değil
  olasılıksal bir denge sağlar.
- `ground_motion` görevindeki hedefler arasında güçlü bir korelasyon var
  (PGA ile Sa(0.1s) gibi); bu fiziksel olarak beklenen bir durumdur, veri
  hatası değildir.
