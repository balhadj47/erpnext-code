#!/usr/bin/env python3
"""ERPNext Fix Mode — ChatGPT Phase 6.5

Auto-detects and fixes common ERPNext app issues.

Usage:
  python3 erpnext_fix.py /path/to/erpnext-app           # Detect + report
  python3 erpnext_fix.py /path/to/erpnext-app --fix     # Auto-fix what's safe
  python3 erpnext_fix.py /path/to/erpnext-app --json    # Machine-readable output
"""

import json
import os
import sys
from pathlib import Path


FIXABLE_ISSUES = {
    "missing_init": "Add __init__.py to module directories",
    "missing_permissions": "Add System Manager permissions to DocTypes",
    "missing_pyproject": "Generate pyproject.toml template",
    "missing_readme": "Generate README.md template",
    "missing_changelog": "Generate CHANGELOG.md template",
    "missing_license": "Generate LICENSE file",
    "broken_hooks_fixtures": "Add missing fixture types to hooks.py",
    "orphan_workspace": "Report orphan workspaces (manual fix)",
    "patch_naming": "Report patches with non-standard naming",
    "missing_istable": "Add istable=1 to child table DocTypes",
}


class ERPNextFixer:
    def __init__(self, app_path: str):
        self.app_path = Path(app_path).resolve()
        self.app_name = self.app_path.name
        self.fixes_applied: list[str] = []
        self.fixes_skipped: list[str] = []
        self.issues_detected: list[dict] = []

    def analyze(self):
        """Detect all issues without fixing."""
        self._check_missing_init()
        self._check_missing_files()
        self._check_permissions()
        self._check_hooks()
        return {
            "app_name": self.app_name,
            "issues": self.issues_detected,
            "fixable": [i for i in self.issues_detected if i["type"] in FIXABLE_ISSUES],
        }

    def fix(self):
        """Detect and auto-fix safe issues."""
        self.analyze()
        for issue in self.issues_detected:
            fixer = getattr(self, f"_fix_{issue['type']}", None)
            if fixer:
                try:
                    fixer(issue)
                    self.fixes_applied.append(f"{issue['type']}: {issue.get('msg', '')}")
                except Exception as e:
                    self.fixes_skipped.append(f"{issue['type']}: {e}")
        return {
            "app_name": self.app_name,
            "fixes_applied": self.fixes_applied,
            "fixes_skipped": self.fixes_skipped,
            "remaining_issues": [
                i for i in self.issues_detected
                if not any(i["type"] in f for f in self.fixes_applied)
            ],
        }

    def _check_missing_init(self):
        """Find module dirs without __init__.py."""
        app_module = self.app_path / self.app_name
        if not app_module.exists():
            return
        for item in app_module.iterdir():
            if item.is_dir() and item.name != "__pycache__":
                init_file = item / "__init__.py"
                if not init_file.exists():
                    # Skip if it doesn't look like a module (no doctype subdirs)
                    has_content = any(item.rglob("*.py")) or any(item.rglob("*.json"))
                    if has_content:
                        self.issues_detected.append({
                            "type": "missing_init",
                            "path": str(item.relative_to(self.app_path)),
                            "msg": f"Module directory '{item.name}' missing __init__.py",
                        })

    def _check_missing_files(self):
        """Check for required app files."""
        required = {
            "pyproject.toml": {"type": "missing_pyproject", "severity": "high"},
            "README.md": {"type": "missing_readme", "severity": "medium"},
            "CHANGELOG.md": {"type": "missing_changelog", "severity": "low"},
        }
        for filename, meta in required.items():
            if not (self.app_path / filename).exists():
                self.issues_detected.append({
                    "type": meta["type"],
                    "severity": meta["severity"],
                    "path": filename,
                    "msg": f"{filename} not found",
                })

    def _check_permissions(self):
        """Check DocTypes for missing permissions."""
        app_module = self.app_path / self.app_name
        if not app_module.exists():
            return
        for json_file in app_module.rglob("**/doctype/*/*.json"):
            try:
                data = json.loads(json_file.read_text())
                if data.get("doctype") != "DocType":
                    continue
                if data.get("istable"):
                    continue  # Child tables don't need standalone permissions
                perms = data.get("permissions", [])
                if not perms:
                    self.issues_detected.append({
                        "type": "missing_permissions",
                        "path": str(json_file.relative_to(self.app_path)),
                        "doctype": data.get("name"),
                        "msg": f"DocType '{data.get('name')}' has no permissions",
                    })
            except (json.JSONDecodeError, KeyError):
                pass

    def _check_hooks(self):
        """Check hooks.py for completeness."""
        hooks_path = self.app_path / "hooks.py"
        if not hooks_path.exists():
            return
        content = hooks_path.read_text()

        # Check if fixtures dir exists but hooks may not register all types
        fixtures_dir = self.app_path / self.app_name / "fixtures"
        if fixtures_dir.exists():
            fixture_types_found = set()
            for f in fixtures_dir.rglob("*.json"):
                try:
                    data = json.loads(f.read_text())
                    dt = data.get("doctype")
                    if dt:
                        fixture_types_found.add(dt)
                except (json.JSONDecodeError, KeyError):
                    pass

            import re
            registered = re.findall(r'["\']([^"\']+)["\']', re.search(r'fixtures\s*=\s*\[(.*?)\]', content, re.DOTALL).group(1) if re.search(r'fixtures\s*=\s*\[(.*?)\]', content, re.DOTALL) else "")
            missing = fixture_types_found - set(registered)
            if missing:
                self.issues_detected.append({
                    "type": "broken_hooks_fixtures",
                    "path": "hooks.py",
                    "missing_types": list(missing),
                    "msg": f"Fixture types not registered in hooks.py: {', '.join(missing)}",
                })

    def _fix_missing_init(self, issue: dict):
        path = self.app_path / issue["path"] / "__init__.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Auto-generated by erpnext-code fix mode\n")

    def _fix_missing_pyproject(self, issue: dict):
        content = f"""[project]
name = "{self.app_name}"
version = "0.1.0"
description = "{self.app_name} — ERPNext custom app"
authors = [{{ name = "Developer" }}]
requires-python = ">=3.10"
dependencies = []

[project.entry-points]
frappe = {{
    "{self.app_name}" = "{self.app_name}"
}}
"""
        (self.app_path / "pyproject.toml").write_text(content)

    def _fix_missing_readme(self, issue: dict):
        content = f"""# {self.app_name}

ERPNext custom app.

## Installation

```bash
bench get-app {self.app_name}
bench --site <site> install-app {self.app_name}
```

## Modules

See `modules.txt` for module list.

## License

Proprietary.
"""
        (self.app_path / "README.md").write_text(content)

    def _fix_missing_changelog(self, issue: dict):
        content = """# Changelog

## [0.1.0] — Unreleased
### Added
- Initial app scaffold

[0.1.0]: https://github.com/OWNER/REPO/releases/tag/v0.1.0
"""
        (self.app_path / "CHANGELOG.md").write_text(content)

    def _fix_missing_permissions(self, issue: dict):
        json_path = self.app_path / issue["path"]
        data = json.loads(json_path.read_text())
        data["permissions"] = [
            {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}
        ]
        json_path.write_text(json.dumps(data, indent=2) + "\n")

    def _fix_broken_hooks_fixtures(self, issue: dict):
        hooks_path = self.app_path / "hooks.py"
        content = hooks_path.read_text()
        import re
        match = re.search(r'(fixtures\s*=\s*\[)(.*?)(\])', content, re.DOTALL)
        if not match:
            return
        existing = re.findall(r'"([^"]+)"', match.group(2))
        all_types = sorted(set(existing + issue.get("missing_types", [])))
        new_fixtures = "fixtures = [\n    " + ",\n    ".join(f'"{t}"' for t in all_types) + ",\n]"
        content = re.sub(r'fixtures\s*=\s*\[.*?\]', new_fixtures, content, flags=re.DOTALL)
        hooks_path.write_text(content)

    def print_report(self, result: dict):
        """Print human-readable fix report."""
        print()
        print(f"\033[1m═══ ERPNext Fix Mode: {result['app_name']} ═══\033[0m")
        print()

        if "fixes_applied" in result:
            print(f"\033[32m✅ Fixes Applied ({len(result['fixes_applied'])})\033[0m")
            for f in result["fixes_applied"]:
                print(f"  ✓ {f}")
            print()

            if result["fixes_skipped"]:
                print(f"\033[33m⚠️  Skipped ({len(result['fixes_skipped'])})\033[0m")
                for s in result["fixes_skipped"]:
                    print(f"  ✗ {s}")
                print()

            if result["remaining_issues"]:
                print(f"\033[31m❌ Remaining ({len(result['remaining_issues'])})\033[0m")
                for i in result["remaining_issues"]:
                    print(f"  • {i['msg']} — {i.get('path', '')}")
                print()
            else:
                print("\033[32m✅ All issues fixed!\033[0m")
                print()
        else:
            # Analyze-only mode
            print(f"\033[33mIssues Detected ({len(result['issues'])})\033[0m")
            for i in result["issues"]:
                fixable = "🔧" if i["type"] in FIXABLE_ISSUES else "👁️"
                print(f"  {fixable} [{i['type']}] {i['msg']} — {i.get('path', '')}")
            fixable_count = len([i for i in result["issues"] if i["type"] in FIXABLE_ISSUES])
            if fixable_count:
                print(f"\n  \033[36m{fixable_count} issues auto-fixable. Run with --fix to apply.\033[0m")
            print()


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <app_path> [--fix] [--json]")
        sys.exit(1)

    app_path = sys.argv[1]
    do_fix = "--fix" in sys.argv
    output_json = "--json" in sys.argv

    if not os.path.isdir(app_path):
        print(f"Error: '{app_path}' is not a directory", file=sys.stderr)
        sys.exit(1)

    fixer = ERPNextFixer(app_path)

    if do_fix:
        result = fixer.fix()
    else:
        result = fixer.analyze()

    if output_json:
        print(json.dumps(result, indent=2, default=str))
    else:
        fixer.print_report(result)


if __name__ == "__main__":
    main()
