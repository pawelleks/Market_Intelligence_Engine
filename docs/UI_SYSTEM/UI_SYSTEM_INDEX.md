---
title: UI System Index
version: 2.0.0
last_updated: 2025-11-07
status: active
owner: architecture
---

# UI System Index

Authoritative map of UI/UX documentation.

---

## Core

- `ARCHITECT_BIBLE.md`
  - Canonical engineering & architecture constraints.
  - All UI work must respect this.

- `docs/UI_SYSTEM/UI_README_v2.md`
  - Global UI rules, structure, and invariants.

---

## Page Specs

- `docs/UI_SYSTEM/PAGE_SPEC_MARKOV_v2.md`
  - Markov Chains Analysis page.
  - Sections, filters, offline artifacts, summaries.

(Extend with additional PAGE_SPEC_* files as new pages are normalized.)

---

## Visual & Interaction

- `docs/UI_SYSTEM/DESIGN_BRIEF_v2.md`
  - Visual language, tone, semantic colors, spacing.

- `docs/UI_SYSTEM/CHART_SPECS_v2.md`
  - Reusable chart patterns.
  - How to visualize probabilities and transitions correctly.

---

## How to Use This System

1. **When updating a page:**
   - Check:
     - `ARCHITECT_BIBLE.md`
     - `UI_README_v2.md`
     - Relevant `PAGE_SPEC_*`
     - `CHART_SPECS_v2.md`
   - If new behavior doesn’t fit:
     - Propose a small SPEC PATCH in a PR or via Architect-style prompt.

2. **When using an AI Coding Agent:**
   - Always include:
     - This index.
     - The relevant specs.
     - Explicit file scope + test commands.

3. **When something drifts:**
   - Fix the spec or the code, but never allow long-lived divergence.

---