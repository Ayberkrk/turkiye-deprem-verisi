"""
Deduplikasyon öncesi olay kimliklerini, hayatta kalan temsilci kimliğe
eşleyen ortak yardımcılar.

Neden gerekli: dalga formu dosyaları ve indirme günlüğü, indirildikleri
andaki olay kimliğiyle diskte duruyor. Deduplikasyon yeniden
çalıştırıldığında (ör. yöntem iyileştirildiğinde) o kimlik artık başka
bir kümenin üyesi olabilir; hangi kaynaktan geldiğine bakılmaksızın
temsilciye eşlenmezse aynı deprem iki ayrı olay gibi görünür.
"""
import pandas as pd


def representative_id_lookup(id_map: pd.DataFrame) -> pd.Series:
    """event_id_cluster_map.csv içeriğinden, kaynak olay kimliği ->
    temsilci kimlik eşlemesi (tüm kaynaklar için)."""
    return id_map.drop_duplicates("source_event_id").set_index("source_event_id")["representative_event_id"]


def remap_to_representative(df: pd.DataFrame, lookup, column: str = "event_id") -> pd.DataFrame:
    """df[column]'u temsilci kimliğe çevirir; eşlemede olmayan kimlikler
    olduğu gibi kalır. lookup None ise df değişmeden döner."""
    if lookup is None:
        return df
    df = df.copy()
    df[column] = df[column].map(lookup).fillna(df[column])
    return df


def collapse_duplicate_station_records(table: pd.DataFrame, original_id_column: str) -> pd.DataFrame:
    """Aynı (event_id, station) için birden fazla kayıt varsa tek satıra
    indirir. Aynı deprem birden fazla kaynak kimliğiyle indirilmişse
    eşleme sonrası aynı çift iki kez görünür; aynı dalga formunu iki
    ayrı kayıt gibi saymamak için biri tutulur. Penceresi temsilci
    olayın origin zamanına göre kesilmiş olan (dosya kimliği temsilciyle
    aynı) tercih edilir."""
    is_representative_file = table[original_id_column] == table["event_id"]
    order = (~is_representative_file).astype(int)
    ordered = table.assign(_order=order).sort_values("_order", kind="stable")
    return ordered.drop_duplicates(["event_id", "station"]).drop(columns="_order").sort_index()
