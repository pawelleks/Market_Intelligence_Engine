# State Classification Standard (Authoritative)

All components must use `core/state_classification.py` for regime/state derivation.

## Tri-State Regime Logic

Let:
- `return_value` be the raw daily return in decimal form (e.g. `0.001` for +0.10%).
- `threshold_bps` be an integer basis-point threshold (e.g. `10`, `15`, `20`).
- `T = threshold_bps * 0.0001` (bps → decimal).

Classification (INCLUSIVE boundaries):
- **Green**   if `return_value >= +T`
- **Red**     if `return_value <= -T`
- **Neutral** if `-T < return_value < +T`

Important:
- No UI rounding prior to classification; decisions use full precision of the numeric value.
- Boundaries are inclusive (`>= +T` and `<= -T`). Thus exactly +T → Green, exactly -T → Red.
- Any new feature or analytics module requiring a state label **must** call `classify_tri_state`.

## Binary Mode (Historical Behavior)
Binary collapsing retains existing semantics: values classified Green (Up) vs Red (Down). Neutral from tri logic collapses to Red by default unless explicitly redefined.

## Extension Points
Additional classification modes (quantile, volatility regimes, etc.) should be implemented in this module to prevent logic drift.

## UI Integration
Pages (e.g. Markov Chains Analysis, Price & Daily Returns Viewer) must:
- Import classification functions from the `core.state_classification` module.
- Ensure summaries and tables (One-Step, Multi-Horizon) reuse the same previous-state anchor computed from the most recent return using the selected threshold.

## Tests
Unit tests MUST validate boundary conditions:
- For threshold 10 bps (T=0.001):
  - `+0.0010` → Green
  - `-0.0010` → Red
  - `+0.000999` → Neutral
  - `-0.000999` → Neutral

This document supersedes any prior ad-hoc state logic scattered in analytics or UI code.

