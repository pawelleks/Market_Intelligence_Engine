# Market Intelligence Engine — Documentation

**Welcome!** This is the documentation hub for the Market Intelligence Engine (MIE).

---

## 🎯 Quick Start

- **New to MIE?** Start with [`CORE/ARCHITECT_BIBLE.md`](CORE/ARCHITECT_BIBLE.md) for system overview
- **Setting up development?** See [`DEVELOPMENT/DEV_GUIDE.md`](DEVELOPMENT/DEV_GUIDE.md)
- **Looking for API reference?** Jump to [Analytics](#analytics--data-reference) or [CLI](#cli-reference)
- **Building UI?** Check the [UI System](#ui-system) docs

---

## 📚 Core Documentation

### Architecture & Design

| Document | Purpose | Audience |
|----------|---------|----------|
| [`CORE/ARCHITECT_BIBLE.md`](CORE/ARCHITECT_BIBLE.md) | **Master architecture document** — system design, principles, data flow, module structure | All developers |
| [`CORE/state_classification.md`](CORE/state_classification.md) | Regime/state labeling logic (canonical rules) | Analytics developers |

### Analytics & Data Reference

| Document | Purpose | Audience |
|----------|---------|----------|
| [`CORE/ANALYTICS_REFERENCE.md`](CORE/ANALYTICS_REFERENCE.md) | Complete reference for analytics engines (Markov, HMM, Seasonality) | Analytics developers, data scientists |
| [`CORE/DATA_REFERENCE.md`](CORE/DATA_REFERENCE.md) | Data schemas, storage patterns, feature catalog | All developers |

### CLI Reference

| Document | Purpose | Audience |
|----------|---------|----------|
| [`CORE/CLI_REFERENCE.md`](CORE/CLI_REFERENCE.md) | Command-line interface documentation | DevOps, automation, developers |

### Development

| Document | Purpose | Audience |
|----------|---------|----------|
| [`DEVELOPMENT/DEV_GUIDE.md`](DEVELOPMENT/DEV_GUIDE.md) | Developer onboarding, setup, testing guide | New developers |
| [`DEVELOPMENT/TESTING.md`](DEVELOPMENT/TESTING.md) | Comprehensive testing guide (pytest, debugging, CI) | Developers, QA |
| [`DEVELOPMENT/CONTRIBUTING.md`](DEVELOPMENT/CONTRIBUTING.md) | **Contributing guide** — PR process, code style, commit conventions | Contributors |
| [`DEVELOPMENT/AI_PROMPT_HEADER.txt`](DEVELOPMENT/AI_PROMPT_HEADER.txt) | Standard prompt template for AI coding agents | AI-assisted development |

---

## 🎨 UI System

Complete UI/UX specifications and design standards:

| Document | Purpose |
|----------|---------|
| [`UI_SYSTEM/UI_SYSTEM_INDEX.md`](UI_SYSTEM/UI_SYSTEM_INDEX.md) | **Entry point** — navigation hub for UI docs |
| [`UI_SYSTEM/UI_README_v2.md`](UI_SYSTEM/UI_README_v2.md) | UI system overview, global layout patterns |
| [`UI_SYSTEM/DESIGN_BRIEF_v2.md`](UI_SYSTEM/DESIGN_BRIEF_v2.md) | UX principles, design language, visual tone |
| [`UI_SYSTEM/CHART_SPECS_v2.md`](UI_SYSTEM/CHART_SPECS_v2.md) | Chart styling rules, color tokens, visual standards |
| [`UI_SYSTEM/PAGE_SPEC_MARKOV_v2.md`](UI_SYSTEM/PAGE_SPEC_MARKOV_v2.md) | Detailed Markov Chains page specification |
| [`UI_SYSTEM/PAGE_SPEC_HMM_v2.md`](UI_SYSTEM/PAGE_SPEC_HMM_v2.md) | **Hidden Markov Model page specification** (v2.0) |

---

## 📜 Version History

| Document | Purpose |
|----------|---------|
| [`CHANGELOG.md`](CHANGELOG.md) | Release notes and version history |

---

## 🗄️ Legacy & Historical Docs

⚠️ **Files in `docs/legacy/` are deprecated and marked for deletion.**

All files in the legacy folder have been:
- Superseded by v2 documentation in CORE/, DEVELOPMENT/, or UI_SYSTEM/
- Marked with deprecation banners (date: 2025-11-14)
- Scheduled for deletion after 6-month grace period (2026-05-14)

**No runtime code depends on legacy documentation.** They are preserved only for historical reference.

**Legacy files include:**
- Architecture drafts (merged into ARCHITECT_BIBLE.md)
- Old UI specifications (replaced by UI_SYSTEM/*_v2.md files)
- Planning documents (Restructure_PLAN.md - project completed)
- Command references (replaced by developer_commands_cheatsheet.md)

**For migration guidance:** See [`legacy/README.md`](legacy/README.md) for replacement mapping.

---

## 🔗 External Resources

- **GitHub Repository**: [Link to repo]
- **Issue Tracker**: [Link to issues]
- **Contributing Guidelines**: [`DEVELOPMENT/CONTRIBUTING.md`](DEVELOPMENT/CONTRIBUTING.md)

---

**Last Updated**: 2025-11-14  
**Maintained By**: MIE Development Team
