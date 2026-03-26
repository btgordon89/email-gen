# Architecture Diagram: Before & After

## BEFORE: Each Step Was a Standalone Function

```
┌─────────────────────────────────────────────────────────────┐
│ step1_brief.py (160 lines)                                  │
├─────────────────────────────────────────────────────────────┤
│ STEP1_SYSTEM = """48 lines of hardcoded system prompt"""   │
│                                                              │
│ def _build_prompt(...): # 40 lines                          │
│     # Format inputs into prompt                             │
│                                                              │
│ def _parse_json(...): # 20 lines - DUPLICATED IN 6 FILES   │
│     # Strip fences, parse JSON, handle errors               │
│                                                              │
│ def run(run_dir):                                            │
│     # Load inputs (10 lines)                                 │
│     # Call LLM (5 lines)                                     │
│     # Parse JSON (1 line)                                    │
│     # Set defaults manually (7 lines)                        │
│     # Write output (2 lines)                                 │
│     # No audit trail ❌                                      │
│     # No validation ❌                                       │
└─────────────────────────────────────────────────────────────┘

Same pattern repeated in:
- step2a_structure.py (251 lines)
- step2d_copy.py (187 lines)
- step2e_links.py (172 lines)
- step3_cohesion.py (193 lines)
- step4_images.py (with duplicate _effective_copy())
- step5_assembly.py (with duplicate _effective_copy())
```

**Problems:**
- 🔴 600+ lines of duplicate code across 7 files
- 🔴 System prompts buried in Python code
- 🔴 No audit trail
- 🔴 No validation
- 🔴 Hard to test
- 🔴 Hard to maintain

---

## AFTER: Shared Infrastructure + Simple Step Classes

```
┌─────────────────────────────────────────────────────────────┐
│                    SHARED INFRASTRUCTURE                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ base_step.py (BaseStep)                            │    │
│  ├────────────────────────────────────────────────────┤    │
│  │ - Loads system prompt from prompts/*.system.md     │    │
│  │ - Calls LLM with retry logic                       │    │
│  │ - Parses JSON (using json_parser.py)               │    │
│  │ - Sets defaults automatically                       │    │
│  │ - Calls validate() hook                             │    │
│  │ - Writes output JSON                                │    │
│  │ - Writes audit log (using audit.py)                │    │
│  └────────────────────────────────────────────────────┘    │
│                         ▲                                    │
│                         │ inherits                           │
│  ┌──────────────────────┴──────────────────────────┐       │
│  │ json_parser.py   │ effective.py  │ validators.py │       │
│  │ - parse_llm_json │ - effective_  │ - validate_   │       │
│  │ - strip fences   │   copy()      │   structure() │       │
│  │ - retry support  │ - effective_  │ - validate_   │       │
│  │                  │   links()     │   copy()      │       │
│  │                  │ - effective_  │ - validate_   │       │
│  │                  │   structure() │   links()     │       │
│  └──────────────────┴───────────────┴───────────────┘       │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ audit.py                                           │    │
│  │ - write_audit_log() → output/<run>/audit/*.json   │    │
│  │ - Tracks: prompt, response, duration, warnings     │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ prompts/*.system.md (7 files)                      │    │
│  │ - step1_brief.system.md                            │    │
│  │ - step2a_structure.system.md                       │    │
│  │ - step2d_copy.system.md                            │    │
│  │ - ... (externalized, version-controlled)           │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘

                           ▼ used by

┌─────────────────────────────────────────────────────────────┐
│ step1_brief.py (75 lines - 53% reduction!)                 │
├─────────────────────────────────────────────────────────────┤
│ class Step1Brief(BaseStep):                                 │
│     step_id = "step1_brief"                                  │
│     output_filename = "step1_brief.json"                     │
│     model_fn = config.brief_model                            │
│     default_schema = {...}                                   │
│                                                              │
│     def load_inputs(self, run_dir):                          │
│         # What data do I need? (20 lines)                    │
│         return {"questionnaire": ..., "brand_identity": ...} │
│                                                              │
│     def build_prompt(self, inputs):                          │
│         # What should the LLM do? (40 lines)                 │
│         return f"Create brief for {inputs['questionnaire']}" │
│                                                              │
│ # Singleton for backward compatibility                       │
│ _instance = Step1Brief()                                     │
│ def run(run_dir): return _instance.run(run_dir)              │
└─────────────────────────────────────────────────────────────┘

Same simple pattern in:
- step2a_structure.py (103 lines, 59% reduction, + validation)
- step2d_copy.py (92 lines, 51% reduction, + validation)
- step2e_links.py (108 lines, 37% reduction, + validation)
- step3_cohesion.py (107 lines, 45% reduction, + validation)
```

**Benefits:**
- ✅ 49% average code reduction per step
- ✅ System prompts in reviewable `.md` files
- ✅ Complete audit trail (automatic)
- ✅ Validation hooks (optional per step)
- ✅ Easy to test (clear interfaces)
- ✅ Easy to maintain (single source of truth)

---

## Execution Flow: Before & After

### BEFORE
```
User runs: python main.py step2d --run my_campaign

         ▼
    step2d_copy.run(run_dir)
         │
         ├─ Load inputs manually
         ├─ Build prompt manually
         ├─ Call gemini_text.generate_text()
         ├─ Call _parse_json() [duplicate code!]
         ├─ Set defaults manually (7 lines of boilerplate)
         ├─ Write output manually
         └─ Done (no audit, no validation ❌)
```

