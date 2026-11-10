"""
`scripts/` dizinindeki modüller bir paket değil, bağımsız script'ler
(build_event_station_table.py'nin build_dataset.py'yi import etme
yönteminin aynısı - bkz. o dosyadaki sys.path.insert). Testlerin de
aynı script'leri doğrudan import edebilmesi için scripts/ dizinini
sys.path'e ekliyoruz.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
