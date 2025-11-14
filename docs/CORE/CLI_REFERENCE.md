# CLI Reference

This reference captures typical command patterns and expected effects. Where commands are not present, prefer the scripts under `scripts/` and consult `developer_commands_cheatsheet.md`.

Note: If `cli/mie.py` is not present, use the `scripts/*.sh` or Python scripts under `scripts/` to perform rebuilds and validations.

## Features

- Build features (full):
```
python scripts/rebuild_all_from_scratch.py
# Or
python scripts/rebuild_all_analytics.py
```

- Update features (lookback):
```
python scripts/rebuild_all_analytics.py --lookback 90
```

## Markov

- Ensure Markov matrices available for a ticker and window (if a coordinating script exists):
```
python scripts/rebuild_all_analytics.py --markov-only --tickers SPY --windows 1Y 2Y 5Y
```

- List produced matrices:
```
ls data/analytics/markov/SPY/matrices/*/*/2Y*
```

## HMM

- Build standardized HMM paths if a script exists in `scripts/`:
```
python scripts/rebuild_all_analytics.py --hmm-only --tickers SPY --windows 5 --states 2
```

## Seasonality

- Build seasonality base per ticker if a script exists:
```
python scripts/fix_seasonality_schema.py --rebuild SPY QQQ
python scripts/check_seasonality_integrity.py
```

## Validation

- Data integrity:
```
python scripts/check_data_integrity.py
```

- Seasonality alignment:
```
python scripts/validate_seasonality_alignment.py
```

## Streamlit

- Multipage app:
```
streamlit run app/Home.py
```

- Individual pages:
```
streamlit run app/pages/01_Markov_Chain.py
```

