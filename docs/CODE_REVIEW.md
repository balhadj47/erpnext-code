# Code Review — ERPNext Execution Engine

**Date:** 2026-07-15
**Files Reviewed:** 15 Python files, ~2,750 lines

---

## Large Functions (>30 lines)

| Function | File | Lines | Issue |
|----------|------|-------|-------|
| `Pipeline.run()` | pipeline.py | ~240 | God method — orchestrates 12+ concerns |
| `ERPNextBrowserVerifier.run_full()` | erpnext_browser_verify.py | ~60 | Long test sequence, should be data-driven |
| `StrongValidator._validate_file()` | validator.py | ~120 | Mega-method with 5 validation levels |
| `TaskPlanner.plan()` | planner.py | ~60 | Template detection mixed with task generation |
| `PluginExecutor.execute()` | executor.py | ~45 | Long if-elif chain, should use dispatch dict |
| `ERPNextAnalyzer._detect_issues()` | erpnext_analyzer.py | ~40 | Multiple unrelated checks in one method |
| `TargetedRecovery.repair()` | recovery.py | ~35 | Dispatch dict, but missing handlers |

## Large Classes (>200 lines)

| Class | File | Lines | Issue |
|-------|------|-------|-------|
| `ERPNextBrowserVerifier` | erpnext_browser_verify.py | 350 | Too many test methods, mixed with navigation logic |
| `ERPNextAnalyzer` | erpnext_analyzer.py | 280 | Analysis + formatting in one class |
| `ERPNextFixer` | erpnext_fix.py | 250 | Detection + fixing + reporting in one class |
| `StrongValidator` | validator.py | 220 | 5 validation levels in one class |
| `Pipeline` | pipeline.py | 280 | Orchestrator + executor + verifier |

## Duplicate Logic

| Pattern | Files | Lines |
|---------|-------|-------|
| `_extract_list(contents, key)` | planner.py, erpnext_analyzer.py, erpnext_fix.py | ~30 lines × 3 |
| `_extract_dict_keys(contents, key)` | planner.py, erpnext_analyzer.py | ~15 lines × 2 |
| `MODULE_TEMPLATES` dict | planner.py, executor.py | ~25 lines × 2 |
| DocType scanning loop | planner.py, erpnext_analyzer.py | ~40 lines × 2 |
| `lambda t, ctx: self.plugin_executor.execute(t, ctx)` | pipeline.py | 4 occurrences |
| Chromium executable path | erpnext_browser_verify.py | 3 occurrences |
| `GREEN/RED/YELLOW/CYAN/BOLD/DIM/RESET` color constants | erpnext_execute.py, erpnext_analyzer.py, erpnext_fix.py | ~8 lines × 4 |

## Missing Typing

| File | Missing Annotations |
|------|---------------------|
| `validator.py` | `_validate_*` methods return `list[str]` but untyped |
| `recovery.py` | `repair()` returns `RepairResult` but handlers return untyped |
| `planner.py` | `_resolve_dependencies` parameter `graph` is untyped |
| `executor.py` | `PluginExecutor._guess_module` untyped parameter |
| `journal.py` | `_load_json` return type is `Any` |

## Missing Docstrings

| File | Functions Without Docstrings |
|------|------------------------------|
| `validator.py` | `_validate_doctype_structure`, `_validate_hooks_content`, `_validate_references`, `_validate_hooks_integration` |
| `recovery.py` | All `_repair_*` methods (8 methods) |
| `planner.py` | `_extract_list`, `_extract_dict_keys`, `_resolve_dependencies` |
| `metrics.py` | `start_phase`, `end_phase` |
| `scheduler.py` | `get_parallelism_report` |

## Magic Numbers

| Value | File | Line | Context |
|-------|------|------|---------|
| `3` | recovery.py | Task.max_attempts default |
| `300` | recovery.py | Timeout? Unclear |
| `8000` | erpnext_browser_verify.py | Wait timeout (ms) |
| `1440`, `900` | erpnext_browser_verify.py | Viewport dimensions |
| `375`, `812` | erpnext_browser_verify.py | Mobile viewport |
| `1217` | erpnext_browser_verify.py | Chromium version |
| `30` | plugins/__init__.py | Subprocess timeout |
| `60` | plugins/__init__.py | Browser test timeout |
| `5` | pipeline.py | Max iterations default |

## Complex Conditionals

| Location | Issue |
|----------|-------|
| `executor.py:155` | `"is_submittable": 1 if dt_name in ("Work Order", "Inspection Report") else 0` — template-specific logic in generic code |
| `recovery.py:98-120` | Indentation fix logic has 6 negative conditions in one `if` — hard to reason about |
| `pipeline.py:123` | One-line JSON loading with nested dict comprehension and conditional |
| `erpnext_fix.py:151` | 200-char regex chain with nested groups |

## Poor Error Handling

| Location | Issue |
|----------|-------|
| `plugins/__init__.py:44` | `except Exception as e: return {"error": str(e)}` — swallows all exceptions, loses traceback |
| `executor.py:37` | `raise NotImplementedError` — caller must know to use `execute_with_validation` instead |
| `recovery.py:164` | Unconditional `return RepairResult(success=False)` — doesn't even try |
| `validator.py:126-132` | JS syntax check only counts braces — gives false confidence |

---

## Summary

| Finding | Count |
|---------|-------|
| Large functions (>30 lines) | 7 |
| Large classes (>200 lines) | 5 |
| Duplicate code blocks | 7 patterns, ~150 duplicated lines |
| Missing type annotations | 20+ functions |
| Missing docstrings | 15+ functions |
| Magic numbers | 10 |
| Complex conditionals | 4 |
| Poor error handling | 4 |

**Code quality score: 48/100**

### Quick fixes (low effort, high impact):
1. Extract color constants into `engine/colors.py`
2. Extract regex parsers into `engine/hooks_parser.py`
3. Extract module templates into `engine/templates.py`
4. Replace `lambda t, ctx:` duplicates with method reference
5. Fix `hash()` → `hashlib.sha256`
6. Fix `pickle` → `json` in cache
7. Add type annotations to all public methods
8. Convert magic numbers to named constants