### AFTER
```
User runs: python main.py step2d --run my_campaign

         ▼
    step2d_copy.run(run_dir)  [singleton wrapper]
         │
         ▼
    Step2dCopy._instance.run(run_dir)  [BaseStep method]
         │
         ├─ start_time = now()
         ├─ inputs = self.load_inputs(run_dir)  [step implements]
         ├─ prompt = self.build_prompt(inputs)  [step implements]
         ├─ system = self._load_system_prompt()  [from .md file ✅]
         ├─ raw = self._call_llm(prompt, system)
         ├─ parsed, warnings = json_parser.parse_llm_json(raw)  [shared ✅]
         ├─ parsed = json_parser.ensure_keys(parsed, default_schema)
         ├─ warnings += self.validate(parsed, inputs)  [step implements ✅]
         ├─ io_util.write_json(output_path, parsed)
         ├─ audit.write_audit_log(...)  [complete trace ✅]
         │    └─ writes: output/<run>/audit/step2d_copy.audit.json
         └─ return parsed
```

**What You Write**: Just 2-3 methods (50-80 lines)  
**What You Get**: Audit trail, validation, error handling, retry support, prompt versioning — all automatic!

---

## File Structure: Before & After

### BEFORE
```
email_gen/
├── pipeline/
│   ├── step1_brief.py ────────────── 160 lines (system prompt + duplicate code)
│   ├── step2a_structure.py ───────── 251 lines (system prompt + duplicate code)
│   ├── step2d_copy.py ────────────── 187 lines (system prompt + duplicate code)
│   ├── step2e_links.py ───────────── 172 lines (system prompt + duplicate code)
│   ├── step3_cohesion.py ─────────── 193 lines (system prompt + duplicate code)
│   ├── step4_images.py ───────────── 420 lines (duplicate effective_copy/structure)
│   └── step5_assembly.py ─────────── 264 lines (duplicate effective_copy/structure)
│
└── output/
    └── <run_id>/
        ├── step1_brief.json
        ├── step2d_copy.json
        └── ... (no audit trail ❌)
```

### AFTER
```
email_gen/
├── pipeline/
│   ├── base_step.py ──────────────── Base class (handles boilerplate)
│   ├── json_parser.py ────────────── Shared JSON parsing
│   ├── effective.py ──────────────── Shared effective state merging
│   ├── audit.py ──────────────────── Audit trail logging
│   ├── validators.py ─────────────── Inter-step validation
│   │
│   ├── prompts/
│   │   ├── step1_brief.system.md ──── Externalized system prompt ✅
│   │   ├── step2a_structure.system.md
│   │   ├── step2d_copy.system.md
│   │   ├── step2e_links.system.md
│   │   └── step3_cohesion.system.md
│   │
│   ├── step1_brief.py ────────────── 75 lines (just business logic ✅)
│   ├── step2a_structure.py ───────── 103 lines (just business logic ✅)
│   ├── step2d_copy.py ────────────── 92 lines (just business logic ✅)
│   ├── step2e_links.py ───────────── 108 lines (just business logic ✅)
│   ├── step3_cohesion.py ─────────── 107 lines (just business logic ✅)
│   ├── step4_images.py ───────────── 420 lines (uses shared effective.py ✅)
│   └── step5_assembly.py ─────────── 264 lines (uses shared effective.py ✅)
│
└── output/
    └── <run_id>/
        ├── audit/ ────────────────── New! Complete audit trail ✅
        │   ├── step1_brief.audit.json
        │   ├── step2d_copy.audit.json
        │   └── ...
        ├── step1_brief.json
        ├── step2d_copy.json
        └── ...
```

---

## Adding a New Step: Before & After

### BEFORE (Had to write)
```python
# 150-200 lines total

STEP_SYSTEM = """..."""  # 40 lines hardcoded

def _parse_json(response):  # 20 lines duplicate code
    # Strip fences, parse JSON, handle errors
    ...

def _build_prompt(...):  # 50 lines
    # Format inputs
    ...

def run(run_dir):  # 40 lines
    # Load inputs
    # Call LLM
    # Parse
    # Set defaults
    # Write output
    # No audit, no validation
    ...
```

### AFTER (Have to write)
```python
# 60-90 lines total

class StepNewFeature(BaseStep):
    step_id = "step_new_feature"
    output_filename = "step_new_feature.json"
    model_fn = config.new_feature_model
    default_schema = {"result": ""}
    
    def load_inputs(self, run_dir):  # 15 lines
        return {"brief": ..., "data": ...}
    
    def build_prompt(self, inputs):  # 40 lines
        return f"Generate {inputs['brief']}"
    
    def validate(self, output, inputs):  # optional, 5 lines
        return []  # or validation warnings

_instance = StepNewFeature()
def run(run_dir): return _instance.run(run_dir)
```

Plus create: `prompts/step_new_feature.system.md` (external file)

**Result**: 40-50% less code, automatic audit trail, validation hooks, error handling — all free!

---

## Bottom Line

### Before
- 🔴 Duplicate code everywhere
- 🔴 Hard to maintain
- 🔴 No audit trail
- 🔴 No validation
- 🔴 Prompts buried in Python

### After
- ✅ Single source of truth
- ✅ 49% less code per step
- ✅ Complete audit trail
- ✅ Built-in validation
- ✅ Prompts in markdown
- ✅ Easy to extend
- ✅ Easy to test

**And it's all backward compatible!** 🎉
