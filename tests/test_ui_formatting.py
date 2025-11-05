from app.ui.components import apply_friendly_labels, fmt_percent_two_decimals


def test_apply_friendly_labels_returns_new_df():
    import pandas as pd
    df = pd.DataFrame({"context": ["U", "D"], "mc_prob_up": [0.1, 0.2]})
    labels = {
        "context": "Context",
        "mc_prob_up": "Probability: Up",
    }
    out = apply_friendly_labels(df, labels)
    assert out is not df
    assert "Context" in out.columns and "Probability: Up" in out.columns
    # original unchanged
    assert "context" in df.columns and "mc_prob_up" in df.columns


essential_values = [0, 0.1234, 1, None, "invalid"]

def test_fmt_percent_two_decimals_strings():
    outs = [fmt_percent_two_decimals(x) for x in essential_values]
    for s in outs:
        assert isinstance(s, str)
        assert s.endswith("%")
    # spot check 12.34%
    assert fmt_percent_two_decimals(0.1234).startswith("12.34")

