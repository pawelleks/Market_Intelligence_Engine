
#!/bin/bash
# 1) Update raw price data for all configured tickers (per config/tickers.yml)
# 2) Rebuild/refresh features for all tickers listed in config (SPY, QQQ, DIA, IWM etc.)
#    Uses latest raw data and overwrites existing feature parquets.
# 3) Build complete Markov grid for your main tickers & all UI combinations
#    (binary+tri, thresholds 0–150bps, windows 1Y–MAX, orders 1–4)
# 4) (Optional) Rebuild HMM artifacts if you use the HMM / regime pages

cd /Users/pawelleks/Documents/Python/Projects/Market_Intelligence_Engine
python cli/mie.py update-raw
python cli/mie.py build-features --mode full --csv
python cli/mie.py build-markov-grid \
  --tickers SPY,QQQ,DIA,IWM \
  --state-modes binary,tri \
  --thresholds 0,5,10,15,20,25,30,35,40,45,50,55,60,65,70,75,100,125,150 \
  --windows 1Y,2Y,5Y,10Y,20Y,MAX \
  --orders 1,2,3,4

python cli/mie.py build-hmm-grid --tickers SPY,QQQ,DIA,IWM