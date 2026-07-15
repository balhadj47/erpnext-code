# Build Report — 20260715_192754_test_app

**Goal:** Build a test module
**Status:** HEALTHY
**Finished:** 2026-07-15T19:27:54.575126

## Summary

- Generated files: 4
- Validated files: 3 (75%)
- Fixes applied: 0
- Retries: 1
- Final status: ✅ Success

## Quality Gates

- PASS: planner
- PASS: dependency_graph
- PASS: code_generation
- skipped: static_validation
- skipped: python_syntax
- skipped: json_validation
- skipped: hooks_validation
- skipped: fixture_validation
- skipped: import_validation
- skipped: bench_migrate
- skipped: bench_build
- skipped: unit_tests
- pending: browser_verification
- pending: analyzer
- pending: zero_critical

**Result:** 3/15 passed, 0 failed

## Files Generated

- ✓ `pyproject.toml` (toml) [TT1]
- ✓ `pyproject.toml` (toml) [TT2]
- ✗ `test_app/core/workspace/core.json` (json) [TT5]
- ✓ `` () [TT8]

## Fixes Applied

No fixes were needed.

## Retries

- TT5: 3 attempts — test_app/core/workspace/core.json: missing 'fields' array; test_app/core/workspace/core.json: DocTyp

## Performance

- planning: 2ms
- task_T1: 0ms
- task_T2: 0ms
- task_T3: 0ms
- task_T4: 0ms
- task_T5: 0ms
- task_T6: 0ms
- task_T7: 0ms
- task_T8: 0ms
- task_T9: 0ms
- task_T10: 0ms
- task_T12: 0ms
- task_T13: 0ms
- validation: 0ms
- bench: 0ms

- Success rate: 84.6%
- Repairs: 0
- Critical issues: 0

## Recommendations

- 1 files failed validation
