from pathlib import Path
import pandas as pd
import json

from mie_lib.ui.components import read_parquet_safe, read_csv_safe, read_json_safe, fmt_percent_one_decimal


def test_offline_loaders_and_formatter(tmp_path):
    # Create a tiny parquet/csv/json and ensure loaders work
    p = tmp_path / "x.parquet"
    df = pd.DataFrame({"a": [1, 2]})
    df.to_parquet(p, index=False)
    out = read_parquet_safe(p)
    assert out is not None and "a" in out.columns

    c = tmp_path / "y.csv"
    df.to_csv(c, index=False)
    out2 = read_csv_safe(c)
    assert out2 is not None and "a" in out2.columns

    j = tmp_path / "z.json"
    j.write_text(json.dumps({"k": 1}))
    out3 = read_json_safe(j)
    assert out3 == {"k": 1}

    # Formatter
    assert fmt_percent_one_decimal(0.471) == "47.1%"

