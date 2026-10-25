#!/usr/bin/env bash
# Tüm pipeline'ı sırayla çalıştırır: veri indirme, birleştirme, zenginleştirme,
# doğrulama. Sanal ortamın zaten aktif olduğu varsayılır.
#
# Kullanım:
#   source venv/bin/activate
#   bash scripts/run_all.sh
#   bash scripts/run_all.sh --skip-isc-picks
#
# Not: fetch_waveforms_bulk.py adımı ~1-2 saat sürebilir (KOERI'nin açık
# servisine saygılı bir hızda ilerliyor). Sabırlı olun.

set -e

skip_isc_picks=false

usage() {
    echo "Kullanım: bash scripts/run_all.sh [--skip-isc-picks]"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-isc-picks)
            skip_isc_picks=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Bilinmeyen argüman: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

echo "== 1/12: USGS kataloğu =="
python scripts/download_usgs.py

echo "== 2/12: EMSC/ISC ile genişletme ve deduplikasyon =="
python scripts/expand_catalog.py

echo "== 3/12: KOERI istasyon listesi (+ kanal bazlı zaman aralıkları) =="
python scripts/fetch_orfeus_eida.py

echo "== 4/12: Zemin sınıfı (Vs30) =="
python scripts/fetch_vs30.py

echo "== 5/12: Dalga formu toplu indirme =="
python scripts/fetch_waveforms_bulk.py

echo "== 6/12: Sinyal öznitelikleri, mühendislik metrikleri ve kalite kontrolü =="
python scripts/enrich_waveforms.py

echo "== 7/12: ISC uzman P/S pick'leri (opsiyonel) =="
if [[ "$skip_isc_picks" == true ]]; then
    echo "ISC uzman P/S pick'leri --skip-isc-picks ile atlandı."
else
    python scripts/fetch_isc_picks.py
fi

echo "== 8/12: Olay-istasyon tablosu (event-station) =="
python scripts/build_event_station_table.py

echo "== 9/12: Veri setini birleştir =="
python scripts/build_dataset.py

echo "== 10/12: ML benchmark bölmeleri =="
python scripts/build_benchmarks.py

echo "== 11/12: Doğrulama =="
python scripts/validate_dataset.py

echo "== 12/12: Kaynak kökeni ve çıktı hash manifesti =="
if [[ "$skip_isc_picks" == true ]]; then
    python scripts/build_provenance.py --skip-isc-picks
else
    python scripts/build_provenance.py
fi

echo
echo "Tamamlandı. Sonuç: data/processed/turkiye_deprem_veriseti_v3.parquet + benchmarks/"
