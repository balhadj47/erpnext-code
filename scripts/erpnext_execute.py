#!/usr/bin/env python3
"""ERPNext Autonomous Execution Engine — thin CLI wrapper

Backward-compatible with the original erpnext_execute.py CLI.
Delegates to engine.pipeline.Pipeline internally.

Usage:
  python3 erpnext_execute.py <app_path> <goal>           # Full pipeline
  python3 erpnext_execute.py <app_path> --plan-only      # Show plan only
  python3 erpnext_execute.py <app_path> --deps           # Dependency graph
  python3 erpnext_execute.py <app_path> --verify-only    # Verification loop
  python3 erpnext_execute.py --test                      # Run test suite
"""

import json
import os
import sys
from pathlib import Path

# Ensure engine package is importable
sys.path.insert(0, str(Path(__file__).parent))

from engine.pipeline import Pipeline
from engine.planner import ArtifactGraphBuilder


GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def main():
    if "--test" in sys.argv:
        from engine.tests import run_tests
        success = run_tests()
        sys.exit(0 if success else 1)

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <app_path> [goal] [options]")
        print(f"\nOptions:")
        print(f"  --plan-only      Show task plan, don't execute")
        print(f"  --deps           Show dependency graph")
        print(f"  --verify-only    Run verification loop only")
        print(f"  --dry-run        Simulate without modifying files")
        print(f"  --resume         Resume from last build journal")
        print(f"  --parallel       Execute independent tasks concurrently")
        print(f"  --json           Machine-readable output")
        print(f"  --iterations N   Max iterations (default: 3)")
        print(f"  --test           Run engine test suite")
        sys.exit(1)

    app_path = sys.argv[1]
    plan_only = "--plan-only" in sys.argv
    deps_only = "--deps" in sys.argv
    verify_only = "--verify-only" in sys.argv
    dry_run = "--dry-run" in sys.argv
    resume = "--resume" in sys.argv
    parallel = "--parallel" in sys.argv
    output_json = "--json" in sys.argv
    iterations = 3

    for i, arg in enumerate(sys.argv):
        if arg == "--iterations" and i + 1 < len(sys.argv):
            iterations = int(sys.argv[i + 1])

    # Find goal
    goal = None
    for arg in sys.argv[2:]:
        if not arg.startswith("--"):
            goal = arg
            break

    if not os.path.isdir(app_path):
        print(f"Error: '{app_path}' is not a directory", file=sys.stderr)
        sys.exit(1)

    goal = goal or "Build ERPNext custom app"

    # ── Dependency graph mode ──
    if deps_only:
        builder = ArtifactGraphBuilder()
        graph = builder.build(app_path)
        print(f"\n{BOLD}📊 Dependency Graph{RESET}")
        if graph.dependency_order:
            for i, dt in enumerate(graph.dependency_order):
                deps = graph.all_doctypes().get(dt, None)
                dep_names = deps.depends_on() if deps else []
                dep_str = f" {DIM}← depends on: {', '.join(dep_names)}{RESET}" if dep_names else ""
                print(f"  {i+1}. {CYAN}{dt}{RESET}{dep_str}")
        else:
            print(f"  {DIM}No DocTypes found in app.{RESET}")
        print()
        return

    # ── Plan only mode ──
    if plan_only:
        builder = ArtifactGraphBuilder()
        graph = builder.build(app_path)
        from engine.planner import TaskPlanner
        planner = TaskPlanner()
        tasks = planner.plan(goal, graph)
        print(f"\n{BOLD}📋 Task Plan ({len(tasks)} tasks){RESET}\n")
        cat_icons = {
            "doctype": "📋", "child_table": "📎", "hook": "🔧", "fixture": "📦",
            "permission": "🔒", "workspace": "🖥️", "report": "📊", "dashboard": "📈",
            "test": "🧪", "verify": "✅", "doc": "📝",
        }
        for t in tasks:
            icon = cat_icons.get(t.category, "•")
            deps = f" {DIM}← after: {', '.join(t.depends_on)}{RESET}" if t.depends_on else ""
            print(f"  {icon} {t.id}: {t.name}{deps}")
        print()
        if output_json:
            print(json.dumps([{"id": t.id, "name": t.name, "category": t.category, "depends_on": t.depends_on} for t in tasks], indent=2))
        return

    # ── Verify only mode ──
    if verify_only:
        from engine.plugins import AnalyzerPlugin, FixerPlugin, VerifierPlugin
        analyzer = AnalyzerPlugin()
        fixer = FixerPlugin()
        verifier = VerifierPlugin()

        site_url = os.environ.get("ERPNEXT_SITE_URL", "http://localhost:8000")

        print(f"\n{BOLD}🔍 Verification Loop{RESET}\n")
        analysis = analyzer.analyze(app_path)
        print(f"  Analysis: {len(analysis.get('issues', []))} issues, {len(analysis.get('warnings', []))} warnings")
        if analysis.get("issues"):
            fix_result = fixer.fix(app_path)
            print(f"  Fix: {len(fix_result.get('fixes_applied', []))} fixes applied")
        browser = verifier.verify(site_url, Path(app_path).name)
        print(f"  Browser: {browser.get('passed', 0)} passed, {browser.get('failed', 0)} failed")
        print()

        if output_json:
            print(json.dumps({"analysis": analysis, "browser": browser}, indent=2, default=str))
        return

    # ── Full pipeline ──
    from engine.plugins import AnalyzerPlugin, FixerPlugin, VerifierPlugin

    pipeline = Pipeline(
        app_path,
        goal,
        analyzer=AnalyzerPlugin(),
        fixer=FixerPlugin(),
        verifier=VerifierPlugin(),
        max_iterations=iterations,
        dry_run=dry_run,
        resume=resume,
        parallel=parallel,
    )
    result = pipeline.run()

    if output_json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"\n{BOLD}═══ Pipeline Complete ═══{RESET}")
        print(f"  Build:   {result['build_id']}")
        print(f"  Report:  {result['report_path']}")
        m = result["metrics"]
        print(f"  Tasks:   {GREEN}{m.get('tasks_completed', 0)} done{RESET}, "
              f"{RED}{m.get('tasks_failed', 0)} failed{RESET}, "
              f"{YELLOW}{m.get('tasks_blocked', 0)} blocked{RESET}")
        print(f"  Fixes:   {m.get('repairs_succeeded', 0)} repairs applied")
        print(f"  Files:   {m.get('files_generated', 0)} generated")
        print()


if __name__ == "__main__":
    main()
