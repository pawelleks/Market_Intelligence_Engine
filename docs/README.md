# Market Intelligence Engine — Documentation

**Welcome!** This is the documentation hub for the Market Intelligence Engine (MIE).

---

## 🎯 Quick Start

- **New to MIE?** Start with [`CORE/ARCHITECT_BIBLE.md`](CORE/ARCHITECT_BIBLE.md) for system overview
- **Setting up development?** See [`DEVELOPMENT/SETUP.md`](DEVELOPMENT/SETUP.md)
- **Looking for API reference?** Jump to [Analytics](#analytics--data-reference) or [CLI](#cli-reference)
- **Building UI?** Check the [UI System](#ui-system) docs

---

## 📚 Core Documentation

### Architecture & Design

| Document | Purpose | Audience |
|----------|---------|----------|
| [`CORE/ARCHITECT_BIBLE.md`](CORE/ARCHITECT_BIBLE.md) | **Master architecture document** — system design, principles, data flow | All developers |
| [`CORE/PIPELINE_ARCHITECTURE.md`](CORE/PIPELINE_ARCHITECTURE.md) | **Dependency Graph** — Data flow and pipeline stages | Architects, DevOps |
| [`CORE/state_classification.md`](CORE/state_classification.md) | Regime/state labeling logic (canonical rules) | Analytics developers |

### Analytics & Data Reference

| Document | Purpose | Audience |
|----------|---------|----------|
| [`CORE/ANALYTICS_REFERENCE.md`](CORE/ANALYTICS_REFERENCE.md) | Reference for analytics engines (Markov, HMM) | Quants, Data Scientists |
| [`CORE/DATA_REFERENCE.md`](CORE/DATA_REFERENCE.md) | Data schemas, storage patterns | All developers |
| [`CORE/EXPECTED_MOVES_SPEC.md`](CORE/EXPECTED_MOVES_SPEC.md) | Specification for Expected Moves analytics | Quants |

### CLI Reference

| Document | Purpose | Audience |
|----------|---------|----------|
| [`CORE/CLI_REFERENCE.md`](CORE/CLI_REFERENCE.md) | Command-line interface documentation | DevOps, Automation |

---

## 🛠 Development & Operations

| Document | Purpose | Audience |
|----------|---------|----------|
| [`DEVELOPMENT/SETUP.md`](DEVELOPMENT/SETUP.md) | **Installation Guide** — Docker setup, environment config | New developers |
| [`DEVELOPMENT/CONTRIBUTING.md`](DEVELOPMENT/CONTRIBUTING.md) | **Contributing Guide** — Branching, PRs, Standards | Contributors |
| [`OPERATIONS/DATA_PIPELINE.md`](OPERATIONS/DATA_PIPELINE.md) | **Runbook** — Managing daily updates, troubleshooting | DevOps |

---

## 🎨 UI System

| Document | Purpose |
|----------|---------|
| [`UI_SYSTEM/UI_SPECS.md`](UI_SYSTEM/UI_SPECS.md) | **UI System Specification (v3)** — React/Vite/FastAPI stack |

---

## 🗄️ Legacy & Deprecated

Files in `_deprecated_v1/` are preserved for historical reference but are no longer active.
