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

# Saf fonksiyon testleri, modül düzeyindeki istemcinin servis keşfine
# bağımlı olmamalı (#34). Gerçek istemci yalnızca import sırasında
# değiştirilir; testlerde ağ yöntemi çağrılırsa boş nesne hata verir.
from importlib import import_module  # noqa: E402
from unittest.mock import patch  # noqa: E402

with patch("obspy.clients.fdsn.Client", return_value=object()):
    for module_name in ("enrich_waveforms", "fetch_waveforms_bulk", "fetch_orfeus_eida"):
        import_module(module_name)
