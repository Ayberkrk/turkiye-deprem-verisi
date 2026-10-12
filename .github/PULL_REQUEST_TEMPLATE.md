## Ne değişti

<!-- Değişikliği ve nedenini anlat. İlgili issue varsa bağla, ör. "Fixes #12". -->

## Nasıl doğrulandı

<!--
Bir hata düzeltmesiyse hatayı gösteren reprodüksiyonu ve düzeltmeden
sonraki sonucu yaz. Sayısal/fiziksel bir hesaplama için kullanılan
referansı (kapalı form çözüm, başka bir yazılım) ve toleransı belirt.
-->

## Kontrol listesi

- [ ] `python -m pytest tests/ -v` yerelde geçiyor
- [ ] Değişiklik için test eklendi ya da güncellendi
- [ ] Veri üreten bir script değiştiyse `python scripts/quick_check.py` ve `python scripts/validate_dataset.py` geçiyor
- [ ] Yeni bir veri kaynağı eklendiyse `DATA_CARD.md` ve `LICENSE-DATA.md` güncellendi
- [ ] Kullanıcıyı etkileyen değişiklik `CHANGELOG.md`'ye eklendi
