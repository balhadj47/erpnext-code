import { registerBundledSkill } from '../bundledSkills.js'

export function registerERPNextAnalyzerSkill(): void {
  registerBundledSkill({
    name: 'erpnext-analyze',
    description:
      'Analyze an ERPNext app: detect missing fixtures, broken hooks, orphan workspaces, missing permissions, naming issues. Generates a project model report. Usage: /erpnext-analyze <app_path>',
    location: 'bundled',
    userInvocable: true,
    async getPromptForCommand(args: string): Promise<string> {
      return `# ERPNext Project Analyzer

Run the project analyzer on the ERPNext app to detect issues:

\`\`\`bash
python3 scripts/erpnext_analyzer.py ${args || '.'}
\`\`\`

This will:
1. Read hooks.py — doc_events, fixtures, scheduler_events
2. Read modules.txt — check for missing __init__.py
3. Read patches.txt — check naming conventions
4. Parse all DocType JSONs — permissions, istable, is_submittable
5. Count child tables, workspaces, reports, dashboards
6. Generate stats + issues + warnings report

Use \`--json\` flag for machine-readable output.`
    },
  })
}

export function registerERPNextFixSkill(): void {
  registerBundledSkill({
    name: 'erpnext-fix',
    description:
      'Auto-fix common ERPNext app issues: missing __init__.py, missing permissions, missing pyproject.toml, broken hooks fixtures. Usage: /erpnext-fix <app_path>',
    location: 'bundled',
    userInvocable: true,
    async getPromptForCommand(args: string): Promise<string> {
      return `# ERPNext Fix Mode

Auto-detect and fix common ERPNext app issues:

\`\`\`bash
# Detect only (safe, no changes):
python3 scripts/erpnext_fix.py ${args || '.'}

# Auto-fix safe issues:
python3 scripts/erpnext_fix.py ${args || '.'} --fix
\`\`\`

Auto-fixable issues:
- Missing __init__.py in module directories
- DocTypes without permissions (adds System Manager)
- Missing pyproject.toml (generates template)
- Missing README.md / CHANGELOG.md
- Broken hooks.py fixtures (adds missing fixture types)`
    },
  })
}

export function registerERPNextBrowserSkill(): void {
  registerBundledSkill({
    name: 'erpnext-verify',
    description:
      'Browser-based ERPNext app verification: login, navigate, test DocType CRUD, check reports, dashboards, browser console, mobile view. Usage: /erpnext-verify <site_url>',
    location: 'bundled',
    userInvocable: true,
    async getPromptForCommand(args: string): Promise<string> {
      return `# ERPNext Browser Verification

Run browser-based verification of an ERPNext app:

\`\`\`bash
# Quick smoke test (login + 1 DocType):
python3 scripts/erpnext_browser_verify.py ${args || 'http://localhost:8000'} --quick

# Full test suite:
python3 scripts/erpnext_browser_verify.py ${args || 'http://localhost:8000'} --full

# Test specific DocType:
python3 scripts/erpnext_browser_verify.py ${args || 'http://localhost:8000'} --doctype "Sales Order"

# Change credentials:
python3 scripts/erpnext_browser_verify.py ${args || 'http://localhost:8000'} --user admin --password mypass
\`\`\`

Tests:
1. Login — verify authentication works
2. Navigation — Desk, AwesomeBar search
3. DocType CRUD — List view → New form → form rendering
4. Reports — Report builder access
5. Dashboards — Dashboard view
6. Browser Console — Failed resources, JS errors
7. Mobile View — 375px viewport rendering`
    },
  })
}
