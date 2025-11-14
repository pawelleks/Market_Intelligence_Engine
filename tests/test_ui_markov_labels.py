from mie_lib.ui.theme import get_metric_labels


def test_metric_labels_have_human_friendly_names():
    labels = get_metric_labels()
    keys = [
        "mc_prob_up_next",
        "mc_prob_neutral_next",
        "mc_prob_down_next",
        "context",
        "mc_prob_up",
        "mc_prob_neutral",
        "mc_prob_down",
    ]
    for k in keys:
        assert k in labels
        assert isinstance(labels[k], str) and len(labels[k]) > 0
    # Spot check exact values per finalized spec
    assert labels["mc_prob_up_next"] == "Probability: Up next"
    assert labels["mc_prob_down"] == "Probability: Down"
    assert labels["context"] == "Context"
