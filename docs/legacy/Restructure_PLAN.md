> ----------------------------------------------  
> **DEPRECATED** — moved to docs/legacy/ on 2025-11-14  
> Not referenced from v2 documentation.  
> This was an internal planning document for the documentation restructuring project.  
> The restructuring has been completed. Safe to delete after manual review.  
> ----------------------------------------------

---

📋 Documentation Inventory & Analysis
Core Architecture & Design (Category A - MUST KEEP)
ARCHITECT_BIBLE.md - Master architecture document, system-of-record for design decisions, layering, and invariants. Status: A - MUST KEEP

ARCHITECTURE.md - High-level system overview, component diagram, data flow. Status: A - MUST KEEP (but should be reconciled with ARCHITECT_BIBLE)

ANALYTICS_REFERENCE.md - Complete reference for all analytics engines (Markov, HMM, Seasonality, Momentum, etc.). Status: A - MUST KEEP

DATA_REFERENCE.md - Schema definitions, feature catalog, data pipeline specs. Status: A - MUST KEEP

DEV_GUIDE.md - Developer onboarding, setup instructions, testing guide. Status: A - MUST KEEP

UI System Documentation (Category A/B)
UI_SYSTEM/UI_SYSTEM_INDEX.md - Navigation hub for UI docs. Status: A - MUST KEEP

UI_SYSTEM/UI_README_v2.md - UI system overview, component inventory. Status: A - MUST KEEP

UI_SYSTEM/CHART_SPECS_v2.md - Chart styling rules, color tokens, visual standards. Status: A - MUST KEEP

UI_SYSTEM/DESIGN_BRIEF_v2.md - UX principles, design language, accessibility. Status: A - MUST KEEP

UI_SYSTEM/PAGE_SPEC_MARKOV_v2.md - Detailed Markov page specification. Status: A - MUST KEEP

UI_REFERENCE.md - (Root-level UI doc) Status: B - CAN BE MERGED into UI_SYSTEM folder

CLI & Operations (Category A)
CLI_REFERENCE.md - Complete CLI command reference. Status: A - MUST KEEP
State & Process Documentation (Category A/D)
state_classification.md - Regime/state labeling logic. Status: A - MUST KEEP

CHANGELOG.md - Version history, release notes. Status: A - MUST KEEP

Prompts & Templates (Category A)
AI_PROMPT_HEADER.txt - Standard prompt header for AI agents. Status: A - MUST KEEP
Legacy/Historical (Category C/D/E)
legacy/ folder - Contains:

Old architecture docs
Deprecated API specs
Historical design notes
Superseded CLI references
Status: D - OUTDATED BUT CONTAINS IMPORTANT DETAILS (keep for historical context, but clearly mark as archived)

🔍 Redundancy & Consolidation Opportunities
ARCHITECTURE.md vs ARCHITECT_BIBLE.md
Issue: Overlap in scope; both cover system design
Recommendation:
Keep ARCHITECT_BIBLE.md as the authoritative source
Merge ARCHITECTURE.md high-level diagrams/overview into ARCHITECT_BIBLE.md
OR keep ARCHITECTURE.md as a quick-start version with link to ARCHITECT_BIBLE for deep details
UI_REFERENCE.md vs UI_SYSTEM/ folder
Issue: Root-level UI_REFERENCE.md duplicates content now in UI_SYSTEM/
Recommendation:
Move UI_REFERENCE.md → UI_SYSTEM/UI_REFERENCE_LEGACY.md
Update all internal links to point to UI_SYSTEM/ docs
Legacy folder
Issue: Unclear what's still relevant
Recommendation:
Add legacy/README.md explaining what's deprecated
Date-stamp all legacy files
Extract any still-relevant content into main docs
🏗️ Proposed Consolidated Structure
✅ Action Plan
Phase 1: Consolidate Core Docs
Merge ARCHITECTURE.md → ARCHITECT_BIBLE.md (keep diagrams, remove duplication)
Create docs/README.md as navigation hub
Move root-level UI_REFERENCE.md → UI_SYSTEM/UI_REFERENCE_LEGACY.md
Phase 2: Organize by Audience
Create CORE folder for system-level docs (architecture, analytics, data, CLI)
Create DEVELOPMENT/ folder for dev-focused content
Extract testing content from DEV_GUIDE.md → DEVELOPMENT/TESTING.md
Phase 3: Legacy Cleanup
Add legacy/README.md explaining deprecation status
Date-stamp all legacy files (e.g., legacy/ARCHITECTURE_2023.md)
Scan legacy docs for still-relevant content → migrate to main docs
Phase 4: New Docs
Create UI_SYSTEM/PAGE_SPEC_HMM_v2.md (based on your rebuild)
Create DEVELOPMENT/CONTRIBUTING.md (PR process, code style, commit conventions)
Add cross-references between related docs
📊 Classification Summary
Category	Count	Files
A - MUST KEEP	12	ARCHITECT_BIBLE, ANALYTICS_REFERENCE, DATA_REFERENCE, CLI_REFERENCE, DEV_GUIDE, CHANGELOG, state_classification, UI_SYSTEM/* (6 files), AI_PROMPT_HEADER
B - CAN BE MERGED	2	ARCHITECTURE.md, UI_REFERENCE.md
C - DEPRECATED	0	(None identified yet)
D - OUTDATED BUT IMPORTANT	1	legacy/ folder
E - REDUNDANT	0	(After merging B items)
