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

echo "== 1/11: USGS kataloğu =="
python scripts/download_usgs.py

echo "== 2/11: EMSC/ISC ile genişletme ve deduplikasyon =="
python scripts/expand_catalog.py

echo "== 3/11: KOERI istasyon listesi (+ kanal bazlı zaman aralıkları) =="
python scripts/fetch_orfeus_eida.py

echo "== 4/11: Zemin sınıfı (Vs30) =="
python scripts/fetch_vs30.py

echo "== 5/11: Dalga formu toplu indirme =="
python scripts/fetch_waveforms_bulk.py

echo "== 6/11: Sinyal öznitelikleri, mühendislik metrikleri ve kalite kontrolü =="
python scripts/enrich_waveforms.py

echo "== 7/11: ISC uzman P/S pick'leri (opsiyonel, atlanabilir) =="
python scripts/fetch_isc_picks.py

echo "== 8/11: Olay-istasyon tablosu (event-station) =="
python scripts/build_event_station_table.py

echo "== 9/11: Veri setini birleştir =="
python scripts/build_dataset.py

echo "== 10/11: Doğrulama =="
python scripts/validate_dataset.py

echo "== 11/11: ML benchmark bölmeleri =="
python scripts/build_benchmarks.py

echo
echo "Tamamlandı. Sonuç: data/processed/turkiye_deprem_veriseti_v3.parquet + benchmarks/"
