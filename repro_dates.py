from datetime import date, timedelta

def _get_horizon_targets(as_of: date):
    print(f"--- Calculating Horizons for {as_of} ({as_of.strftime('%A')}) ---")
    
    # 1. EOW (Friday of current week)
    days_to_fri = (4 - as_of.weekday() + 7) % 7
    if as_of.weekday() > 4: 
         days_to_fri = (4 - as_of.weekday() + 7) % 7
    eow = as_of + timedelta(days=days_to_fri)
    print(f"EOW (Calc): {eow}")

    # 2. EOM
    next_month = as_of.replace(day=28) + timedelta(days=4)
    eom = next_month - timedelta(days=next_month.day)
    print(f"EOM (Calc): {eom}")

    # 3. EOQ
    quarter_months = [3, 6, 9, 12]
    curr_month = as_of.month
    try:
        q_month = next(m for m in quarter_months if m >= curr_month)
    except StopIteration:
        q_month = 3 # Next year Q1? No, logic assumes current year
    
    if q_month == 12:
        eoq = date(as_of.year, 12, 31)
    else:
        tgt = date(as_of.year, q_month, 1) + timedelta(days=32)
        eoq = tgt.replace(day=1) - timedelta(days=1)
    print(f"EOQ (Calc): {eoq}")
    
    return {
        "eow": eow,
        "eom": eom,
        "eoq": eoq
    }

if __name__ == "__main__":
    _get_horizon_targets(date(2025, 12, 18))
    _get_horizon_targets(date(2025, 12, 10))
