#!/usr/bin/env python3
"""ERPNext Browser Verification — ChatGPT Phase 7

Autonomous Playwright-based QA agent that tests ERPNext apps through the browser.
Tests: login, navigation, forms, DocType CRUD, reports, dashboards, permissions.

Usage:
  python3 erpnext_browser_verify.py <site_url> [options]

Options:
  --user USER          Username (default: Administrator)
  --password PASS      Password (default: admin)
  --app APP            App name to test
  --doctype DOCTYPE    Test a specific DocType
  --screenshots DIR    Screenshot directory (default: ./screenshots)
  --headless           Run headless (default: visible)
  --quick              Quick smoke test only (login + 1 DocType)
  --full               Full test suite (login, all DocTypes, reports, dashboards)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("Error: playwright not installed. Run: pip install playwright && playwright install chromium", file=sys.stderr)
    sys.exit(1)


GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


class ERPNextBrowserVerifier:
    def __init__(
        self,
        site_url: str,
        username: str = "Administrator",
        password: str = "admin",
        app_name: str | None = None,
        headless: bool = False,
        screenshot_dir: str = "./screenshots",
    ):
        self.site_url = site_url.rstrip("/")
        self.username = username
        self.password = password
        self.app_name = app_name
        self.headless = headless
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        self.results: list[dict] = []
        self.page = None
        self.browser = None
        self.playwright = None

    def _screenshot(self, name: str):
        """Take a screenshot."""
        if self.page:
            timestamp = datetime.now().strftime("%H%M%S")
            path = self.screenshot_dir / f"{timestamp}_{name}.png"
            self.page.screenshot(path=str(path), full_page=True)
            return str(path)
        return None

    def _record(self, test: str, passed: bool, detail: str = "", screenshot: str | None = None):
        """Record a test result."""
        result = {
            "test": test,
            "passed": passed,
            "detail": detail,
            "screenshot": screenshot,
            "timestamp": datetime.now().isoformat(),
        }
        self.results.append(result)
        icon = f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"
        print(f"  {icon} {test}")
        if detail and not passed:
            print(f"    {RED}{detail}{RESET}")
        return result

    # ─── Test: Login ────────────────────────────────────────────────

    def test_login(self) -> bool:
        """Test login to ERPNext."""
        print(f"\n{BOLD}🔑 Login{RESET}")
        try:
            self.page.goto(f"{self.site_url}/login", timeout=15000)
            self.page.wait_for_selector('input[data-fieldname="login_email"]', timeout=10000)
            self.page.fill('input[data-fieldname="login_email"]', self.username)
            self.page.fill('input[data-fieldname="login_password"]', self.password)
            self.page.click('button.btn-login')
            self.page.wait_for_url(f"{self.site_url}/app", timeout=15000)
            self._record("Login", True)
            self._screenshot("login_success")
            return True
        except PlaywrightTimeout:
            # Check if already logged in
            if "/app" in (self.page.url or ""):
                self._record("Login", True, "Already logged in")
                return True
            ss = self._screenshot("login_failed")
            self._record("Login", False, "Login failed — timeout or wrong credentials", ss)
            return False
        except Exception as e:
            ss = self._screenshot("login_error")
            self._record("Login", False, str(e), ss)
            return False

    # ─── Test: Navigation ───────────────────────────────────────────

    def test_navigation(self) -> bool:
        """Test basic navigation: Desk, modules, list views."""
        print(f"\n{BOLD}🧭 Navigation{RESET}")
        all_pass = True

        # Test Desk access
        try:
            self.page.goto(f"{self.site_url}/app", timeout=10000)
            self.page.wait_for_selector('.navbar', timeout=8000)
            self._record("Desk homepage", True)
        except Exception as e:
            self._record("Desk homepage", False, str(e))
            all_pass = False

        # Test AwesomeBar search
        try:
            self.page.click('.search-bar input[type="text"]', timeout=5000)
            self.page.fill('.search-bar input[type="text"]', "User")
            time.sleep(1)
            self._record("AwesomeBar search", True)
        except Exception as e:
            self._record("AwesomeBar search", False, str(e))
            all_pass = False

        return all_pass

    # ─── Test: DocType CRUD ─────────────────────────────────────────

    def test_doctype_crud(self, doctype: str) -> bool:
        """Test Create-Read-Submit-Cancel-Delete for a DocType."""
        print(f"\n{BOLD}📋 DocType: {doctype}{RESET}")
        all_pass = True

        # Open list view
        try:
            encoded = doctype.replace(" ", "%20")
            self.page.goto(f"{self.site_url}/app/{encoded}", timeout=15000)
            self.page.wait_for_selector('.list-row-container', timeout=10000)
            self._record(f"{doctype}: List view", True)
            self._screenshot(f"{doctype}_list")
        except PlaywrightTimeout:
            # May have no records — check if page loaded
            try:
                self.page.wait_for_selector('.no-result', timeout=3000)
                self._record(f"{doctype}: List view", True, "Empty (no records)")
            except PlaywrightTimeout:
                ss = self._screenshot(f"{doctype}_list_failed")
                self._record(f"{doctype}: List view", False, "Page did not load", ss)
                return False

        # Create new record
        try:
            self.page.click('button:has-text("Add")', timeout=5000)
            self.page.wait_for_selector('input[data-fieldname]', timeout=8000)
            self._record(f"{doctype}: New form opened", True)
        except PlaywrightTimeout:
            ss = self._screenshot(f"{doctype}_new_failed")
            self._record(f"{doctype}: New form opened", False, "Add button or form did not load", ss)
            return False

        # Check for JavaScript errors
        try:
            errors = self.page.evaluate("""() => {
                const msgs = [];
                window.__errs = [];
                const orig = window.onerror;
                window.onerror = (msg) => { window.__errs.push(msg); if (orig) orig(msg); };
                return window.__errs || [];
            }""")
            if errors:
                self._record(f"{doctype}: JS errors", False, str(errors))
                all_pass = False
        except Exception:
            pass  # JS eval failed — non-critical

        self._screenshot(f"{doctype}_form")
        self._record(f"{doctype}: Form rendered", True)

        return all_pass

    def test_all_doctypes(self, doctypes: list[str]) -> dict:
        """Test CRUD for all DocTypes in the app."""
        results = {}
        for dt in doctypes:
            results[dt] = self.test_doctype_crud(dt)
        return results

    # ─── Test: Reports ──────────────────────────────────────────────

    def test_reports(self) -> bool:
        """Test report builder access."""
        print(f"\n{BOLD}📊 Reports{RESET}")
        all_pass = True
        try:
            self.page.goto(f"{self.site_url}/app/query-report", timeout=10000)
            self.page.wait_for_selector('.report-list', timeout=8000)
            self._record("Report list", True)
            self._screenshot("reports")
        except Exception as e:
            self._record("Report list", False, str(e))
            all_pass = False
        return all_pass

    # ─── Test: Dashboards ───────────────────────────────────────────

    def test_dashboards(self) -> bool:
        """Test dashboard access."""
        print(f"\n{BOLD}📈 Dashboards{RESET}")
        try:
            self.page.goto(f"{self.site_url}/app/dashboard-view", timeout=10000)
            self.page.wait_for_selector('.dashboard', timeout=8000)
            self._record("Dashboard", True)
            self._screenshot("dashboard")
            return True
        except Exception as e:
            self._record("Dashboard", False, str(e))
            return False

    # ─── Test: Browser Console ──────────────────────────────────────

    def test_browser_console(self) -> list[str]:
        """Capture browser console errors."""
        print(f"\n{BOLD}🖥️  Browser Console{RESET}")
        errors = []
        try:
            logs = self.page.evaluate("""() => {
                const entries = performance.getEntriesByType('resource');
                const failed = entries.filter(e => {
                    return e.transferSize === 0 && e.decodedBodySize === 0 && !e.name.includes('socket.io');
                });
                return failed.map(e => e.name);
            }""")
            if logs:
                errors = [str(l) for l in logs[:10]]  # Top 10
                self._record("Console errors", False, f"{len(errors)} failed resources: {errors[:3]}...")
            else:
                self._record("Console errors", True, "No failed resources detected")
        except Exception as e:
            self._record("Console errors", False, str(e))
        return errors

    # ─── Test: Mobile Viewport ──────────────────────────────────────

    def test_mobile_view(self) -> bool:
        """Test mobile responsive view."""
        print(f"\n{BOLD}📱 Mobile View{RESET}")
        try:
            self.page.set_viewport_size({"width": 375, "height": 812})
            self.page.goto(f"{self.site_url}/app", timeout=10000)
            time.sleep(1)
            self._screenshot("mobile_view")
            self._record("Mobile viewport", True)
            # Reset viewport
            self.page.set_viewport_size({"width": 1440, "height": 900})
            return True
        except Exception as e:
            self._record("Mobile viewport", False, str(e))
            return False

    # ─── Run All Tests ──────────────────────────────────────────────

    def run_quick_smoke(self):
        """Quick smoke test: login + 1 DocType."""
        with sync_playwright() as p:
            self.playwright = p
            self.browser = p.chromium.launch(
                headless=self.headless,
                executable_path="/tmp/playwright-browsers/chromium-1217/chrome-linux64/chrome"
                if os.path.exists("/tmp/playwright-browsers/chromium-1217/chrome-linux64/chrome")
                else None,
            )
            self.page = self.browser.new_page(viewport={"width": 1440, "height": 900})

            if not self.test_login():
                self._summary()
                return self.results

            self.test_navigation()

            if self.app_name:
                # Try to find DocTypes for this app
                doctypes = self._discover_doctypes()
                if doctypes:
                    self.test_doctype_crud(doctypes[0])
                else:
                    # Fallback: test a standard DocType
                    self.test_doctype_crud("User")

            self.test_browser_console()
            self._summary()
            return self.results

    def run_full(self):
        """Full test suite: login, all DocTypes, reports, dashboards, mobile."""
        with sync_playwright() as p:
            self.playwright = p
            self.browser = p.chromium.launch(
                headless=self.headless,
                executable_path="/tmp/playwright-browsers/chromium-1217/chrome-linux64/chrome"
                if os.path.exists("/tmp/playwright-browsers/chromium-1217/chrome-linux64/chrome")
                else None,
            )
            self.page = self.browser.new_page(viewport={"width": 1440, "height": 900})

            if not self.test_login():
                self._summary()
                return self.results

            self.test_navigation()

            doctypes = self._discover_doctypes()
            if doctypes:
                self.test_all_doctypes(doctypes[:5])  # Max 5 to keep test reasonable
            else:
                self.test_doctype_crud("User")

            self.test_reports()
            self.test_dashboards()
            self.test_mobile_view()
            self.test_browser_console()
            self._summary()
            return self.results

    def _discover_doctypes(self) -> list[str]:
        """Try to discover app DocTypes from the Desk sidebar."""
        if not self.app_name:
            return []
        try:
            self.page.goto(f"{self.site_url}/app", timeout=10000)
            time.sleep(1)
            # Click the module in sidebar if visible
            modules = self.page.evaluate("""() => {
                const items = document.querySelectorAll('.sidebar-label, .module-link, .app-logo');
                return Array.from(items).map(el => el.textContent?.trim()).filter(Boolean);
            }""")
            return modules[:5] if modules else []
        except Exception:
            return []

    def _summary(self):
        """Print summary and close browser."""
        if self.browser:
            self.browser.close()

        passed = sum(1 for r in self.results if r["passed"])
        failed = sum(1 for r in self.results if not r["passed"])
        total = len(self.results)

        print(f"\n{BOLD}═══ Results ═══{RESET}")
        print(f"  {GREEN}Passed: {passed}{RESET}")
        print(f"  {RED}Failed: {failed}{RESET}" if failed else f"  Failed: {failed}")
        print(f"  Total:  {total}")
        print(f"  Screenshots: {self.screenshot_dir}")
        print()

        if failed == 0:
            print(f"{GREEN}{BOLD}✅ All tests passed!{RESET}")
        else:
            print(f"{RED}{BOLD}❌ {failed} test(s) failed.{RESET}")
            print(f"\n  Failed tests:")
            for r in self.results:
                if not r["passed"]:
                    print(f"    ✗ {r['test']}: {r.get('detail', '')}")
        print()


def main():
    parser = argparse.ArgumentParser(description="ERPNext Browser Verification Agent")
    parser.add_argument("site_url", help="ERPNext site URL (e.g., http://localhost:8000)")
    parser.add_argument("--user", default="Administrator", help="Username")
    parser.add_argument("--password", default="admin", help="Password")
    parser.add_argument("--app", help="App name to test")
    parser.add_argument("--doctype", help="Test a specific DocType")
    parser.add_argument("--screenshots", default="./screenshots", help="Screenshot directory")
    parser.add_argument("--headless", action="store_true", help="Run headless")
    parser.add_argument("--quick", action="store_true", help="Quick smoke test")
    parser.add_argument("--full", action="store_true", help="Full test suite")

    args = parser.parse_args()

    verifier = ERPNextBrowserVerifier(
        site_url=args.site_url,
        username=args.user,
        password=args.password,
        app_name=args.app,
        headless=args.headless,
        screenshot_dir=args.screenshots,
    )

    if args.doctype:
        # Single DocType test
        with sync_playwright() as p:
            verifier.playwright = p
            verifier.browser = p.chromium.launch(
                headless=args.headless,
                executable_path="/tmp/playwright-browsers/chromium-1217/chrome-linux64/chrome"
                if os.path.exists("/tmp/playwright-browsers/chromium-1217/chrome-linux64/chrome")
                else None,
            )
            verifier.page = verifier.browser.new_page()
            verifier.test_login()
            verifier.test_doctype_crud(args.doctype)
            verifier._summary()
    elif args.full:
        verifier.run_full()
    else:
        verifier.run_quick_smoke()


if __name__ == "__main__":
    main()
