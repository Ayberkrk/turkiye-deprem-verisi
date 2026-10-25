import pandas as pd
import pytest

from review_catalog_matches import export_review_sample, score_review_file


@pytest.fixture
def raw_catalog(tmp_path):
    path = tmp_path / "catalog.csv"
    pd.DataFrame(
        [
            {
                "source": "usgs", "source_event_id": "a", "time_utc": "2020-01-01T00:00:00Z",
                "latitude": 38.0, "longitude": 37.0, "magnitude": 5.0,
            },
            {
                "source": "isc", "source_event_id": "b", "time_utc": "2020-01-01T00:00:01Z",
                "latitude": 38.0, "longitude": 37.0, "magnitude": 5.0,
            },
            {
                "source": "emsc", "source_event_id": "c", "time_utc": "2020-01-01T00:00:05Z",
                "latitude": 38.2, "longitude": 37.0, "magnitude": 5.1,
            },
            {
                "source": "usgs", "source_event_id": "d", "time_utc": "2020-01-01T00:00:08Z",
                "latitude": 38.0, "longitude": 37.0, "magnitude": 5.0,
            },
        ]
    ).to_csv(path, index=False)
    return path


def test_export_is_deterministic_and_leaves_labels_blank(raw_catalog, tmp_path):
    first = export_review_sample(raw_catalog, tmp_path / "first.csv", samples_per_stratum=2, seed=7)
    second = export_review_sample(raw_catalog, tmp_path / "second.csv", samples_per_stratum=2, seed=7)

    pd.testing.assert_frame_equal(first, second)
    assert first["reviewer_label"].eq("").all()
    assert set(first["predicted_label"]).issubset({"match", "non_match"})
    assert (first["review_weight"] > 0).all()
    assert first["stratum"].str.contains("same_source").any()


def test_export_caps_sample_per_stratum_and_records_population(raw_catalog, tmp_path):
    sample = export_review_sample(raw_catalog, tmp_path / "review.csv", samples_per_stratum=1)

    assert sample.groupby("stratum").size().max() == 1
    assert (sample["stratum_population"] >= sample["stratum_sample_size"]).all()
    assert sample["review_weight"].tolist() == sample["stratum_population"].tolist()


def test_score_uses_stratum_weights_for_precision_recall_f1(tmp_path):
    path = tmp_path / "adjudicated.csv"
    pd.DataFrame(
        {
            "predicted_label": ["match", "match", "non_match", "non_match"],
            "reviewer_label": ["match", "non_match", "match", "non_match"],
            "review_weight": [2, 1, 3, 1],
        }
    ).to_csv(path, index=False)

    result = score_review_file(path)

    assert result["weighted_true_positive"] == 2
    assert result["weighted_false_positive"] == 1
    assert result["weighted_false_negative"] == 3
    assert result["precision"] == pytest.approx(2 / 3)
    assert result["recall"] == pytest.approx(2 / 5)
    assert result["f1"] == pytest.approx(0.5)
    assert "threshold-gate" in result["metric_scope"]


@pytest.mark.parametrize("labels", [["match", ""], ["match", "maybe"]])
def test_score_rejects_blank_or_unknown_reviewer_labels(tmp_path, labels):
    path = tmp_path / "bad.csv"
    pd.DataFrame(
        {"predicted_label": ["match", "non_match"], "reviewer_label": labels, "review_weight": [1, 1]}
    ).to_csv(path, index=False)

    with pytest.raises(ValueError, match="reviewer_label"):
        score_review_file(path)


def test_export_rejects_missing_and_invalid_catalog_fields(tmp_path):
    missing = tmp_path / "missing.csv"
    pd.DataFrame({"source": ["usgs"]}).to_csv(missing, index=False)
    with pytest.raises(ValueError, match="Eksik zorunlu"):
        export_review_sample(missing, tmp_path / "out.csv")

    invalid = tmp_path / "invalid.csv"
    pd.DataFrame(
        {"source": ["usgs"], "source_event_id": ["x"], "time_utc": ["not-a-date"],
         "latitude": [38], "longitude": [37], "magnitude": [5]}
    ).to_csv(invalid, index=False)
    with pytest.raises(ValueError, match="geçerli"):
        export_review_sample(invalid, tmp_path / "out.csv")


def test_score_rejects_missing_prediction_and_nonpositive_weight(tmp_path):
    path = tmp_path / "bad-score.csv"
    pd.DataFrame(
        {"predicted_label": [None], "reviewer_label": ["match"], "review_weight": [0]}
    ).to_csv(path, index=False)

    with pytest.raises(ValueError, match="predicted_label"):
        score_review_file(path)
