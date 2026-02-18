import httpx
import json
import calendar
from datetime import datetime, timedelta, date
import pandas_market_calendars as mcal

# --- CONFIG ---
THETA_URL = "http://theta_terminal:25510"
TICKERS = ['SPX', 'SPY', 'QQQ', 'IWM']
OUTPUT_JSON = '/app/public/data/expected_moves_static.json'
SIGMA_FACTOR = 0.85

# --- MARKET CALENDAR ---
NYSE = mcal.get_calendar('NYSE')


def is_trading_day(dt: date) -> bool:
    schedule = NYSE.schedule(start_date=dt, end_date=dt)
    return len(schedule) > 0


def next_trading_day(from_date: date) -> date:
    """Return the next open market session on or after from_date."""
    schedule = NYSE.schedule(
        start_date=from_date,
        end_date=from_date + timedelta(days=10),
    )
    return schedule.index[0].date()


def next_weekly_expiry(from_date: date) -> date:
    """Return the next Friday that is a trading day (weekly options expiry)."""
    days_ahead = 4 - from_date.weekday()  # 4 = Friday
    if days_ahead <= 0:
        days_ahead += 7
    friday = from_date + timedelta(days=days_ahead)

    schedule = NYSE.schedule(
        start_date=friday,
        end_date=friday + timedelta(days=10),
    )
    return schedule.index[0].date()


def last_trading_day_of_month(year: int, month: int) -> date:
    """Return the last trading day of the specified month (EOM)."""
    last_day = calendar.monthrange(year, month)[1]
    dt = date(year, month, last_day)
    while not is_trading_day(dt):
        dt -= timedelta(days=1)
    return dt


def next_monthly_expiry(from_date: date) -> date:
    """Return the last trading day of the current month (EOM).
    If already past EOM, use next month's last trading day."""
    eom = last_trading_day_of_month(from_date.year, from_date.month)
    if eom <= from_date:
        if from_date.month == 12:
            eom = last_trading_day_of_month(from_date.year + 1, 1)
        else:
            eom = last_trading_day_of_month(from_date.year, from_date.month + 1)
    return eom


def fmt_label(d: date) -> str:
    """Format date as 'Mon Feb 9' for the UI."""
    return d.strftime('%a %b %-d')


def get_price(client, root):
    """Fetch latest close from Theta Terminal REST API."""
    print(f"--- Fetching Close for {root} ---")
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        fmt_start = start_date.strftime('%Y%m%d')
        fmt_end = end_date.strftime('%Y%m%d')

        if root in ['SPX', 'VIX']:
            url = f"{THETA_URL}/v2/hist/index/eod"
            params = {
                "root": root,
                "start_date": fmt_start,
                "end_date": fmt_end,
            }
            is_index = True
        else:
            url = f"{THETA_URL}/v2/hist/stock/eod"
            params = {
                "root": root,
                "start_date": fmt_start,
                "end_date": fmt_end,
            }
            is_index = False

        response = client.get(url, params=params, timeout=10.0)
        if response.status_code != 200:
            print(f"   > API ERROR {response.status_code}")
            return None

        data = response.json()

        if isinstance(data, dict) and "response" in data:
            candles = data["response"]
            if not candles:
                return None

            if is_index:
                # Index EOD — has proper OHLC with 'close' column
                header = data.get("header", {}).get("format", [])
                try:
                    close_idx = header.index("close")
                    date_idx = header.index("date") if "date" in header else -1
                    if date_idx >= 0:
                        candles.sort(key=lambda r: r[date_idx], reverse=True)
                    price = float(candles[0][close_idx])
                except (ValueError, IndexError):
                    price = float(candles[0][5])  # fallback: close at index 5
                return price
            else:
                header = data.get("header", {}).get("format", [])
                try:
                    close_idx = header.index("close")
                    date_idx = header.index("date") if "date" in header else 0
                    # Sort by date descending — take the most recent trading day
                    candles.sort(key=lambda r: r[date_idx], reverse=True)
                    return candles[0][close_idx]
                except Exception:
                    return candles[-1][4]

        return None

    except Exception as e:
        print(f"   > ERROR: {e}")
        return None


