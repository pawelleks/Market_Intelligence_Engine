import re
from pathlib import Path

from app.ui.theme import color_for_status, mpl_palette_for_prob, plotly_palette_for_prob


def test_no_inline_hex_outside_theme():
    root = Path("app")
    hex_re = re.compile(r"#([0-9a-fA-F]{6})")
    for p in root.rglob("*.py"):
        if p.name == "theme.py":
            continue
        s = p.read_text()
        hits = [m.group(0) for m in hex_re.finditer(s)]
        assert len(hits) == 0, f"Inline hex colors found in {p}: {hits[:5]}"


def test_color_for_status_mapping():
    # These rely on theme tokens being present
    assert isinstance(color_for_status("bull"), str)
    assert color_for_status("bull") == color_for_status("up")
    assert color_for_status("bear") == color_for_status("error")
    assert color_for_status("neutral") == color_for_status("info")


def test_prob_palettes_default_order():
    mpl = mpl_palette_for_prob()
    pl = plotly_palette_for_prob()
    assert len(mpl) == 3 and len(pl) == 3
    assert mpl == pl

