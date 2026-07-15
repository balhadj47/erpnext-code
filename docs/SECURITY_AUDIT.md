# Security Audit — ERPNext Execution Engine

**Date:** 2026-07-15
**Scope:** All Python scripts in `scripts/engine/` + `scripts/erpnext_*.py`

---

## Critical (2)

### S1: Unsafe Pickle Deserialization — Remote Code Execution

- **Severity:** Critical
- **Files:** `engine/cache.py:66-68`
- **Problem:** `pickle.load()` deserializes untrusted data from `.builds/.cache/*.pickle`. A malicious pickle file placed on disk (e.g., via a compromised CI runner, shared filesystem, or another process) can execute arbitrary Python code. CVSS 8.4.
- **Fix:** Replace with `json` serialization. All `ArtifactGraph` fields are JSON-compatible.

### S2: `hash()` for Checksums — Unstable, Collision-Prone

- **Severity:** Critical
- **Files:** `engine/rollback.py:58`
- **Problem:** `checksum=str(hash(content))` uses Python's built-in `hash()` which is randomized per process (PYTHONHASHSEED) and not cryptographically secure. Checksums recorded in one run won't match in another. Provides zero integrity guarantee.
- **Fix:** `hashlib.sha256(content.encode()).hexdigest()`.

---

## High (4)

### S3: Hardcoded Chromium Path — Version Pinning

- **Files:** `erpnext_browser_verify.py:290,321,418`
- **Problem:** `/tmp/playwright-browsers/chromium-1217/chrome-linux64/chrome` hard-coded 3 times. Forces specific browser version, breaks on updates, and exposes filesystem layout.
- **Fix:** Remove `executable_path`. Let Playwright discover browsers via `playwright install`.

### S4: Subprocess with User-Controlled Paths

- **Files:** `engine/plugins/__init__.py:37,58,77`
- **Problem:** `AnalyzerPlugin`, `FixerPlugin`, `VerifierPlugin` pass user-provided `app_path` and `site_url` directly to `subprocess.run([sys.executable, ...])`. While `sys.executable` is fixed, the script paths are derived from `Path(__file__).parent.parent.parent` which could be manipulated via symlinks.
- **Fix:** Import modules directly instead of subprocess. Use `shlex.quote()` for any remaining shell arguments.

### S5: Credential Exposure in Subprocess

- **Files:** `erpnext_browser_verify.py:69-73`
- **Problem:** `--password` is accepted as a CLI argument and passed to Playwright. In multi-user systems, `ps aux` can expose the password. No warning about CLI password usage.
- **Fix:** Accept password via environment variable `ERPNEXT_PASSWORD` or prompt on stdin. Document that CLI `--password` is insecure.

### S6: No File Write Validation — Arbitrary Path Write

- **Files:** `engine/journal.py:109`, `engine/executor.py:144-211`
- **Problem:** `GeneratedFile.path` is used directly for file writes without path traversal checks. A malicious `GeneratedFile` with `path="../../../etc/cron.d/backdoor"` could write outside the app directory.
- **Fix:** Validate that resolved `Path(app_path / f.path)` is within `app_path`. Reject paths containing `..`.

---

## Medium (6)

### M1: `eval()`-Like Behavior via `importlib.import_module`

- **Files:** `engine/plugins/__init__.py:116-128`
- **Problem:** `discover_plugins()` uses `importlib.import_module(f".{mod_name}", package="engine.plugins")` which imports and executes arbitrary Python files from the plugins directory. A compromised `.py` file in the plugins directory gains full process access.
- **Mitigation:** This is inherent to Python plugin systems. Document the trust boundary. Consider plugin signing or sandboxing.

### M2: TOCTOU in Rollback Manager

- **Files:** `engine/rollback.py:51-68`
- **Problem:** `snapshot_file` reads file content, then later `restore` writes it back. Between snapshot and restore, another process could modify or replace the file. The restored content would be stale (time-of-check-time-of-use).
- **Fix:** Lock files during snapshot-restore window, or compare mtime before restore.

### M3: No Input Sanitization in Regex Patterns

- **Files:** `engine/recovery.py:20-43`
- **Problem:** `ErrorClassifier._PATTERNS` are hardcoded and safe, but if patterns are ever extended from user input, `re.search(pattern, error_lower)` with user-controlled patterns enables ReDoS (regular expression denial of service).
- **Fix:** Document that patterns must remain hardcoded. Add timeout to regex operations.

### M4: Insecure Temp File Handling in Tests

- **Files:** `engine/tests/__init__.py`, `test_production.py`
- **Problem:** `tempfile.mkdtemp()` and `tempfile.TemporaryDirectory()` are used correctly, but `.builds/` test output accumulates without cleanup between test runs — could leak data.
- **Fix:** Add cleanup in tearDown. Use `tmp_path` fixture if migrating to pytest.

### M5: No HTTPS Enforcement for Browser Verification

- **Files:** `erpnext_browser_verify.py:69`
- **Problem:** Site URL defaults to `http://localhost:8000`. No warning about using HTTPS in production. Credentials sent over plaintext HTTP in local testing.
- **Fix:** Document that production testing should use HTTPS. Add `--insecure` flag requirement for HTTP.

### M6: Unvalidated JSON from Subprocess

- **Files:** `engine/plugins/__init__.py:40-42,61-63`
- **Problem:** `json.loads(result.stdout)` on subprocess output — if the subprocess is compromised (or produces unexpected output), this could raise exceptions that bypass error handling. The `except Exception` catches it but loses the context.
- **Fix:** Validate the JSON schema before processing. Log the raw output on parse failure.

---

## Low (3)

### L1: `sys.executable` in Subprocess — Relies on Same Interpreter

- **Files:** Multiple files
- **Fix:** Document as deliberate design choice for venv consistency.

### L2: No Rate Limiting on Journal Writes

- **Files:** `engine/journal.py`
- **Fix:** Acceptable for single-threaded use. Add file lock if concurrent access becomes possible.

### L3: DEBUG Logging May Leak File Contents

- **Files:** `engine/pipeline.py`, `engine/journal.py`
- **Problem:** Execution logs contain file paths and error messages but no explicit sensitive data filter.
- **Fix:** Add `--redact` flag for production use.

---

## Summary

| Severity | Count | CVSS Range |
|----------|-------|-----------|
| Critical | 2 | 7.0-8.4 |
| High | 4 | 5.0-6.9 |
| Medium | 6 | 3.0-4.9 |
| Low | 3 | 0.1-2.9 |

**Security score: 58/100**
- Critical fixes (pickle, hash) are trivial and must be done immediately.
- Subprocess and path traversal issues require architectural changes in Phase 7.
- Browser credential handling needs hardening before production deployment.
