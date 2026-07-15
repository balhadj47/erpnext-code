"""Plugin implementations with auto-discovery (Phase 11.8).

Wraps existing standalone scripts as interface implementations.
Supports automatic plugin discovery via importlib.
"""

import importlib
import json
import sys
from pathlib import Path
from typing import Any

from ..interfaces import IAnalyzer, IFixer, IVerifier


# Direct imports for H5 fix — no subprocess overhead
# Add scripts dir to path for direct imports
_scripts_dir = Path(__file__).parent.parent.parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))


class AnalyzerPlugin(IAnalyzer):
    """Wraps erpnext_analyzer.py via direct import (H5 fix)."""

    def analyze(self, app_path: str) -> dict:
        try:
            from erpnext_analyzer import ERPNextAnalyzer
            analyzer = ERPNextAnalyzer(app_path)
            model = analyzer.analyze()
            # Convert to dict for interface compatibility
            return {
                "issues": model.get("issues", []),
                "warnings": model.get("warnings", []),
                "stats": model.get("stats", {}),
            }
        except ImportError:
            return {"issues": [], "warnings": [], "stats": {}, "error": "Analyzer module not importable"}
        except Exception as e:
            return {"issues": [], "warnings": [], "error": str(e)}


class FixerPlugin(IFixer):
    """Wraps erpnext_fix.py via direct import (H5 fix)."""

    def fix(self, app_path: str) -> dict:
        try:
            from erpnext_fix import ERPNextFixer
            fixer = ERPNextFixer(app_path)
            result = fixer.fix()
            return {
                "fixes_applied": result.get("fixes_applied", []),
                "fixes_skipped": result.get("fixes_skipped", []),
            }
        except ImportError:
            return {"fixes_applied": [], "fixes_skipped": [], "error": "Fixer module not importable"}
        except Exception as e:
            return {"fixes_applied": [], "fixes_skipped": [], "error": str(e)}


class VerifierPlugin(IVerifier):
    """Wraps erpnext_browser_verify.py.

    NOTE: Uses subprocess because Playwright requires sync_playwright() context manager
    which cannot be cleanly wrapped in a direct function call.
    """

    def verify(self, site_url: str, app_name: str, headless: bool = False) -> dict:
        try:
            from erpnext_browser_verify import ERPNextBrowserVerifier
            verifier = ERPNextBrowserVerifier(
                site_url=site_url,
                app_name=app_name,
                headless=headless,
            )
            results = verifier.run_quick_smoke() if True else verifier.run_full()
            passed = sum(1 for r in results if r.get("passed"))
            failed = sum(1 for r in results if not r.get("passed"))
            return {"results": results, "passed": passed, "failed": failed}
        except ImportError:
            return {"results": [], "passed": 0, "failed": 0, "error": "Verifier module not importable (playwright required)"}
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
                mod = importlib.import_module(f".{mod_name}", package="scripts.engine.plugins")  # H6: correct package name
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
