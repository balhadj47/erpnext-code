# ERPNext Knowledge Audit — Gap Analysis

**Date:** 2026-07-15
**Sources:** `src/skills/bundled/erpnext-knowledge-content.ts`, `src/constants/prompts.ts`, Genesis ERP knowledge base (205 docs)

---

## Currently Covered

| Area | Coverage | Source |
|------|----------|--------|
| DocTypes (JSON structure, field types) | ✅ Complete | prompts.ts, knowledge skill |
| Controllers (validate, on_submit, etc.) | ✅ Complete | knowledge skill |
| hooks.py (fixtures, doc_events, scheduler) | ✅ Complete | knowledge skill |
| patches.txt (migrations) | ✅ Complete | knowledge skill |
| Bench CLI (new-app, migrate, console, etc.) | ✅ Complete | prompts.ts |
| Query Builder (joins, aggregates, filters) | ✅ Complete | knowledge skill |
| Permissions (role matrix, levels) | ✅ Complete | knowledge skill |
| Child Tables (istable, Table fieldtype) | ✅ Complete | knowledge skill |
| Standard DocTypes (all 11 modules) | ✅ Complete | prompts.ts |
| Coding Standards (naming, folder structure) | ✅ Complete | knowledge skill |
| Performance (caching, N+1, indexing) | ✅ Complete | knowledge skill |
| Security (parameterized queries, CSRF, whitelist) | ✅ Complete | knowledge skill |
| Company Standards (deployment checklist) | ✅ Complete | knowledge skill |

---

## Missing Coverage

### High Priority — Core ERPNext Features

| Feature | Status | Why Important |
|---------|--------|---------------|
| **Workflow** | ❌ Missing | DocType state machines (Draft→Submitted→Approved). Fundamental to most business apps. |
| **Property Setter** | ❌ Missing | Override DocType properties without modifying core. Essential for customization. |
| **Background Jobs** | ❌ Missing | `frappe.enqueue()`, scheduled tasks, job monitoring. Every production app needs this. |
| **Notifications** | ❌ Missing | Email alerts, system notifications, webhook triggers. Business-critical. |
| **Print Formats** | ❌ Missing | PDF generation, Jinja templates, custom print layouts. Required for every transactional app. |
| **Web Forms / Portal** | ❌ Missing | Public-facing forms, customer/supplier portals. Common requirement. |
| **REST API** | ❌ Missing | `frappe.whitelist()` is mentioned but REST API patterns, authentication, pagination are not. |
| **Fixture Export/Import** | ⚠️ Partial | Export mentioned but import, fixture versioning, conflict resolution not covered. |

### Medium Priority — Advanced Features

| Feature | Status |
|---------|--------|
| **Server Scripts** | ❌ Missing — `frappe.get_doc().run_script()` |
| **Client Scripts** | ❌ Missing — JS customization without modifying source |
| **Workspace API** | ❌ Missing — programmatic workspace generation |
| **Dashboard Charts** | ⚠️ Partial — mentioned but no chart type reference |
| **Number Cards** | ❌ Missing — dashboard metric cards |
| **Role Profiles** | ❌ Missing — bundled role assignments |
| **Regional Modules** | ❌ Missing — India, Germany, France compliance |
| **Multi-company** | ⚠️ Partial — company field mentioned, but cross-company sharing, inter-company transactions not covered |
| **Localization** | ⚠️ Partial — `frappe._()` mentioned, but translation workflow, .csv format, Transifex integration not covered |
| **Patch Ordering** | ⚠️ Partial — patches.txt format covered, but dependency between patches, `depends_on` attribute not |

### Low Priority — Nice to Have

| Feature | Status |
|---------|--------|
| **Webhooks** | ❌ |
| **Slack/Teams Integration** | ❌ |
| **OAuth2 Providers** | ❌ |
| **Custom Permissions (User Permission)** | ❌ |
| **Document Versioning** | ❌ |
| **Bulk Operations** | ❌ |
| **Calendar Views** | ❌ |
| **Kanban Views** | ❌ |
| **Tree Views** | ❌ |
| **Geolocation Fields** | ❌ |
| **Barcode Fields** | ❌ |
| **Signature Fields** | ❌ |
| **Rating Fields** | ❌ |

---

## Genesis Knowledge Base Portable Content

205 knowledge docs exist but are NOT ported to erpnext-code. Currently only the `erpnext-knowledge-content.ts` skill has a 440-line summary. Full 205-doc port would add:

- 20 Accounting docs
- 18 Stock docs
- 18 HR docs
- 15 CRM docs
- 14 Selling docs
- 14 Reports docs
- 13 Buying docs
- 13 Manufacturing docs
- 13 Permissions docs
- 12 Projects docs
- 10 Support docs
- 9 Website docs
- 5 Assets docs
- 5 Quality docs
- 4 Workflow docs
- 3 Custom Fields docs
- 3 Print Format docs

**Estimated additional content:** ~50,000 lines of reference material.

---

## Recommendations

1. **Add Workflow support immediately** — this is the #1 most-requested ERPNext feature
2. **Add Print Formats** — every transactional DocType needs them
3. **Expand REST API coverage** — the agent needs to know `GET /api/resource/`, `POST`, `PUT`, `DELETE` patterns
4. **Port high-impact knowledge docs** — Accounting (20), Stock (18), HR (18) are the most commonly customized modules
5. **Add a `/erpnext-workflow` skill** — dedicated to state machine definitions

**Knowledge score: 65/100** — solid foundation, 12 high-priority gaps
