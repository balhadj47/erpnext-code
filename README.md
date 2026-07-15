<p align="center">
  <img src="assets/screenshot.png" alt="erpnext-code" width="720" />
</p>

<h1 align="center">erpnext-code</h1>

<p align="center">
  <strong>ERPNext v16 Specialist — AI coding agent for Frappe Framework</strong><br>
  Built on free-code. All telemetry stripped. All ERPNext knowledge loaded.<br>
  One binary. Zero hallucinations about Frappe APIs.
</p>

<p align="center">
  <a href="#quick-install"><img src="https://img.shields.io/badge/install-one--liner-blue?style=flat-square" alt="Install" /></a>
  <a href="https://github.com/balhadj47/erpnext-code/stargazers"><img src="https://img.shields.io/github/stars/balhadj47/erpnext-code?style=flat-square" alt="Stars" /></a>
  <a href="https://github.com/balhadj47/erpnext-code/issues"><img src="https://img.shields.io/github/issues/balhadj47/erpnext-code?style=flat-square" alt="Issues" /></a>
  <a href="#features"><img src="https://img.shields.io/badge/features-54%20flags-orange?style=flat-square" alt="Feature Flags" /></a>
</p>

---

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/balhadj47/erpnext-code/main/install.sh | bash
```

Then run `erpnext-code` and set your API key:

```bash
export DEEPSEEK_API_KEY="sk-..."   # Recommended for ERPNext work
# or
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## What This Is

A CLI AI coding agent that **knows ERPNext inside out**. Not a general-purpose assistant — it's laser-focused on building, debugging, and maintaining Frappe Framework v16 and ERPNext v16 custom apps.

Built on [free-code](https://github.com/freecodexyz/free-code), the open build of Claude Code with all telemetry removed, all security prompt guardrails stripped, and all 54 experimental features unlocked.

### What It Knows

- **Frappe Framework v16**: DocTypes, hooks, controllers, permissions, Query Builder
- **ERPNext v16 architecture**: All 16 modules (CRM, Selling, Buying, Stock, Accounting, Manufacturing, HR, Projects, Support, Quality, Assets, etc.)
- **Bench CLI**: `new-app`, `migrate`, `install-app`, `run-tests`, `console`, `export-fixtures`
- **DocType JSON patterns**: Child tables, Link fields, permissions, fixtures
- **Critical rules**: Never uses raw SQL, never modifies core, never invents APIs

### What It Won't Do

- **Never** use raw SQL — always Frappe Query Builder or `frappe.db.sql()` with parameters
- **Never** import from `erpnext.*` in custom app code
- **Never** modify ERPNext core files
- **Never** invent field names or API endpoint names
- **Never** skip hooks.py registration for new DocTypes

---

## Usage

```bash
cd your-erpnext-app/
erpnext-code
```

```
> Build a DocType for Field Service Management with Site Visit tracking
> Debug why hooks.py doc_events aren't firing on Sales Order submit
> Generate fixtures for my custom app
> Review my controller code for security issues
> Add permission roles to all DocTypes in this app
```

### Built-in Commands

| Command | What It Does |
|---------|-------------|
| `/erpnext-knowledge` | Load Frappe/ERPNext reference — DocTypes, hooks, permissions, Query Builder |
| `/plan` | Enter planning mode for complex app features |
| `/review` | Code review an app against Frappe best practices |

Plus all standard agent commands: bash, file read/write/edit, git operations, subagents.

---

## Model Providers

| Provider | Env Variable | Recommended For |
|----------|-------------|-----------------|
| DeepSeek | `DEEPSEEK_API_KEY` | ERPNext work (best value) |
| Anthropic | `ANTHROPIC_API_KEY` | Highest quality |
| OpenAI | `OPENAI_API_KEY` | GPT models |

DeepSeek API is OpenAI-compatible. Set `OPENAI_BASE_URL=https://api.deepseek.com` and `OPENAI_API_KEY` to use DeepSeek through the OpenAI provider path.

---

## What's Different From free-code

| Feature | free-code | erpnext-code |
|---------|-----------|-------------|
| Focus | General coding | ERPNext v16 only |
| System prompt | Generic software engineer | ERPNext specialist with Frappe expertise |
| Knowledge base | None | 205 docs across 16 ERPNext modules |
| Bench CLI | Not mentioned | First-class tool awareness |
| DocType rules | None | Strict validation rules baked in |
| Built-in skills | 14 general | + ERPNext reference knowledge |
| CLAUDE.md | Generic | Frappe conventions, bench commands |

---

## Build From Source

```bash
# Prerequisites: Bun >= 1.3.11
git clone https://github.com/balhadj47/erpnext-code.git
cd erpnext-code
bun install
bun run build:dev:full
./cli-dev
```

---

## Credits

Built on [free-code](https://github.com/freecodexyz/free-code) by [@paoloanzn](https://x.com/paoloanzn) — the free build of Claude Code.

ERPNext specialization, knowledge base, and system prompt by [@balhadj47](https://github.com/balhadj47), ported from [Genesis ERP](https://github.com/balhadj47/genesis-erp).

---

## License

Same as free-code upstream. No license file included in the source snapshot.
