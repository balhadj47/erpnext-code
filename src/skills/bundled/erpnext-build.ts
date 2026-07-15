import { registerBundledSkill } from '../bundledSkills.js'

export function registerERPNextBuildSkill(): void {
  registerBundledSkill({
    name: 'erpnext-build',
    description:
      'Autonomous Execution Engine: plan tasks with dependencies, execute, verify, auto-fix, repeat until green. Usage: /erpnext-build <app_path> "<goal>"',
    location: 'bundled',
    userInvocable: true,
    async getPromptForCommand(args: string): Promise<string> {
      return `# ERPNext Autonomous Execution Engine

Orchestrate the full ERPNext development pipeline:

\`\`\`bash
# Plan + execute full pipeline:
python3 scripts/erpnext_execute.py <app_path> "<goal>"

# Show plan only (no execution):
python3 scripts/erpnext_execute.py <app_path> "<goal>" --plan-only

# Show dependency graph:
python3 scripts/erpnext_execute.py <app_path> "<goal>" --deps

# Verification loop only:
python3 scripts/erpnext_execute.py <app_path> --verify-only

# Machine-readable output:
python3 scripts/erpnext_execute.py <app_path> "<goal>" --json
\`\`\`

## What it does:

1. **Plan** → Break goal into ordered task graph with dependencies
2. **Execute** → Run each task in dependency order
3. **Verify** → bench migrate → analyzer → browser QA
4. **Fix** → If verification fails, auto-fix and retry
5. **Repeat** → Continue until all checks pass (max iterations)

## Known module templates:
- field_service → Site Visit, Inspection Report, Work Order, Crew, Equipment
- contractor → Contractor, Contract, Compliance Check, Trade, Site
- hr_extended → Training Program, Training Event, Certification
- inventory_extended → Stocktake, Stock Reconciliation, Quality Check
- project_extended → Project Phase, Resource Allocation, Variation Order
- maintenance → Asset Maintenance Log, Preventive Schedule

## Dependency graph:
The engine resolves DocType dependencies automatically.
Example: Variation Order → Contract → Customer → Company

Set ERPNEXT_SITE_URL env var for browser verification.`
    },
  })
}
