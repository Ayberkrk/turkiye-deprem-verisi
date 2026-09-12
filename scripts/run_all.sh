#!/usr/bin/env bash
# Tüm pipeline'ı sırayla çalıştırır: veri indirme, birleştirme, zenginleştirme,
# doğrulama. Sanal ortamın zaten aktif olduğu varsayılır.
#
# Kullanım:
#   source venv/bin/activate
#   bash scripts/run_all.sh
#
# Not: fetch_waveforms_bulk.py adımı ~1-2 saat sürebilir (KOERI'nin açık
# servisine saygılı bir hızda ilerliyor). Sabırlı olun.

set -e

echo "== 1/8: USGS kataloğu =="
python scripts/download_usgs.py

echo "== 2/8: EMSC/ISC ile genişletme ve deduplikasyon =="
python scripts/expand_catalog.py

echo "== 3/8: KOERI istasyon listesi =="
python scripts/fetch_orfeus_eida.py

echo "== 4/8: Zemin sınıfı (Vs30) =="
python scripts/fetch_vs30.py

echo "== 5/8: Dalga formu toplu indirme =="
python scripts/fetch_waveforms_bulk.py

echo "== 6/8: Sinyal öznitelikleri (PGA/PGV/SNR/faz) =="
python scripts/enrich_waveforms.py

echo "== 7/8: Veri setini birleştir =="
python scripts/build_dataset.py

echo "== 8/8: Doğrulama =="
python scripts/validate_dataset.py

echo
echo "Tamamlandı. Sonuç: data/processed/turkiye_deprem_veriseti_v3.parquet"
