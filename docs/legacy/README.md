# Legacy Documentation — Historical Archive

⚠️ **All files in this directory are DEPRECATED and preserved for historical reference only.**

**Last archived**: 2025-11-14

---

## Why This Folder Exists

This folder contains superseded documentation from earlier phases of the Market Intelligence Engine project. The content here has been:
- **Superseded** by newer versions in the main docs
- **Consolidated** into more comprehensive documents
- **Refactored** into the current doc structure

**Do NOT use these files for development.** They are kept only for:
- Historical context
- Understanding design evolution
- Reference during migration/debugging

---

## Current Documentation

**Please use these instead:**

| Legacy File | Current Replacement |
|-------------|---------------------|
| `ARCHITECTURE.md` | [`../CORE/ARCHITECT_BIBLE.md`](../CORE/ARCHITECT_BIBLE.md) |
| `Restructure_PLAN.md` | N/A (project completed) |
| `COMMANDS.md` | [`../CORE/CLI_REFERENCE.md`](../CORE/CLI_REFERENCE.md) |
| `UI_README.md` | [`../UI_SYSTEM/UI_README_v2.md`](../UI_SYSTEM/UI_README_v2.md) |
| `ui/CHART_SPECS.md` | [`../UI_SYSTEM/CHART_SPECS_v2.md`](../UI_SYSTEM/CHART_SPECS_v2.md) |
| `ui/DESIGN_BRIEF.md` | [`../UI_SYSTEM/DESIGN_BRIEF_v2.md`](../UI_SYSTEM/DESIGN_BRIEF_v2.md) |
| `ui/PAGES_SPEC.md` | [`../UI_SYSTEM/PAGE_SPEC_MARKOV_v2.md`](../UI_SYSTEM/PAGE_SPEC_MARKOV_v2.md) |

---

## File Inventory

### Architecture Documentation
- **`ARCHITECTURE.md`** (Deprecated: 2025-11-14)
  - High-level system overview (merged content)
  - **Replaced by**: `CORE/ARCHITECT_BIBLE.md`

### Project Planning
- **`Restructure_PLAN.md`** (Deprecated: 2025-11-14)
  - Internal documentation restructuring plan
  - **Status**: Project completed; no replacement needed

### Command-Line Documentation
- **`COMMANDS.md`** (Deprecated: ~2023)
  - Early CLI command reference
  - **Replaced by**: `CORE/CLI_REFERENCE.md`

### UI System (v1)
- **`UI_README.md`** (Deprecated: 2025-11-07)
  - Original UI system overview
  - **Replaced by**: `UI_SYSTEM/UI_README_v2.md`

- **`ui/CHART_SPECS.md`** (Deprecated: 2025-11-07)
  - v1 chart specifications
  - **Replaced by**: `UI_SYSTEM/CHART_SPECS_v2.md`

- **`ui/DESIGN_BRIEF.md`** (Deprecated: 2025-11-07)
  - v1 design principles
  - **Replaced by**: `UI_SYSTEM/DESIGN_BRIEF_v2.md`

- **`ui/PAGES_SPEC.md`** (Deprecated: 2025-11-07)
  - Early page specifications
  - **Replaced by**: `UI_SYSTEM/PAGE_SPEC_MARKOV_v2.md` and related specs

---

## Migration Notes

### What Changed (UI Docs v1 → v2)
- ✅ Consolidated color tokens and semantic naming
- ✅ Added comprehensive page specifications per feature
- ✅ Standardized layout patterns and component hierarchy
- ✅ Integrated with `ARCHITECT_BIBLE.md` constraints
- ✅ Added offline-first design requirements

### What Changed (COMMANDS.md → CLI_REFERENCE.md)
- ✅ Updated command syntax for current CLI structure
- ✅ Added batch script references
- ✅ Integrated with data pipeline architecture
- ✅ Added validation and rebuild workflows

---

## Deletion Policy

**These files will be permanently deleted:**
- After 6 months with no references in active code
- When confirmed all content is captured in current docs
- When no active development questions reference them

**Estimated deletion**: 2026-05-14 (6 months from 2025-11-14)

---

## Questions?

If you need clarification on what replaced a legacy doc:
1. Check the "Current Replacement" table above
2. See [`../README.md`](../README.md) for documentation navigation
3. Ask in project chat/issues if migration is unclear

---

**Maintainer Note**: Do not add new files to this folder. All new documentation belongs in the main `docs/` structure.
