# Architecture Audit — ERPNext Execution Engine

**Date:** 2026-07-15
**Auditor:** Senior Staff Engineer, Production Readiness Review
**Scope:** All 19 Python files in `scripts/engine/` + `scripts/erpnext_*.py`

---

## Critical Findings (4)

### C1: Duplicate `BuildMetrics` — Silent Type Collision

- **Severity:** Critical
- **Files:** `engine/interfaces.py:160`, `engine/metrics.py:24`
- **Problem:** Two completely different `BuildMetrics` dataclasses exist with the same name. `interfaces.py` has one with `total_duration_ms`, `tasks_*`, `repairs_*`, `files_*`. `metrics.py` has another with `planning_time_ms`, `generation_time_ms`, phase timings. Both are used in `pipeline.py` — `journal.record_metrics()` expects interfaces version while `self.metrics_collector.metrics` returns the metrics version. This causes runtime type confusion and JSON serialization failures.
- **Fix:** Rename `metrics.py:BuildMetrics` → `TimingMetrics`. Update all references.

### C2: Module Templates Duplicated in 3 Files

- **Severity:** Critical
- **Files:** `planner.py:213-238`, `executor.py:109-118`, `erpnext_fix.py` (partial)
- **Problem:** `MODULE_TEMPLATES` is defined in `TaskPlanner` (6 modules) and partially duplicated in `PluginExecutor._module_templates` (2 modules). These are divergent copies — adding a module requires changes in multiple places. The fixer also duplicates template generation logic.
- **Fix:** Extract into `engine/templates.py` as a single source of truth.

### C3: `IncrementalExecutor` Violates Liskov Substitution Principle

- **Severity:** Critical
- **Files:** `engine/executor.py:34-37`, `engine/interfaces.py:193-203`
- **Problem:** `IncrementalExecutor` implements `IExecutor` but its `execute()` method raises `NotImplementedError`. You cannot substitute `IncrementalExecutor` for `IExecutor` — the real execution happens through `execute_with_validation()` which takes an `executor_fn` callback. This breaks LSP.
- **Fix:** Remove `IExecutor` interface or make `IncrementalExecutor` not implement it. Use `execute_with_validation` as the primary entry point.

### C4: Pipeline — God Class Anti-Pattern

- **Severity:** Critical
- **Files:** `engine/pipeline.py:36-320`
- **Problem:** `Pipeline` orchestrates 12+ components in a single ~280-line `run()` method. Handles: dry-run, resume, parallel/sequential branching, verification, rollback, journaling, report generation, and metrics. Adding a new execution mode requires modifying this class. Testing requires mocking 12 dependencies.
- **Fix:** Extract `_execute_sequential`, `_execute_parallel`, `_run_verification` into strategy classes. Use composition: `Pipeline(strategy=SequentialStrategy())`.

---

## High Severity (8)

### H1: Fake Verification Gates

- **Files:** `engine/pipeline.py:254-260`
- **Problem:** Five gates (`static_validation`, `python_syntax`, `json_validation`, `hooks_validation`, `fixture_validation`) are unconditionally passed with `gates.pass_gate()` — no actual validation runs. This will give false confidence in production.
- **Fix:** Wire the `StrongValidator` into these gates or mark them as `skip_gate` with reason.

### H2: Duplicate Executor Lambda — 4 Occurrences

- **Files:** `engine/pipeline.py:197,219,229`
- **Problem:** `lambda t, ctx: self.plugin_executor.execute(t, ctx)` appears 4 times.
- **Fix:** Store as `self._executor_fn` in `__init__`.

### H3: Unsafe Pickle in Cache

- **Files:** `engine/cache.py:66-68`
- **Problem:** Uses `pickle.load()` for deserialization. Malicious `.builds/.cache/*.pickle` files can execute arbitrary code. All `ArtifactGraph` fields are JSON-serializable — pickle is unnecessary.
- **Fix:** Replace with JSON serialization.

### H4: Hard-Coded Chromium Path — 3 Occurrences

- **Files:** `scripts/erpnext_browser_verify.py:290,321,418`
- **Problem:** `/tmp/playwright-browsers/chromium-1217/chrome-linux64/chrome` is version-specific and duplicated 3 times. Will break on any Playwright/chromium update.
- **Fix:** Remove `executable_path`, let Playwright auto-discover browsers.

