# Katkıda Bulunma

Bu depoya kod (script/düzeltme) veya yeni bir veri kaynağı eklemek
istiyorsanız aşağıdaki kontrol listesini takip edin.

## Kod değişikliği / bug düzeltmesi

1. Değişikliğinizi yapmadan önce, mümkünse önce hatayı **doğrulayın**
   (crash'i veya yanlış sonucu gösteren küçük bir reprodüksiyon).
2. Testleri çalıştırın:

   ```bash
   pip install -r requirements-dev.txt
   python -m pytest tests/ -v
   ```

3. `scripts/` altındaki saf (dosya sistemi/ağ gerektirmeyen) fonksiyonlar
   için mümkünse `tests/` altına bir birim test ekleyin - özellikle
   sayısal/fiziksel bir hesaplama düzeltiyorsanız (bkz.
   `tests/test_enrich_waveforms.py`'deki analitik doğrulama örnekleri).
4. Veri üreten bir script'i değiştirdiyseniz, ilgili script'i çalıştırıp
   çıktının değiştiğini/değişmediğini kontrol edin, ardından:

   ```bash
   python scripts/validate_dataset.py
   ```

   ile veri setinin bütünlük/tutarlılık kontrolünden geçtiğinden emin
   olun.
5. Kod tabanının kendi yorum/docstring stiline uyun (Türkçe, teknik
   gerekçe içeren, "neden" açıklayan yorumlar - "ne yaptığını" değil).

## Yeni bir açık veri kaynağı ekleme

Önce `LICENSE-DATA.md`'ye bakıp lisans uyumluluğunu kontrol edin -
özellikle **share-alike/copyleft** lisanslı kaynaklara dikkat edin (bkz.
ISC-GEM örneği, `LICENSE-DATA.md`'de neden ham olarak dahil edilmediği
açıklanıyor). Yeni kaynağı ekledikten sonra `DATA_CARD.md` ve
`LICENSE-DATA.md`'yi güncelleyin.

## Skor tablosuna (leaderboard) katkı

`benchmarks/` üzerinde kendi modelini denedin mi? `docs/leaderboard.md`'ye
bir PR ile satırını ekleyebilirsin - format ve tekrar-üretilebilirlik
kuralları o dosyada.

## GitHub Actions

Her push/PR'da `.github/workflows/tests.yml` çalışır: birim testler ve
`scripts/validate_dataset.py`. PR açmadan önce bunların yerelde
geçtiğinden emin olmak, CI'da sürpriz kırmızı çekten kaçınmanın en
kolay yolu.

## Commit mesajları

Kısa, açıklayıcı, Türkçe (depo Türkçe yazıldığı için) ve neden'i
anlatan bir özetle başlayın. AI/asistan araçlarına referans veya
"Co-Authored-By" satırı eklemeyin.
