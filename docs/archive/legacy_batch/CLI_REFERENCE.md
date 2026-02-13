# CLI Reference

This reference captures typical command patterns for the `mie_lib` CLI.
All commands should be run as a module: `python -m mie_lib.cli.mie <command>`.

## Main Pipelines

- **Rebuild Everything (Full Reset)**
  Destroys (or overwrites) features and analytics with a fresh build.
  ```bash
  python -m mie_lib.cli.mie rebuild-everything
  ```

- **Update Everything (Daily)**
  Incremental update of raw data, features, and analytics (Markov, HMM).
  ```bash
  python -m mie_lib.cli.mie update-everything
  ```

## Individual Modules

### Features
- Update features (incremental):
  ```bash
  python -m mie_lib.cli.mie build-features --mode update --lookback 90
  ```

### Markov
- Build specific Markov output:
  ```bash
  python -m mie_lib.cli.mie build-markov --ticker SPY --state-mode tri --threshold-bps 10 --order 2 --window 1Y
  ```
- Build Grid (Batch):
  ```bash
  python -m mie_lib.cli.mie build-markov-grid --tickers SPY,QQQ
  ```

### HMM
- Build HMM (Standardized):
  ```bash
  python -m mie_lib.cli.mie build-hmm --ticker SPY --states 2 --window-years 5
  ```

### Seasonality
- Build/refresh seasonality facts:
  ```bash
  python -m mie_lib.cli.mie build-seasonality-facts
  ```

### Minervini Scanner
- Build daily snapshot:
  ```bash
  python -m mie_lib.cli.mie build-minervini-daily --date 2024-01-01
  ```

### GAF (Deep Learning)
- Train Model:
  ```bash
  python -m mie_lib.cli.mie train-gaf --ticker SPY --epochs 20
  ```
- Run Inference:
  ```bash
  python -m mie_lib.cli.mie build-gaf-daily --ticker SPY
  ```

## Validation & Reliability

- Data Integrity Check:
  ```bash
  python -m mie_lib.cli.mie validate-raw
  ```

- Reliability Snapshot:
  ```bash
  python -m mie_lib.cli.mie rebuild-reliability
  ```

