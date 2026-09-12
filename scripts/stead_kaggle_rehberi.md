# STEAD'den Türkiye Alt-Kümesini Çıkarma (Kaggle Rehberi)

STEAD veri seti (~85GB) bu bilgisayara indirilemeyecek kadar büyük. Bu adımı
**Kaggle'ın kendi ücretsiz bulut ortamında** çalıştırıp, sonucunda ortaya çıkan
küçük Türkiye alt-kümesini indireceğiz. Kaggle notebook'u veriyi kendi
sunucusunda barındırır, hiçbir şey bilgisayara inmez, sadece sonuç iner.

## Adımlar

1. [kaggle.com/datasets/isevilla/stanford-earthquake-dataset-stead](https://www.kaggle.com/datasets/isevilla/stanford-earthquake-dataset-stead) sayfasına git, ücretsiz Kaggle hesabınla giriş yap.
2. Sağ üstten **"New Notebook"** ile bu veri setine bağlı bir notebook aç (veri otomatik olarak `/kaggle/input/` altında hazır gelir, indirme gerekmez).
3. Aşağıdaki kodu bir hücreye yapıştırıp çalıştır:

```python
import pandas as pd
import h5py

# 1) Önce SADECE metadata CSV'yi oku (küçük, birkaç yüz MB) - waveform'lara henüz dokunmuyoruz
meta = pd.read_csv("/kaggle/input/stanford-earthquake-dataset-stead/metadata.csv")

# 2) Türkiye'nin kabaca sınırları içine düşen istasyon/olayları filtrele
turkiye = meta[
    (meta["receiver_latitude"].between(35.0, 43.0)) &
    (meta["receiver_longitude"].between(25.0, 45.5))
]
print(f"Türkiye'ye düşen kayıt sayısı: {len(turkiye)}")

turkiye.to_csv("/kaggle/working/stead_turkiye_metadata.csv", index=False)

# 3) Eğer sonuç boş DEĞİLSE, sadece bu satırların waveform'larını dev HDF5'ten çek
if len(turkiye) > 0:
    with h5py.File("/kaggle/input/stanford-earthquake-dataset-stead/merged.hdf5", "r") as f:
        with h5py.File("/kaggle/working/stead_turkiye_waveforms.hdf5", "w") as out:
            for trace_name in turkiye["trace_name"]:
                out.create_dataset(trace_name, data=f["data"][trace_name][:])
    print("Türkiye waveform alt-kümesi hazır: /kaggle/working/stead_turkiye_waveforms.hdf5")
else:
    print("STEAD'de Türkiye kapsamında kayıt bulunamadı, bu kaynak atlanabilir.")
```

4. Notebook'u çalıştır, **"Output"** sekmesinden `stead_turkiye_metadata.csv` ve
   (varsa) `stead_turkiye_waveforms.hdf5` dosyalarını indir.
5. İndirdiğin dosyaları bu projenin `data/processed/` klasörüne koy.

## Beklenti konusunda dürüst not

STEAD'in istasyon ağı ağırlıklı olarak küresel/ABD kaynaklı olduğu için
Türkiye kapsamı **az veya sıfır çıkabilir**. Bu normal, çünkü STEAD bu
projenin çekirdeği değil, varsa bonus bir katman. Asıl omurga zaten
`fetch_orfeus_eida.py` (KOERI'nin kendi ağı) ve `download_usgs.py`.
