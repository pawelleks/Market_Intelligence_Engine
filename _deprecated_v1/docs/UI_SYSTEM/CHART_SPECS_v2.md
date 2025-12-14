---
title: Chart Specs – Market Intelligence Engine
version: 2.0.0
last_updated: 2025-11-07
status: active
owner: product+architecture
---

# Chart Specs (v2)

Defines reusable chart patterns for all analytical pages.

Must be consistent with:
- `UI_README_v2.md`
- `DESIGN_BRIEF_v2.md`
- Page specs (e.g. `PAGE_SPEC_MARKOV_v2.md`)

---

## General Rules

- Charts **explain numbers**, not replace them.
- Always pair charts with:
  - A clear title.
  - Axis labels where relevant.
  - Short text summary.
- Colors:
  - Semantic:
    - Green = positive/up.
    - Red = negative/down.
    - Neutral = yellow/amber/gray.
  - Muted, no neon.
- Dark background compatible.

### Technical Specifications

- **Performance**:
  - Downsample to ≤ 2,500 points per series to maintain responsiveness.
  - Lazy-load charts when possible.
- **Sizing**:
  - Default: compact size for overview.
  - Expand action: opens modal at **1200×700px** with zoom/pan capabilities.
- **Tooltips**:
  - Show exact values + date/context.
  - Percentages displayed with 1 decimal place by default.
  - Include sample counts where relevant (e.g., transition matrices).
- **Interactivity**:
  - Hover tooltips on all data points.
  - Legend toggle for multi-series charts.
  - Zoom/drag when expanded.
- **Exports**:
  - CSV/PNG download available on each chart card.

---

## Components

### 1. Probability Bar / Column Chart

**Usage**:
- One-step transition probabilities.
- Horizon distributions from P^h.

**Spec**:
- X-axis:
  - Categories: Green, Neutral, Red.
- Y-axis:
  - Probability 0–1 (or 0–100%).
- Tooltip:
  - Exact percentage.
- State colors:
  - Green / Neutral / Red consistent with DESIGN_BRIEF_v2.

---

### 2. Horizon Probability Trend

**Usage**:
- Multi-horizon (1–5 days) probability evolution.

**Spec**:
- X-axis:
  - Horizon (1, 2, 3, 4, 5).
- Y-axis:
  - Probability.
- Lines:
  - One line per state (Green, Neutral, Red).
- Interpretation:
  - Text summary must state:
    - Which state dominates.
    - Whether probabilities converge or diverge.

---

### 3. Heatmaps (Optional)

For Markov K>1 or dense matrices.

**Spec**:
- Axes:
  - Context vs. Next State.
- Color scale:
  - Dark → low probability.
  - Bright → high probability.
- Tooltip:
  - Exact probability & counts.
- Only show when:
  - Readable (limited contexts).
  - Adds insight beyond table.

---

## Prohibited / Caution

- No 3D charts.
- No animation for core analytics.
- Do not use colors unrelated to semantics for Markov/HMM state identities.

If a new visual pattern is used more than twice, propose a patch to this file.