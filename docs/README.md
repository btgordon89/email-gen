# Email Gen v1 Documentation

This folder contains all documentation for the Email Generator v1 pipeline.

## 📁 Folder Structure

### [`prds/`](prds/)
Product Requirements Documents that define the original pipeline architecture:
- **PRD_00_OVERVIEW.md** — Master architecture overview
- **PRD_01_SCAFFOLDING.md** — Project setup and structure
- **PRD_02_QUESTIONNAIRE.md** — Questionnaire system design
- **PRD_03_STEP1_BRIEF.md** — Step 1: Brief generator
- **PRD_04_STEP2A_STRUCTURE.md** — Step 2A: HTML structure
- **PRD_05_STEP2B_DISCOUNT.md** — Step 2B: Discount strategy
- **PRD_06_STEP2C_PRODUCTS.md** — Step 2C: Product selection
- **PRD_07_STEP2D_COPY.md** — Step 2D: Copy generation
- **PRD_08_STEP2E_LINKS.md** — Step 2E: Link generation
- **PRD_09_STEP3_COHESION.md** — Step 3: Cohesion review

### [`refactoring/`](refactoring/)
Documentation of the March 2026 refactoring that improved maintainability and auditability:

**Start here:**
- **REFACTORING_COMPLETE.md** — Executive summary of what changed and why

**Details:**
- **REFACTORING_SUMMARY.md** — Complete overview of improvements
- **BEFORE_AFTER.md** — Side-by-side code comparison showing 49% reduction
- **ARCHITECTURE_DIAGRAM.md** — Visual explanation of new vs old architecture
- **CHECKLIST.md** — Complete task list with verification steps
- **REFACTORING_PROGRESS.md** — Detailed progress tracking

**Key Improvements:**
- ✅ 49% average code reduction per step
- ✅ Complete audit trail for every step execution
- ✅ Externalized system prompts to `.md` files
- ✅ Inter-step validation
- ✅ 100% backward compatible

### Root Files
- **FUTURE_INTERACTIVE_MODE.md** — Planned interactive questionnaire feature

## 🚀 Quick Start

If you're new to the project:
1. Read [`prds/PRD_00_OVERVIEW.md`](prds/PRD_00_OVERVIEW.md) — Understand the pipeline
2. Read [`refactoring/REFACTORING_COMPLETE.md`](refactoring/REFACTORING_COMPLETE.md) — See recent improvements
3. Check the main [`README.md`](../README.md) in the project root (if it exists)

## 📊 Architecture Summary

```
Questionnaire (YAML)
        ↓
    Step 1: Brief
        ↓
    ┌───────┼───────┐
    ↓       ↓       ↓
Step 2A  Step 2B  Step 2C
(HTML)  (Discount)(Products)
    ↓       ↓       ↓
    ↓   Step 2D  Step 2E
    ↓   (Copy)   (Links)
    ↓       ↓       ↓
    └───────┼───────┘
            ↓
    Step 3: Cohesion
            ↓
    Step 4: Images
            ↓
    Step 5: Assembly
            ↓
    Step 6: Klaviyo Upload
            ↓
    Final Email Template
```

## 🔍 Finding What You Need

**Want to understand the pipeline?**
→ Read [`prds/PRD_00_OVERVIEW.md`](prds/PRD_00_OVERVIEW.md)

**Want to modify a step?**
→ Read the relevant PRD (e.g., [`prds/PRD_07_STEP2D_COPY.md`](prds/PRD_07_STEP2D_COPY.md))

**Want to understand the new architecture?**
→ Read [`refactoring/ARCHITECTURE_DIAGRAM.md`](refactoring/ARCHITECTURE_DIAGRAM.md)

**Want to see code improvements?**
→ Read [`refactoring/BEFORE_AFTER.md`](refactoring/BEFORE_AFTER.md)

**Want to add a new feature?**
→ See how simple it is in [`refactoring/BEFORE_AFTER.md`](refactoring/BEFORE_AFTER.md#adding-a-new-step-example)

## 📝 Documentation Standards

All documentation in this folder follows these principles:
- **Markdown format** for easy reading and version control
- **Clear examples** with code snippets where relevant
- **Diagrams** using text/ASCII art for accessibility
- **Actionable** with specific file paths and commands

## 🔄 Keeping Docs Updated

When making changes to the pipeline:
1. Update relevant PRD if changing step behavior
2. Add notes to refactoring docs if architectural changes
3. Keep this README updated with new doc locations

---

Last updated: March 2026
