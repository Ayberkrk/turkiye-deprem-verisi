# Skor Tablosu (Leaderboard)

`benchmarks/` altındaki resmi train/val/test bölmelerinde denenmiş
modellerin sonuçları. Amaç: aynı bölmeler üzerinde farklı yaklaşımları
adil biçimde kıyaslayabilmek.

**Kendi sonucunu eklemek ister misin?** Bir PR aç, aşağıdaki ilgili
tabloya satırını ekle. Skorun tekrar üretilebilir olması için:
- Hangi split (`train`/`val`/`test`) üzerinde ölçüldüğünü belirt (test
  skorları val'e göre daha güvenilir bir kıyas noktasıdır).
- Kısa bir açıklama veya kod linki ekle.
- Mümkünse `docs/benchmarks.md`'deki bölme yöntemini (event bazlı,
  hash'e dayalı) değiştirmeden kullan - farklı bir bölme kullanılan
  sonuçlar bu tabloyla doğrudan kıyaslanamaz.

## ground_motion

**Görev**: büyüklük + mesafe + Vs30 → log10(PGA_g). Metrik: RMSE
(log10 g birimiyle - düşük daha iyi) ve R² (yüksek daha iyi), test
bölmesinde.

| Model | RMSE (log10 g) | R² | Not | Kaynak |
|---|---|---|---|---|
| Naif (train ortalaması) | 0.717 | 0.000 | Girdi kullanmıyor, sadece referans | `notebooks/02_ground_motion_baseline.py` |
| Doğrusal (OLS, 3 öznitelik) | 0.419 | 0.657 | Kapalı-form en küçük kareler, ek bağımlılık yok | `notebooks/02_ground_motion_baseline.py` |
| RandomForest (3 öznitelik) | 0.392 | 0.701 | 200 ağaç, max_depth=8 | `notebooks/03_ground_motion_randomforest.py` |

## phase_picking

Henüz bir model baseline'ı yok - sadece etiketlerin kalitesi ölçüldü
(`scripts/compare_picks_to_isc.py`, bkz. `docs/benchmarks.md`). P-dalgası
için otomatik pick'ler uzman pick'lerinden ortalama 9,3s (medyan 0,6s)
sapıyor; S-dalgası için ortalama 51,6s (medyan 9,5s). Bu sayılar bir
model skoru değil, etiket kalitesinin üst sınırı - bir model bu
etiketlerle eğitilirse, bu hatanın bir kısmını miras alır.

## early_warning

Henüz bir baseline yok. Katkı bekleniyor.
