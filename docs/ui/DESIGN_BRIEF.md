# DESIGN BRIEF — Market Intelligence Engine (UI)

## Vision
A modern, dark-only research dashboard that blends Bloomberg-like density with Koyfin’s clarity. It must be fast, readable, explanatory, and shareable.

## Audience
- Active investors, PMs, quants
- Curious investors who want plain-English takeaways

## Core Principles
1) **Dark-only theme**; low-glare, high-contrast text.
2) **Zero compute in UI** — only render precomputed Parquet/CSV.
3) **Readable at a glance** — cards, short labels, compact tables.
4) **Explain as you go** — every study has a 2–3 sentence summary.
5) **Expandable charts** — small by default, one-click expand (modal).
6) **Performance** — downsample to ≤ 2,500 points per chart; lazy-load.
7) **Consistency** — shared tokens for colors, fonts, spacing.

## Layout Patterns
- **Top bar**: Ticker selector, date range, data freshness.
- **Sections** (cards): title, compact header line (params), key metric row, chart + summary.
- **Two-column** where possible; single column on narrow screens.
- **“More details”** link opens a deeper research page (Markov/HMM labs).

## Visual Language
- Background: #0B1220 (page), #0E1525 (cards)
- Gridlines: #203049
- Foreground text: #D7E3F3
- Accents: Green #4CAF50, Red #F44336, Neutral #9E9E9E, Blue #9EC4FF
- Fonts: System UI / Inter; small but readable; titles 18–20px; body 12–13px.
- Sparing use of color; focus on data.

## Interactions
- Charts: hover tooltips, legend toggle, zoom/drag when expanded.
- Export: CSV/PNG download on each card.
- Notes: each card has a 2–3 sentence human summary.

## Performance Guardrails
- Max points per series: 2,500 (auto-downsample).
- No synchronous heavy I/O on main thread.
- Cache loaded datasets per page; invalidate on ticker/date change.

## Accessibility
- Minimum contrast ratio for text 7:1.
- Titles and axes always visible in dark mode.

## Deliverables (UI Layer)
- `app/ui/theme.py` — tokens + helpers (dark).
- `app/ui/components.py` — Card, SectionHeader, ExpandableChart, SummaryBox.
- `config/ui.yml` — tokens (colors, spacing, fonts, max_points).
- Pages per spec in PAGES_SPEC.md using only precomputed files.