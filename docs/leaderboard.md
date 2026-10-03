# Skor Tablosu (Leaderboard)

`benchmarks/` altındaki resmi train/val/test bölmelerinde denenmiş
modellerin sonuçları. Amaç: aynı bölmeler üzerinde farklı yaklaşımları
adil biçimde kıyaslayabilmek.

**Kendi sonucunu eklemek ister misin?** Bir PR aç, aşağıdaki ilgili
tabloya satırını ekle. Skorun tekrar üretilebilir olması için:
- Hangi split (`train`/`val`/`test`) üzerinde ölçüldüğünü belirt (test
  skorları val'e göre daha güvenilir bir kıyas noktasıdır).
- Kısa bir açıklama veya kod linki ekle.
- Mümkünse `docs/benchmarks.md`'deki bölme yöntemini (olay grubu bazlı,
  hash'e dayalı) değiştirmeden kullan - farklı bir bölme kullanılan
  sonuçlar bu tabloyla doğrudan kıyaslanamaz.

## ground_motion

**Görev**: büyüklük + mesafe + Vs30 → log10(PGA_g), hedef yönelimden
bağımsız yatay PGA (`pga_rotd50_g`; v5.9 öncesi satırlar tek bileşenli
`pga_g` üzerindeydi ve bu tabloyla kıyaslanamaz). Metrik: RMSE
(log10 g birimiyle - düşük daha iyi) ve R² (yüksek daha iyi), test
bölmesinde.

| Model | RMSE (log10 g) | R² | Not | Kaynak |
|---|---|---|---|---|
| Naif (train ortalaması) | 0.727 | 0.000 | Girdi kullanmıyor, sadece referans | `notebooks/02_ground_motion_baseline.py` |
| Doğrusal (OLS, 3 öznitelik) | 0.418 | 0.669 | Kapalı-form en küçük kareler, ek bağımlılık yok | `notebooks/02_ground_motion_baseline.py` |
| Akkar vd. (2014), uydurma yok | 0.456 | - | Yayınlanmış GMPE, bu veriyle kalibre edilmedi; yalnızca Mw'si olan 169 test kaydında ve `pga_geomean_g` üzerinde, diğer satırlarla doğrudan kıyaslanamaz (aynı 169 satırda doğrusal model 0.387). Yanlılık -0.238, bkz. `docs/benchmarks.md` | `notebooks/07_gmpe_comparison.py` |
| RandomForest (3 öznitelik) | 0.398 | 0.699 | 200 ağaç, max_depth=8 | `notebooks/03_ground_motion_randomforest.py` |

## phase_picking

**Görev**: dalga formu -> P/S varış zamanı. Metrik: ortalama/medyan
mutlak zamanlama hatası (saniye, düşük daha iyi), ISC uzman pick'iyle
eşleşen (sınırlı) alt kümede, test bölmesinde.

| Model | P ortalama (medyan) | S ortalama (medyan) | Not | Kaynak |
|---|---|---|---|---|
| Otomatik STA/LTA pick'in kendisi (model yok) | 6.4s (0.63s) | 52.4s (43.3s) | n=25 P / 10 S eşleşme (test); eğitilmiş bir model değil, mevcut etiketin split üzerindeki hata payı | `notebooks/04_phase_picking_baseline.py` |

Genel (split'e kısıtlanmamış, tüm eşleşmeler) etiket kalitesi ölçümü için
`scripts/compare_picks_to_isc.py` ve `docs/benchmarks.md`'ye bakın: P-dalgası
için otomatik pick'ler uzman pick'lerinden ortalama 9,3s (medyan 0,6s)
sapıyor; S-dalgası için ortalama 51,6s (medyan 9,5s). Bu sayılar bir
model skoru değil, etiket kalitesinin üst sınırı - bir model bu
etiketlerle eğitilirse, bu hatanın bir kısmını miras alır.

## early_warning

**Görev**: P varışından sonraki 1/3/5/10 saniyelik pencere -> Mw. Metrik:
MAE (Mw biriminde, düşük daha iyi), test bölmesinde.

| Model | 1s | 3s | 5s | 10s | Not | Kaynak |
|---|---|---|---|---|---|---|
| Naif (train ortalaması) | 0.387 | 0.387 | 0.387 | 0.387 | Girdi kullanmıyor, sadece referans | `notebooks/05_early_warning_baseline.py` |
| log10(Pd) + log10(R) - OLS | 0.344 | 0.313 | 0.298 | 0.280 | Cihaz tepkisi çıkarılmış düşey tepe yer değiştirme + hiposantral mesafe; aynı satırlarda naif 0.394 | `notebooks/06_early_warning_pd_baseline.py` |
| log10(ham tepe genlik) - OLS | 0.383 | 0.376 | 0.373 | 0.381 | Kapalı-form en küçük kareler, cihaz tepkisi çıkarılmamış ham genlik (bkz. `docs/benchmarks.md` sınırlaması) | `notebooks/05_early_warning_baseline.py` |