### H5: Fragile Subprocess Plugin Bridge

- **Files:** `engine/plugins/__init__.py:32-88`
- **Problem:** Analyzer, Fixer, Verifier plugins shell out via `subprocess.run()` — 30-60s timeouts, fragile path resolution via `Path(__file__).parent.parent.parent`, Verifier parses output by counting `✓`/`✗` characters.
- **Fix:** Import and call the scripts' Python functions directly — they're all in the same package.

### H6: Broken Plugin Auto-Discovery

- **Files:** `engine/plugins/__init__.py:116`
- **Problem:** `discover_plugins()` imports with `package="engine.plugins"` but the actual package is `scripts.engine.plugins`. Discovery always fails; falls through to hard-coded registry. Discovery code is dead weight.
- **Fix:** Fix package name or remove auto-discovery until it works.

### H7: Regex-Based Python Parsing in 3 Files

- **Files:** `planner.py:197-207`, `erpnext_analyzer.py:87-104`, `erpnext_fix.py:151`
- **Problem:** `_extract_list()` and `_extract_dict_keys()` use regex to parse Python source. Fails on nested brackets, multi-line dicts, comments inside lists. Duplicated across 3 files (~80 lines).
- **Fix:** Create `HooksParser` using `ast.parse` for robust parsing. Share across all modules.

### H8: `Journal.write_report` / `IJournal.write_report` Signature Mismatch

- **Files:** `interfaces.py:261`, `journal.py:129`, `pipeline.py:159`
- **Problem:** Interface says `write_report(build_id)`, Journal says `write_report(build_id, tasks=None, metrics=None)`, Pipeline calls both `write_health_report` and `write_report` which overwrite the same file. Two reports with different content.
- **Fix:** Unify into single `finalize()` call generating one comprehensive report.

---

## Medium Severity (11)

### M1: `ErrorClassifier._PATTERNS` — Mutable Class Dict
- **Files:** `engine/recovery.py:20-43`
- **Fix:** Wrap in `MappingProxyType`.

### M2: Naive `_repair_syntax` Indentation Fix
- **Files:** `engine/recovery.py:98-120`
- **Fix:** Use `autopep8` or only fix after `ast.parse` confirms error.

### M3: `_repair_reference` Always Fails
- **Files:** `engine/recovery.py:164`
- **Fix:** Log specific broken reference; suggest fuzzy match corrections.

### M4: `_resolve_dependencies` — O(n²) Pop
- **Files:** `engine/planner.py:185`
- **Fix:** Use `collections.deque`.

### M5: Validation Level 4 (PERMISSIONS) Skipped
- **Files:** `engine/validator.py:78-106`
- **Fix:** Add permission-level validation block.

### M6: `validate()` Marks All Files as Validated=False on Any Failure
- **Files:** `engine/validator.py:54-56`
- **Fix:** Track per-file validation state.

### M7: `_guess_module` Uses `modules[0]` — Fragile
- **Files:** `engine/executor.py:250-254`
- **Fix:** Accept explicit `module` on `Task`.

### M8: Flaky Cache Test
- **Files:** `engine/tests/__init__.py:301-311`
- **Fix:** Mock mtime check or add sleep.

### M9: `erpnext_analyzer.py` Duplicates ArtifactGraphBuilder
- **Files:** `scripts/erpnext_analyzer.py:133-163`
- **Fix:** Import `ArtifactGraphBuilder` directly; add issue detection layer on top.

### M10: No Timeout on ThreadPoolExecutor Futures
- **Files:** `engine/scheduler.py:89`
- **Fix:** `future.result(timeout=300)`.

### M11: Browser Verify CRUD Test Is a No-Op
- **Files:** `erpnext_browser_verify.py:151-201`
- **Fix:** Fill fields, click Save, verify record exists.

---

## Summary

| Severity | Count | Must Fix |
|----------|-------|----------|
| Critical | 4 | Yes — before production |
| High | 8 | Yes — before production |
| Medium | 11 | Should fix |
| Low | 10 | Nice to fix |

**Architecture score: 62/100**
- Good: Interface-based design, quality gates, journaling, rollback
- Needs work: God class, type collisions, duplicated code, fragile subprocess bridges, fake verification gates