def get_atm_straddle(client, root: str, exp_date: date, spot_price: float) -> dict | None:
    """Fetch ATM straddle from ThetaData bulk snapshot for a specific expiration."""
    exp_str = exp_date.strftime('%Y%m%d')
    url = f"{THETA_URL}/v2/bulk_snapshot/option/quote"
    params = {"root": root, "exp": exp_str}

    print(f"   Fetching ATM straddle for {root} exp={exp_date}...")
    try:
        response = client.get(url, params=params, timeout=15.0)
        if response.status_code != 200:
            print(f"   > Snapshot API ERROR {response.status_code}")
            return None

        data = response.json()
        header = data.get("header", {}).get("format", [])
        if not header:
            return None

        idx_bid = header.index("bid") if "bid" in header else None
        idx_ask = header.index("ask") if "ask" in header else None
        if idx_bid is None or idx_ask is None:
            return None

        # Parse contracts, find calls and puts near ATM
        calls = {}
        puts = {}

        for item in data.get("response", []):
            contract = item.get("contract", {})
            ticks = item.get("ticks", [])
            if not contract or not ticks:
                continue

            strike_raw = contract.get("strike", 0)
            right = contract.get("right", "")
            strike = strike_raw / 1000.0

            tick = ticks[-1]
            bid = tick[idx_bid] if tick[idx_bid] else 0
            ask = tick[idx_ask] if tick[idx_ask] else 0
            mid = (bid + ask) / 2.0

            if right == "C":
                calls[strike] = mid
            elif right == "P":
                puts[strike] = mid

        if not calls and not puts:
            print(f"   > No option data for {root} exp={exp_date}")
            return None

        # Find ATM strike
        all_strikes = sorted(set(calls.keys()) | set(puts.keys()))
        if not all_strikes:
            return None
        atm_strike = min(all_strikes, key=lambda s: abs(s - spot_price))

        call_price = calls.get(atm_strike, 0)
        put_price = puts.get(atm_strike, 0)
        data_quality = "good"

        # Bad Tick Filter
        if call_price <= 0.05 and put_price > 0.05:
            print(f"   > BAD TICK: Call=${call_price:.2f} near-zero. Estimating Call ≈ Put (${put_price:.2f})")
            call_price = put_price
            data_quality = "estimated"
        elif put_price <= 0.05 and call_price > 0.05:
            print(f"   > BAD TICK: Put=${put_price:.2f} near-zero. Estimating Put ≈ Call (${call_price:.2f})")
            put_price = call_price
            data_quality = "estimated"
        elif call_price <= 0.05 and put_price <= 0.05:
            print(f"   > BAD TICK: Both legs near-zero. Skipping {root} exp={exp_date}")
            return None

        straddle = call_price + put_price
        print(f"   > ATM {atm_strike}: C=${call_price:.2f} P=${put_price:.2f} Straddle=${straddle:.2f} [{data_quality}]")
        return {
            "atm_strike": atm_strike,
            "call_price": round(call_price, 2),
            "put_price": round(put_price, 2),
            "straddle": round(straddle, 2),
            "data_quality": data_quality,
        }

    except Exception as e:
        print(f"   > Straddle fetch error: {e}")
        return None


def main():
    print(">>> STARTING DATA FETCH...")

    # Compute target dates once
    today = date.today()
    dte_0_date = next_trading_day(today)
    weekly_date = next_weekly_expiry(today)
    monthly_date = next_monthly_expiry(today)

    # DTE in calendar days from today
    dte_0 = max((dte_0_date - today).days, 1)
    dte_w = max((weekly_date - today).days, 1)
    dte_m = max((monthly_date - today).days, 1)

    print(f"   0DTE target:    {fmt_label(dte_0_date)} ({dte_0}d)")
    print(f"   Weekly target:  {fmt_label(weekly_date)} ({dte_w}d)")
    print(f"   Monthly target: {fmt_label(monthly_date)} ({dte_m}d) [EOM]")

    tenors = [
        ("0dte", dte_0_date, dte_0),
        ("weekly", weekly_date, dte_w),
        ("monthly", monthly_date, dte_m),
    ]

    import time

    # Retry configuration for startup race condition
    max_retries = 12  # Try for ~2 minutes (exponential backoff will cap)
    retry_delay = 2.0
    
    with httpx.Client() as client:
        # Check connection before starting loop
        connected = False
        for i in range(max_retries):
            try:
                # Simple health check using list_expirations or just a root check
                resp = client.get(f"{THETA_URL}/v2/list/expirations?root=SPY", timeout=5.0)
                if resp.status_code == 200:
                    connected = True
                    print(">>> Connected to Theta Terminal successfully.")
                    break
            except Exception as e:
                print(f"   > Connection attempt {i+1}/{max_retries} failed: {e}")
            
            if i < max_retries - 1:
                print(f"   > Waiting {retry_delay}s before retry...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, 10.0) # Cap at 10s
        
        if not connected:
            print(">>> ERROR: Could not connect to Theta Terminal after multiple retries. Exiting.")
            return

        results = {}
        for root in TICKERS:
            price = get_price(client, root)

            if price is None or price <= 0:
                print(f"   > SKIP {root}: no valid price from API")
                continue

            print(f"   > {root}: ${price}")

            # Use SPXW root for SPX options (weeklies have better liquidity)
            option_root = "SPXW" if root == "SPX" else root

            ticker_data = {"close": price}

            for tenor_label, exp_date, dte in tenors:
                straddle_data = get_atm_straddle(client, option_root, exp_date, price)

                if straddle_data:
                    breakeven = straddle_data["straddle"]
                    sigma = round(breakeven * SIGMA_FACTOR, 2)
                    ticker_data[tenor_label] = {
                        "breakeven_move": breakeven,
                        "sigma_move": sigma,
                        "upper_breakeven": round(price + breakeven, 2),
                        "lower_breakeven": round(price - breakeven, 2),
                        "upper_sigma": round(price + sigma, 2),
                        "lower_sigma": round(price - sigma, 2),
                        "date": fmt_label(exp_date),
                        "target_date": exp_date.isoformat(),
                        "dte": dte,
                        "data_quality": straddle_data["data_quality"],
                        "debug": {
                            "atm_strike": straddle_data["atm_strike"],
                            "call_price": straddle_data["call_price"],
                            "put_price": straddle_data["put_price"],
                        },
                    }
                else:
                    print(f"   > No straddle for {root} {tenor_label} — skipping tenor")
                    ticker_data[tenor_label] = None

            results[root] = ticker_data

        with open(OUTPUT_JSON, 'w') as f:
            json.dump(results, f, indent=4)
        print(f">>> SUCCESS: JSON saved to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
