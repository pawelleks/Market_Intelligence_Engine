---
title: Market Intelligence Engine – UI System
version: 2.0.0
last_updated: 2025-11-07
status: active
owner: product+architecture
---

# UI System Overview (v2)

This document defines the **global UI contract** for the Market Intelligence Engine.

It is the authoritative reference for:
- Page structure
- Layout and hierarchy
- Typography, color usage, and components
- How analytics surfaces are presented to humans

It must be consistent with:
- `docs/ARCHITECT_BIBLE.md` (architecture + coding constraints; canonical)
- `docs/UI_SYSTEM/DESIGN_BRIEF_v2.md`
- `docs/UI_SYSTEM/PAGE_SPEC_MARKOV_v2.md`
- `docs/UI_SYSTEM/CHART_SPECS_v2.md`
- `docs/UI_SYSTEM/UI_SYSTEM_INDEX.md`

If there is conflict, **ARCHITECT_BIBLE.md wins**, then this UI_README_v2.

---

## 1. Global Layout Principles

1. **Clarity first.** Every page must explain:
   - What it is.
   - What data it’s using.
   - What parameters shape what’s visible.

2. **Offline, reproducible analytics.**
   - UIs must consume **precomputed artifacts** (Parquet, JSON, etc).
   - No heavy computation in Streamlit callbacks.
   - Missing data → clear hints (never stack traces).

3. **Consistent reading pattern.**
   - Top: Page title + meta.
   - Then: Filters.
   - Then: Sections, each self-contained and screenshot-friendly.

4. **Audience duality.**
   - Must work for:
     - Curious non-quants.
     - Quant / systematic users.
   - Achieved via:
     - Plain-language summaries.
     - Structured tables.
     - Optional detail/expander for deeper diagnostics.

---

## 2. Standard Page Skeleton

Every analytical page (including Markov, HMM, Seasonality, Signals) must follow this pattern:

1. **Page Title (H1)**
   - Example: `Markov Chains Analysis`
   - Large, left-aligned, white or near-white.

2. **Page Meta Line (Caption)**
   - Single line, subtle (smaller, slightly muted):
   - Format:
     - `Release: vX.Y.Z • Last updated: YYYY-MM-DD HH:MM (local or UTC) • Data coverage: TICKER universe + date range description`
   - This meta reflects **UI release + artifact generation**, not per-section times.

3. **Global Filter Block**
   - Always rendered near the top.
   - Typical controls (page-dependent):
     - Ticker
     - Time range / window
     - State mode / regime model / signal set
     - Threshold(s)
     - Order (for Markov)
     - Source: `offline` (default; any online sources must be explicit & allowed by ARCHITECT_BIBLE)
   - Filters must:
     - Update all dependent sections consistently.
     - Never silently fall back to different parameters.

4. **Sections (Repeating Pattern)**

Each section on the page must follow this contract:

**(1) Section Title (H2 style)**
- Clear, specific:
  - e.g. `One-Step Next-State Summary`
  - e.g. `K=1 Transition Matrix`
  - e.g. `Multi-Horizon Forecasts (P^h)`

**(2) Settings Line (Caption style, muted)**
- Summarizes effective parameters driving this section:
  - `Ticker: SPY • Time range: 1Y • Source: offline • State mode: tri • Threshold: 10bps • Order: 1 • Data set for SPY: 1993-01-29 – 2025-10-31 • Last updated: 2025-11-07 03:00`
- Values must:
  - Reflect the **actual artifacts used** (ticker, window, order, threshold, mode).
  - Use human-readable dates (YYYY-MM-DD).

**(3) Core Content**
- One or more of:
  - Table(s)
  - Chart(s)
  - Key metrics

**(4) Human-Readable Insight**
- 1–3 concise sentences.
- Example pattern:
  - `Given previous state was Green, next day is most likely Red (53.0%). Continuation (stay Green) = 47.0%.`
  - `Over 1–4 days, probabilities tilt mildly bearish (Red dominates in 3/4 horizons).`
- Must directly reference the numbers shown above it (no hand-wavy language).

**(5) Visual Separation**
- Light horizontal rule or padding between sections.
- Rule: a user should be able to screenshot a section without leaking adjacent content.

---

## 3. Typography & Color (Essentials)

Details in `DESIGN_BRIEF_v2.md`. Core rules:

- Background: dark theme.
- Page title:
  - Large, bold, white.
- Section titles:
  - H2, bold, white.
- Settings lines, meta:
  - Small, muted gray.
- Body and tables:
  - Clean, high-contrast, no neon.

**State Colors (Semantic, not decorative):**

- **Green (U / Bullish / Up)**:
  - Used for “Green” labels and high up-probability emphasis.
- **Red (D / Bearish / Down)**:
  - Used for “Red” labels and down-probability emphasis.
- **Neutral (N / Sideways)**:
  - Muted yellow/amber or gray.

Always keep them:
- Accessible.
- Non-gimmicky.
- Consistent across pages.

---

## 4. Missing Data & Errors

When required artifacts are missing:

- Do NOT crash.
- Do NOT show raw tracebacks.
- Show a compact, friendly message:
  - `Markov matrix unavailable for this configuration.`
  - `CLI hint: python cli/mie.py ensure-markov-available --ticker SPY --order 1 --state-mode tri --threshold-bps 10 --window 1Y`
- No automatic online fetching unless permitted by ARCHITECT_BIBLE.

---

## 5. Interaction with AI Coding Agents

When using an AI Coding Agent to change UI:

- Always reference:
  - This `UI_README_v2.md`
  - `ARCHITECT_BIBLE.md`
  - Page / chart specs (e.g. `PAGE_SPEC_MARKOV_v2.md`, `CHART_SPECS_v2.md`).
- Specify:
  - Which files can be modified.
  - Which invariants must hold (offline reads, no heavy compute in UI, etc.).
- Require tests:
  - `python -m pytest -q`
  - Or targeted test sets where appropriate.

Any deviation from this doc must be justified and, if accepted, reflected in the next version.