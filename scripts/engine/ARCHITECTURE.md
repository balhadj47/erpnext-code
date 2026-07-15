# ERPNext Execution Engine — Architecture v2.0

**Date:** 2026-07-15
**Version:** 2.0 (Production Engineering)

---

## Architecture Overview

```
erpnext_execute.py (thin CLI)
        │
        ▼
engine/pipeline.py (orchestrator)
        │
        ├── engine/gates.py          ← 15 quality gates, stops on failure
        ├── engine/metrics.py        ← Per-phase timing + counters
        ├── engine/rollback.py       ← File snapshots + restore
        ├── engine/scheduler.py      ← Parallel + dependency-aware execution
        ├── engine/planner.py        ← ArtifactGraphBuilder + TaskPlanner
        ├── engine/executor.py       ← IncrementalExecutor + PluginExecutor
        ├── engine/validator.py      ← 5-level validation (syntax→integration)
        ├── engine/recovery.py       ← 12 error classifiers + 8 repair strategies
        ├── engine/journal.py        ← Build journal + health report
        ├── engine/cache.py          ← Pickle-backed mtime cache
        ├── engine/plugins/          ← Auto-discovered plugin implementations
        └── engine/tests/            ← 41 regression tests
```

## Execution Lifecycle

```
1. Snapshot  → RollbackManager saves file state
2. Plan      → ArtifactGraphBuilder scans → TaskPlanner generates tasks
3. Execute   → IncrementalExecutor runs each task:
                 Generate → Validate → Accept | Classify → Repair → Retry
4. Verify    → GateRunner checks all 15 gates:
                 planner → dependency_graph → code_generation → static_validation
                 → python_syntax → json_validation → hooks_validation
                 → fixture_validation → import_validation → bench_migrate
                 → bench_build → unit_tests → browser_verification
                 → analyzer → zero_critical
5. Journal   → BuildJournal writes all artifacts to .builds/<timestamp>/
6. Health    → build_health.md with metrics, gates, repairs, recommendations
7. Rollback  → If gates failed, restore all files to pre-build state
```

## Quality Gates (15)

All gates must pass. Pipeline stops on first failure (strict mode).

| # | Gate | Phase | Depends On |
|---|------|-------|-----------|
| 1 | planner | Plan | — |
| 2 | dependency_graph | Plan | planner |
| 3 | code_generation | Execute | dependency_graph |
| 4 | static_validation | Validate | code_generation |
| 5 | python_syntax | Validate | static_validation |
| 6 | json_validation | Validate | static_validation |
| 7 | hooks_validation | Validate | code_generation |
| 8 | fixture_validation | Validate | json_validation |
| 9 | import_validation | Validate | python_syntax |
| 10 | bench_migrate | Verify | code_generation |
| 11 | bench_build | Verify | bench_migrate |
| 12 | unit_tests | Verify | bench_migrate |
| 13 | browser_verification | Verify | bench_build |
| 14 | analyzer | Verify | code_generation |
| 15 | zero_critical | Verify | analyzer, static_validation |

## Plugin Architecture

Plugins implement interfaces from `engine/interfaces.py`:
- `IAnalyzer` — project analysis
- `IFixer` — auto-repair
- `IVerifier` — browser verification
- `IPlanner` — task planning
- `IExecutor` — task execution
- `IValidator` — file validation
- `IRecovery` — error classification + repair
- `IJournal` — build journal
- `ICache` — filesystem cache

Plugins auto-discovered via `discover_plugins()` — scans `engine/plugins/` directory.
No hardcoded registration needed.

## Rollback

Before any file modification, `RollbackManager.snapshot_file()` saves content + checksum.
If quality gates fail, `rollback()` restores all files in reverse order.
Snapshot state saved to `.builds/<id>/snapshot.json` for audit trail.

## Resume

`--resume` reads `.builds/<latest>/generated_files.json`, marks completed tasks,
skips them in subsequent execution. Never regenerates completed work.

## Parallel Scheduler

Independent tasks execute concurrently via `ThreadPoolExecutor`.
Dependency graph determines parallel groups — tasks in the same group
have no dependencies on each other. Max parallelism configurable (default 4).

## Metrics

Every build tracks:
- Per-phase timing (planning, generation, validation, bench, browser)
- Task counts (completed, failed, blocked, skipped)
- Repair/retry counts
- File counts (generated, modified)
- Issue counts (critical, warnings)
- Success rate

## Journal Format

Each build creates `.builds/<timestamp>_<app>/`:
```
plan.json           — Task plan with dependencies
dependency_graph.json — Full dependency order
generated_files.json — Per-task file manifest
execution.log       — Timestamped execution log
metrics.json        — Build metrics
analyzer.json       — Analyzer output
fixes.json          — Repair history
retries.json        — Retry log
snapshot.json       — Rollback state
final_report.md     — Build summary
build_health.md     — Health report with gates + recommendations
```

## CLI Flags

```
--plan-only      Show task plan, don't execute
--deps           Show dependency graph
--verify-only    Run verification loop only
--dry-run        Simulate without modifying files
--resume         Resume from last build journal
--parallel       Execute independent tasks concurrently
--json           Machine-readable output
--iterations N   Max iterations (default: 3)
--test           Run engine test suite
```

## Test Coverage

41 regression tests across 14 test classes:
- TestQualityGates (5)
- TestMetrics (3)
- TestRollback (3)
- TestScheduler (4)
- TestPluginDiscovery (2)
- TestHealthReport (1)
- TestDryRun (1)
- TestResume (1)
- TestArtifactGraph (4)
- TestValidator (6)
- TestRecovery (4)
- TestJournal (3)
- TestPipeline (2)
- TestCache (2)
