---
title: Design Brief – Market Intelligence Engine
version: 2.0.0
last_updated: 2025-11-07
status: active
owner: design+architecture
---

# Design Brief (v2)

High-level UX and visual system for the Market Intelligence Engine.

---

## Design Goals

1. **Trustworthy**
   - Numbers are precise, sourced, reproducible.
2. **Legible to non-quants**
   - Plain language, guided summaries.
3. **Empowering for quants**
   - Full detail accessible via tables, metadata, and structured layout.
4. **Screenshotable**
   - Each section reads as a self-contained panel.

---

## Visual Language

- **Theme**: Dark, minimal, analytical.
- **Typography**:
  - Titles: clear sans-serif, bold, white.
  - Body: high-contrast, regular weight.
  - Captions/meta: small, muted gray.
- **Color Semantics**:
  - Green: positive / up / bullish.
  - Red: negative / down / bearish.
  - Neutral: muted amber/gray for sideways/uncertain.
- **Spacing**:
  - Generous vertical spacing between sections.
  - Use horizontal rules for separation.

### Technical Color Palette

**Backgrounds**:
- Page background: `#0B1220`
- Card/section background: `#0E1525`
- Gridlines: `#203049`

**Text**:
- Primary foreground: `#D7E3F3`
- Muted/secondary: `#9E9E9E`

**State Colors**:
- Green (bullish): `#4CAF50`
- Red (bearish): `#F44336`
- Blue (neutral/info): `#9EC4FF`
- Neutral/gray: `#9E9E9E`

### Typography Specifications

**Font Family**:
- System UI / Inter (fallback to system sans-serif)

**Font Sizes**:
- Page titles (H1): `18–20px`, bold
- Section titles (H2): `16–18px`, bold
- Body text: `12–13px`, regular weight
- Captions/meta: `10–11px`, muted

**Accessibility Requirements**:
- Minimum contrast ratio: **7:1** (WCAG AAA)
- All text must be readable against dark backgrounds
- Titles and axes always visible in dark mode

### Layout Grid

- **Desktop**: Two-column layout where possible
- **Narrow screens**: Single column fallback
- **Cards**: Self-contained panels with padding, screenshotable
- **Sections**: Clear visual separation with horizontal rules or whitespace

---

## Content Pattern

Each analytical block:

1. What are we looking at? (Title)
2. Under what conditions? (Settings line)
3. What are the numbers? (Table / visual)
4. What does it mean? (Short summary)

If you cannot answer (4), the block is incomplete.

---

## Tone & Copy

- Direct, factual, calm.
- Example:
  - ✅ `Given previous state was Green, next day is most likely Red (53.0%).`
  - ❌ `The market is freaking out and collapsing.`
- Use **“most likely”, “tilt”, “bias”** instead of deterministic claims.

---

## Interaction with Specs

Design Brief is **not** implementation detail.
When in doubt:
- Behavior → `ARCHITECT_BIBLE.md`
- Layout → `UI_README_v2.md`
- Page-specific → `PAGE_SPEC_*`
- Charts → `CHART_SPECS_v2.md`