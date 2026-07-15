#!/usr/bin/env python3
"""ERPNext Project Analyzer — ChatGPT Phase 6.5

Analyzes an ERPNext custom app directory and generates a project model report
with detected issues.

Usage:
  python3 erpnext_analyzer.py /path/to/erpnext-app
  python3 erpnext_analyzer.py /path/to/erpnext-app --json  # machine-readable output
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# H7: Use AST-based parsing instead of regex
try:
    from engine.hooks_parser import HooksParser
except ImportError:
    from scripts.engine.hooks_parser import HooksParser


def green(s: str) -> str: return f"\033[32m{s}\033[0m"
def red(s: str) -> str: return f"\033[31m{s}\033[0m"
def yellow(s: str) -> str: return f"\033[33m{s}\033[0m"
def bold(s: str) -> str: return f"\033[1m{s}\033[0m"
def dim(s: str) -> str: return f"\033[2m{s}\033[0m"


class ERPNextAnalyzer:
    def __init__(self, app_path: str):
        self.app_path = Path(app_path).resolve()
        self.app_name = self.app_path.name
        self.issues: list[dict] = []
        self.warnings: list[dict] = []
        self.stats: dict[str, Any] = {}

    def analyze(self) -> dict:
        """Run full analysis and return project model."""
        hooks = self._read_hooks()
        modules = self._read_modules()
        patches = self._read_patches()
        pyproject = self._read_pyproject()
        doctypes = self._find_all_doctypes()
        fixtures = self._analyze_fixtures()
        workspaces = self._find_json_files("workspace")
        reports = self._find_json_files("report")
        dashboards = self._find_json_files("dashboard")

        self._detect_issues(hooks, modules, patches, doctypes, fixtures, workspaces)

        return {
            "app_name": self.app_name,
            "app_path": str(self.app_path),
            "modules": modules,
            "hooks": hooks,
            "patches": patches,
            "pyproject": pyproject,
            "doctypes": doctypes,
            "child_tables": [d for d in doctypes if d.get("istable")],
            "fixtures": fixtures,
            "workspaces": workspaces,
            "reports": reports,
            "dashboards": dashboards,
            "stats": self.stats,
            "issues": self.issues,
            "warnings": self.warnings,
        }

    def _read_hooks(self) -> dict:
        path = self.app_path / "hooks.py"
        if not path.exists():
            self.issues.append({"severity": "critical", "file": "hooks.py", "msg": "hooks.py not found — app is broken"})
            return {}

        parser = HooksParser.from_file(path)  # H7: AST-based parsing
        return parser.parse_hooks()

    def _read_modules(self) -> list:
        path = self.app_path / "modules.txt"
        if not path.exists():
            self.issues.append({"severity": "high", "file": "modules.txt", "msg": "modules.txt not found"})
            return []
        modules = [l.strip() for l in path.read_text().splitlines() if l.strip()]
        for mod in modules:
            mod_path = self.app_path / self.app_name / mod.lower().replace(" ", "_").replace("-", "_")
            init = mod_path / "__init__.py" if mod_path.exists() else None
            if mod_path.exists() and not (mod_path / "__init__.py").exists():
                self.issues.append({"severity": "medium", "file": f"{mod}/__init__.py", "msg": f"Module '{mod}' missing __init__.py"})
        return modules

    def _read_patches(self) -> list:
        path = self.app_path / "patches.txt"
        if not path.exists():
            self.warnings.append({"severity": "low", "file": "patches.txt", "msg": "No patches.txt — no migrations defined"})
            return []
        return [l.strip() for l in path.read_text().splitlines() if l.strip() and not l.startswith("#")]

    def _read_pyproject(self) -> dict | None:
        path = self.app_path / "pyproject.toml"
        if not path.exists():
            self.issues.append({"severity": "high", "file": "pyproject.toml", "msg": "pyproject.toml not found — app not installable via bench"})
            return None
        return {"exists": True}

    def _find_all_doctypes(self) -> list:
        """Find all DocType JSON files and parse them."""
        doctypes = []
        app_module = self.app_path / self.app_name
        if not app_module.exists():
            return doctypes

        for json_file in app_module.rglob("**/doctype/*/*.json"):
            try:
                data = json.loads(json_file.read_text())
                if data.get("doctype") == "DocType":
                    doctypes.append({
                        "name": data.get("name"),
                        "module": data.get("module"),
                        "istable": data.get("istable", 0),
                        "is_submittable": data.get("is_submittable", 0),
                        "field_count": len(data.get("fields", [])),
                        "permissions": len(data.get("permissions", [])),
                        "file": str(json_file.relative_to(self.app_path)),
                        "has_permissions": bool(data.get("permissions")),
                        "has_system_manager": any(
                            p.get("role") == "System Manager" for p in data.get("permissions", [])
                        ),
                    })
            except (json.JSONDecodeError, KeyError):
                self.issues.append({"severity": "high", "file": str(json_file.relative_to(self.app_path)), "msg": "Invalid DocType JSON"})

        self.stats["total_doctypes"] = len(doctypes)
        self.stats["total_child_tables"] = len([d for d in doctypes if d["istable"]])
        self.stats["total_submittable"] = len([d for d in doctypes if d["is_submittable"]])
        return doctypes

    def _find_json_files(self, subdir: str) -> list:
        """Find JSON files in a subdirectory."""
        results = []
        app_module = self.app_path / self.app_name
        if not app_module.exists():
            return results
        for json_file in app_module.rglob(f"**/{subdir}/*.json"):
            results.append(str(json_file.relative_to(self.app_path)))
        return results

    def _analyze_fixtures(self) -> dict:
        """Analyze the fixtures directory."""
        fixtures_dir = self.app_path / self.app_name / "fixtures"
        if not fixtures_dir.exists():
            return {"exists": False, "files": []}
        files = list(fixtures_dir.rglob("*.json"))
        return {
            "exists": True,
            "file_count": len(files),
            "files": [str(f.relative_to(self.app_path)) for f in files],
        }

    def _detect_issues(self, hooks, modules, patches, doctypes, fixtures, workspaces):
        """Run all issue detectors."""
        # Missing fixture registrations
        fixture_types = hooks.get("fixtures", [])
        if fixtures.get("exists") and not fixture_types:
            self.issues.append({"severity": "medium", "file": "hooks.py", "msg": "fixtures/ exists but hooks.py has empty fixtures list"})

        # DocTypes without permissions
        for dt in doctypes:
            if not dt["has_permissions"] and not dt["istable"]:
                self.issues.append({"severity": "high", "file": dt["file"], "msg": f"DocType '{dt['name']}' has no permissions defined"})
            if dt["has_permissions"] and not dt["has_system_manager"] and not dt["istable"]:
                self.warnings.append({"severity": "medium", "file": dt["file"], "msg": f"DocType '{dt['name']}' missing System Manager role"})
            if dt["is_submittable"] and dt["field_count"] < 3:
                self.warnings.append({"severity": "low", "file": dt["file"], "msg": f"Submittable DocType '{dt['name']}' has only {dt['field_count']} fields"})

        # Orphan workspaces
        workspace_modules = set()
        for ws in workspaces:
            mod = Path(ws).parent.name
            workspace_modules.add(mod)
        declared_modules = set(self._module_folders())
        for wm in workspace_modules:
            if wm not in declared_modules:
                self.warnings.append({"severity": "low", "file": f"workspace/{wm}", "msg": f"Workspace for module '{wm}' but module not in modules.txt"})

        # Patch naming convention
        for patch in patches:
            if not re.match(r'v\d+_\d+', patch.split("/")[-1] if "/" in patch else patch):
                self.warnings.append({"severity": "low", "file": "patches.txt", "msg": f"Patch '{patch}' doesn't follow v{major}_{minor}_description convention"})

    def _module_folders(self) -> set:
        """Find actual module folders in the app."""
        app_module = self.app_path / self.app_name
        if not app_module.exists():
            return set()
        modules = set()
        for item in app_module.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                modules.add(item.name)
        return modules

    def print_report(self, model: dict):
        """Print a human-readable report."""
        print()
        print(bold(f"═══ ERPNext Project Analyzer: {model['app_name']} ═══"))
        print()

        # Stats
        print(bold("📊 Statistics"))
        print(f"  Modules:       {len(model['modules'])} ({', '.join(model['modules'])})" if model['modules'] else "  Modules:       0")
        print(f"  DocTypes:      {model['stats'].get('total_doctypes', 0)}")
        print(f"  Child Tables:  {model['stats'].get('total_child_tables', 0)}")
        print(f"  Submittable:   {model['stats'].get('total_submittable', 0)}")
        print(f"  Patches:       {len(model['patches'])}")
        print(f"  Fixtures:      {model['fixtures'].get('file_count', 0)} files")
        print(f"  Workspaces:    {len(model['workspaces'])}")
        print(f"  Reports:       {len(model['reports'])}")
        print(f"  Dashboards:    {len(model['dashboards'])}")
        print(f"  Hooks:         {len(model['hooks'].get('doc_events', []))} doc_events, {len(model['hooks'].get('fixtures', []))} fixture types")
        print()

        # DocTypes
        if model['doctypes']:
            print(bold("📋 DocTypes"))
            for dt in sorted(model['doctypes'], key=lambda d: (d['module'] or '', d['name'] or '')):
                flags = []
                if dt['istable']: flags.append("child")
                if dt['is_submittable']: flags.append("submittable")
                flag_str = f" [{', '.join(flags)}]" if flags else ""
                perm_str = green("✓") if dt['has_permissions'] else red("✗")
                print(f"  {perm_str} {dt['name']}{flag_str} — {dt['field_count']} fields, {dt['permissions']} roles — {dim(dt['file'])}")
            print()

        # Issues
        if model['issues']:
            print(red(bold(f"❌ Issues ({len(model['issues'])})")))
            for i in model['issues']:
                sev = red("CRIT") if i['severity'] == 'critical' else yellow("HIGH") if i['severity'] == 'high' else dim("MED")
                print(f"  [{sev}] {i['msg']} — {dim(i['file'])}")
            print()

        # Warnings
        if model['warnings']:
            print(yellow(bold(f"⚠️  Warnings ({len(model['warnings'])})")))
            for w in model['warnings']:
                print(f"  [{dim(w['severity'].upper())}] {w['msg']} — {dim(w['file'])}")
            print()

        # Summary
        issue_count = len(model['issues'])
        warn_count = len(model['warnings'])
        if issue_count == 0 and warn_count == 0:
            print(green("✅ No issues found. App looks healthy!"))
        elif issue_count == 0:
            print(yellow(f"✅ No critical issues. {warn_count} warnings to review."))
        else:
            print(red(f"⚠️  {issue_count} issues need attention, {warn_count} warnings."))
        print()


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <app_path> [--json]")
        sys.exit(1)

    app_path = sys.argv[1]
    output_json = "--json" in sys.argv

    if not os.path.isdir(app_path):
        print(f"Error: '{app_path}' is not a directory", file=sys.stderr)
        sys.exit(1)

    analyzer = ERPNextAnalyzer(app_path)
    model = analyzer.analyze()

    if output_json:
        print(json.dumps(model, indent=2))
    else:
        analyzer.print_report(model)


if __name__ == "__main__":
    main()
