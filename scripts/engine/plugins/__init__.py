"""Plugin implementations with auto-discovery (Phase 11.8).

Wraps existing standalone scripts as interface implementations.
Supports automatic plugin discovery via importlib.
"""

import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..interfaces import IAnalyzer, IFixer, IVerifier


# ─── Plugin Implementations ────────────────────────────────────────

class AnalyzerPlugin(IAnalyzer):
    """Wraps erpnext_analyzer.py."""

    def __init__(self, scripts_dir: str | None = None):
        if scripts_dir:
            self.script = Path(scripts_dir) / "erpnext_analyzer.py"
        else:
            self.script = Path(__file__).parent.parent.parent / "erpnext_analyzer.py"

    def analyze(self, app_path: str) -> dict:
        if not self.script.exists():
            return {"issues": [], "warnings": [], "stats": {}, "error": "Analyzer script not found"}
        try:
            result = subprocess.run(
                [sys.executable, str(self.script), app_path, "--json"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
            return {"issues": [], "warnings": [], "error": result.stderr[:500] or "Empty output"}
        except Exception as e:
            return {"issues": [], "warnings": [], "error": str(e)}


class FixerPlugin(IFixer):
    """Wraps erpnext_fix.py."""

    def __init__(self, scripts_dir: str | None = None):
        if scripts_dir:
            self.script = Path(scripts_dir) / "erpnext_fix.py"
        else:
            self.script = Path(__file__).parent.parent.parent / "erpnext_fix.py"

    def fix(self, app_path: str) -> dict:
        if not self.script.exists():
            return {"fixes_applied": [], "fixes_skipped": [], "error": "Fixer script not found"}
        try:
            result = subprocess.run(
                [sys.executable, str(self.script), app_path, "--fix", "--json"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
            return {"fixes_applied": [], "fixes_skipped": [], "error": result.stderr[:500] or "Empty output"}
        except Exception as e:
            return {"fixes_applied": [], "fixes_skipped": [], "error": str(e)}


class VerifierPlugin(IVerifier):
    """Wraps erpnext_browser_verify.py."""

    def __init__(self, scripts_dir: str | None = None):
        if scripts_dir:
            self.script = Path(scripts_dir) / "erpnext_browser_verify.py"
        else:
            self.script = Path(__file__).parent.parent.parent / "erpnext_browser_verify.py"

    def verify(self, site_url: str, app_name: str, headless: bool = False) -> dict:
        if not self.script.exists():
            return {"results": [], "passed": 0, "failed": 0, "error": "Verifier script not found"}
        try:
            args = [sys.executable, str(self.script), site_url, "--quick"]
            if headless:
                args.append("--headless")
            result = subprocess.run(args, capture_output=True, text=True, timeout=60)
            passed = result.stdout.count("✓") if result.returncode == 0 else 0
            failed = result.stdout.count("✗") if result.returncode == 0 else 1
            return {"results": [], "passed": passed, "failed": failed}
        except Exception as e:
            return {"results": [], "passed": 0, "failed": 1, "error": str(e)}


# ─── Plugin Discovery (Phase 11.8) ─────────────────────────────────

_PLUGIN_REGISTRY: dict[str, type] = {
    "analyzer": AnalyzerPlugin,
    "fixer": FixerPlugin,
    "verifier": VerifierPlugin,
}


def discover_plugins() -> dict[str, Any]:
    """Auto-discover and instantiate all available plugins.

    Scans the plugins directory for classes implementing IAnalyzer, IFixer, IVerifier.
    Falls back to built-in implementations if discovery fails.
    """
    plugins: dict[str, Any] = {}

    # Try automatic discovery
    try:
        plugins_dir = Path(__file__).parent
        for py_file in plugins_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            mod_name = py_file.stem
            try:
                mod = importlib.import_module(f".{mod_name}", package="engine.plugins")
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if isinstance(attr, type) and attr_name.endswith("Plugin"):
                        for iface_name in ["analyzer", "fixer", "verifier"]:
                            if iface_name in attr_name.lower() and iface_name not in plugins:
                                try:
                                    plugins[iface_name] = attr()
                                except Exception:
                                    pass
            except ImportError:
                continue
    except Exception:
        pass

    # Fall back to registry
    if "analyzer" not in plugins:
        plugins["analyzer"] = AnalyzerPlugin()
    if "fixer" not in plugins:
        plugins["fixer"] = FixerPlugin()
    if "verifier" not in plugins:
        plugins["verifier"] = VerifierPlugin()

    return plugins


def get_plugin(name: str) -> Any | None:
    """Get a plugin by name."""
    return discover_plugins().get(name)
