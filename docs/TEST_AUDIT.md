# Test Coverage Audit — ERPNext Execution Engine

**Date:** 2026-07-15
**Tests:** 41 tests across 14 classes
**Source:** 2 test files, ~630 lines total

---

## Current Coverage

| Module | Lines | Tests | What's Tested | What's NOT Tested |
|--------|-------|-------|---------------|-------------------|
| `gates.py` | 111 | 5 | Gate creation, pass/fail, dependency chain, summary | `strict` mode behavior, gate order enforcement, skip gate |
| `metrics.py` | 127 | 3 | Phase timing, counters, `to_dict()` | Concurrent phase access, negative durations, `start_phase/end_phase` |
| `rollback.py` | 109 | 3 | Snapshot/restore, new file deletion, state save | Binary files, large files, concurrent snapshots, checksum verification |
| `scheduler.py` | 114 | 4 | Sequential, parallel, mixed, parallelism report | Timeout behavior, exception in executor, max_workers limit |
| `plugins/__init__.py` | 144 | 2 | Discovery returns plugins, `get_plugin()` | Subprocess failure, missing scripts, JSON parse errors |
| `journal.py` | 265 | 4 | Build creation, task recording, report + health report | `write_bench_log`, `write_browser_log`, `write_analyzer_result`, invalid build_id |
| `pipeline.py` | 320 | 3 | Dry run, resume flag, empty app | Parallel execution path, `_run_verification`, rollback on failure, strict gates |
| `planner.py` | 306 | 4 | Empty app, doctype scan, child table scan, dep order | All 6 module templates, TaskPlanner integration, `_extract_list/_dict_keys` edge cases |
| `executor.py` | 254 | 0 | NOTHING | No tests at all — 0% coverage |
| `validator.py` | 235 | 6 | Python/JSON syntax, missing permissions, duplicate fields | Level 3 (references), Level 4 (permissions), Level 5 (integration), JS syntax |
| `recovery.py` | 213 | 4 | Classify syntax/json/perm errors, repair trailing comma | 6 other repair strategies, all 8 missing handlers, repeated failure |
| `cache.py` | 88 | 2 | Cache miss, hit (flaky) | Cache invalidation, concurrent access, corrupted pickle, large graphs |
| `interfaces.py` | 319 | 0 | NOTHING (data classes only) | Type validation, serialization round-trips |
| `erpnext_execute.py` | 176 | 0 | NOTHING | CLI argument parsing, all 7 modes |
| `erpnext_analyzer.py` | 310 | 0 | NOTHING | Issue detection, report formatting, JSON output |
| `erpnext_fix.py` | 301 | 0 | NOTHING | All 6 fix operations, `--fix` flag |
| `erpnext_browser_verify.py` | 433 | 0 | NOTHING | Login, navigation, CRUD, reports, dashboards, mobile |

---

## Weak Assertions

| Test | Problem | Fix |
|------|---------|-----|
| `test_cache_hit_after_put` | `if cached: assert...` — passes on cache miss | Remove conditional |
| `test_resume_flag_accepted` | Only checks `build_id` in result | Test that completed tasks are actually skipped |
| `test_discover_plugins` | `assert "analyzer" in plugins or len(plugins) > 0` — overly permissive | Assert all 3 expected plugins present |
| `test_pipeline_plans_and_runs` | Checks `report_path` exists but not its content | Validate report structure |
| `test_dependency_order` | Only checks relative position of 3 out of 4 doctypes | Check full ordering |
| `test_pipeline_handles_empty_app` | Tests that it doesn't crash, not that output is correct | Validate task list is non-empty |

---

## Missing Test Categories

### Integration Tests: 0
- No test runs the full pipeline end-to-end with real generated files
- No test verifies that analyzer + fixer + verifier work together

### Regression Tests: 0
- No historical bug reproduction tests
- No test for the `requesting_code_review` skill integration

### Browser Tests: 0
- No test actually launches Playwright
- All browser verify logic is untested (433 lines)

### ERPNext End-to-End: 0
- No test with a real `bench` command
- No test with real DocType JSON generation and validation

### Error Path Tests: 3 out of 41 (7%)
- Only `test_json_syntax_fail`, `test_python_syntax_fail`, `test_duplicate_fieldnames`
- No test for: corrupted journal, missing build_id, subprocess failure, disk full, permission denied

---

## Estimated True Coverage

| Category | Estimated |
|----------|-----------|
| Line coverage (engine/) | ~35% |
| Branch coverage | ~20% |
| Integration coverage | ~5% |
| Error path coverage | ~7% |
| **Weighted total** | **~25%** |

---

## Quick Wins (add these tests first)

1. `executor.py` — Test `PluginExecutor.execute()` for each task category
2. `recovery.py` — Test all 8 repair strategies
3. `validator.py` — Test validation levels 3, 4, 5
4. `pipeline.py` — Test parallel execution path
5. `cache.py` — Test invalidation on file change
6. `erpnext_analyzer.py` — Test issue detection on a real app scaffold
7. `erpnext_fix.py` — Test all 6 fix operations end-to-end

---

**Test score: 35/100**
