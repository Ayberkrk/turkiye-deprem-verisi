"""
scripts/export_hf_parquet.py: bölmeler arası şema hizalaması.
"""
import pandas as pd

from export_hf_parquet import aligned_split_frames, to_parquet_frame


def test_all_null_column_becomes_string_instead_of_null_type():
    df = to_parquet_frame(pd.DataFrame({"location": [None, None], "pga_g": [0.1, 0.2]}))
    assert str(df["location"].dtype) == "string"
    assert df["pga_g"].dtype == float


def test_splits_share_schema_when_a_column_is_empty_in_one_split():
    # Küçük bir test bölmesinde s_pick_time tamamen boş olabilir; pandas
    # onu float okur, train'de ise metindir. Hizalanmazsa Hugging Face
    # bölmeleri tek bir veri seti olarak yükleyemez.
    frames = aligned_split_frames(
        {
            "train": pd.DataFrame({"s_pick_time": ["2023-02-06T01:17:40Z", None], "n": [1, 2]}),
            "test": pd.DataFrame({"s_pick_time": [float("nan")], "n": [3]}),
        }
    )
    assert str(frames["train"]["s_pick_time"].dtype) == str(frames["test"]["s_pick_time"].dtype) == "string"
    assert frames["test"]["n"].dtype == frames["train"]["n"].dtype
