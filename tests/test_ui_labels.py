from app.ui.theme import get_metric_labels


def test_get_metric_labels_smoke():
    labels = get_metric_labels()
    assert isinstance(labels, dict)
    assert "hmm_prob_bull" in labels
    assert labels["hmm_prob_bull"].lower().startswith("bull")

