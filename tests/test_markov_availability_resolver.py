from pathlib import Path
import json
from importlib import import_module


def test_availability_resolver_and_cli(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))

    base = tmp_path / "data/analytics/markov/SPY"
    base.mkdir(parents=True, exist_ok=True)
    (base / "matrix_order1.parquet").write_text("parquet")  # sentinel
    (base / "matrix_order3.parquet").write_text("parquet")
    (base / "states.parquet").write_text("parquet")
    meta = {"state_mode": "tri", "threshold_bps": 10, "order": 3}
    (base / "metadata.json").write_text(json.dumps(meta))

    mod = import_module("app.pages.01_Markov_Chain")
    avail = mod._resolve_available_markov(base)
    assert set(avail["orders"]) == {1,3}
    assert avail["state_mode"] == "tri"
    assert avail["threshold_bps"] == 10

    cmd = mod._build_cli_for_combo("SPY", 2, "tri", 10)
    assert cmd.strip().startswith("python cli/mie.py build-markov --ticker SPY --order 2 --state-mode tri --threshold-bps 10")

