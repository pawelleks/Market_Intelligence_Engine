from pathlib import Path


def test_project_scaffold_files_exist():
    expected = [
        "src/data_ingest/__init__.py",
        "src/data_clean/__init__.py",
        "src/features/__init__.py",
        "src/analytics/markov/__init__.py",
        "src/analytics/hmm/__init__.py",
        "src/analytics/seasonality/__init__.py",
        "src/signals/__init__.py",
        """src/utils/config.py""",
        "src/utils/logging.py",
        "src/utils/io.py",
        "cli/mie.py",
        "config/tickers.yml",
        "config/features.yml",
        "config/parameters.yml",
        "tests/test_skeleton.py",
        "README.md",
        "requirements.txt",
    ]
    for p in expected:
        assert Path(p).exists(), f"Missing {p}"


def test_trivial_true():
    assert True

