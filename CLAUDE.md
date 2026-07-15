# CLAUDE.md

This file provides guidance to ERPNext Code when working with ERPNext/Frappe projects.

## Common commands

```bash
# Install dependencies
bun install

# Dev build with all experimental features (./cli-dev)
bun run build:dev:full

# Standard build (./cli)
bun run build

# Run from source without compiling
bun run dev
```

Run the built binary with `./cli-dev`. Set `DEEPSEEK_API_KEY` or `ANTHROPIC_API_KEY` in the environment.

## Frappe/ERPNext conventions (what this agent knows)

- **DocTypes** live in `<app>/<module>/doctype/<name>/` with `<name>.json` and `<name>.py`
- **hooks.py** registers: doc_events, scheduler_events, fixtures, website_context
- **patches.txt** lists migration patches in execution order
- **fixtures/** contains: Custom Field JSONs, Property Setter JSONs, workspace configs
- **Child tables**: set `istable: 1` in DocType JSON, use `Table` fieldtype in parent
- **Links**: `fieldtype: "Link"` with `options: "TargetDocType"`
- **Controller methods**: `frappe.whitelist()` on methods callable from client
- **Permissions**: defined per-role in DocType JSON `permissions` array
- **Naming**: lowercase_underscore for fieldnames, PascalCase for DocType names

## Never do

- Never modify ERPNext core files (frappe/ or erpnext/ directories)
- Never use raw SQL — use Frappe Query Builder or `frappe.db.sql()` with parameters
- Never import from erpnext.* in custom app code
- Never skip hooks.py registration for new DocTypes
- Never invent field names without checking existing DocTypes first

## Always do

- Register every DocType in hooks.py fixtures
- Create migration patches for schema changes
- Test with `bench run-tests` before declaring work done
- Use standard ERPNext DocTypes where possible (add Custom Fields instead of creating new DocTypes)

## High-level architecture

- **Entry point/UI loop**: src/entrypoints/cli.tsx bootstraps the CLI, with the main interactive UI in src/screens/REPL.tsx (Ink/React).
- **Command/tool registries**: src/commands.ts registers slash commands; src/tools.ts registers tool implementations. Implementations live in src/commands/ and src/tools/.
- **LLM query pipeline**: src/QueryEngine.ts coordinates message flow, tool use, and model invocation.
- **Core subsystems**:
  - src/services/: API clients, OAuth/MCP integration, analytics stubs
  - src/state/: app state store
  - src/hooks/: React hooks used by UI/flows
  - src/components/: terminal UI components (Ink)
  - src/skills/: skill system
  - src/plugins/: plugin system
  - src/bridge/: IDE bridge
  - src/voice/: voice input
  - src/tasks/: background task management

## Build system

- scripts/build.ts is the build script and feature-flag bundler. Feature flags are set via build arguments (e.g., `--feature=ULTRAPLAN`) or presets like `--feature-set=dev-full`.
