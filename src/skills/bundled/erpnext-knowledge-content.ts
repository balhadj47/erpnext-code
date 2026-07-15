// ERPNext/Frappe reference knowledge — lazy-loaded
// Ported from Genesis ERP knowledge base: 205 docs across 16 modules

export async function getERPNextModuleKnowledge(module?: string): Promise<string> {
  const base = `# ERPNext v16 / Frappe Framework Reference

## DocType Anatomy

Every DocType has a JSON definition and optional Python controller.

\`\`\`json
{
  "doctype": "DocType",
  "name": "MyDocType",
  "module": "My Module",
  "istable": 0,
  "is_submittable": 0,
  "fields": [
    {"fieldname": "title", "fieldtype": "Data", "label": "Title", "reqd": 1},
    {"fieldname": "status", "fieldtype": "Select", "label": "Status",
     "options": "Draft\\nActive\\nArchived"}
  ],
  "permissions": [
    {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}
  ]
}
\`\`\`

## Field Types Reference

| Fieldtype | Usage | Attributes |
|-----------|-------|------------|
| Data | Short text (max 140-255 chars) | length, options (for Select-in-disguise) |
| Text / Long Text | Long content | — |
| Small Text | Medium text | — |
| Select | Dropdown choices | options (pipe-separated: "Draft\\nActive\\nArchived") |
| Link | Foreign key to another DocType | options="TargetDocType" |
| Dynamic Link | Polymorphic link | options="DocField" for the type field |
| Table / Table MultiSelect | Child records | options="ChildDocType" |
| Currency | Money | — |
| Float / Int | Numbers | precision (Float) |
| Date / Datetime | Dates | — |
| Check | Boolean (0/1 in DB) | — |
| Attach / Attach Image | File upload | — |
| HTML Editor | Rich text | — |
| Button | Action trigger | Controller method |
| Color | Color picker | — |
| Barcode | Barcode scanner | — |
| Geolocation | Map coordinates | — |
| Password | Masked input | — |
| Rating | Star rating | — |
| Signature | Signature pad | — |
| Tab Break | Tab separator in form | — |
| Section Break | Section separator | — |
| Column Break | Column layout | — |
| Image | Image display | options="Image Field" |
| Read Only | Computed display | read_only=1 |
| Heading | Section heading | label only |
| Fold | Collapsible section | — |

## hooks.py Reference

\`\`\`python
# All entries your app should define:

# 1. Fixtures — register custom fields, property setters, etc.
fixtures = ["Custom Field", "Property Setter", "Role Permission"]

# 2. Doc events — hook into standard/core DocType lifecycle
doc_events = {
    "Sales Order": {
        "validate": "your_app.events.sales_order.validate",
        "on_submit": "your_app.events.sales_order.on_submit"
    }
}

# 3. Scheduled tasks
scheduler_events = {
    "daily": [
        "your_app.tasks.daily_cleanup",
        "your_app.tasks.send_reminders"
    ],
    "hourly": ["your_app.tasks.hourly_sync"],
    "cron": {
        "0 0 * * 0": ["your_app.tasks.weekly_report"]  # Every Sunday midnight
    }
}

# 4. Website context (if your app has web views)
website_context = {
    "my_page": "your_app.pages.my_page.get_context"
}

# 5. Override standard DocTypes
override_doctype_class = {
    "Sales Order": "your_app.overrides.sales_order.CustomSalesOrder"
}

# 6. Jinja environment methods
jenv = {
    "methods": ["your_app.utils.jinja_helpers.get_custom_data"]
}

# 7. App include JS
app_include_js = ["/assets/your_app/js/custom_script.js"]

# 8. App include CSS
app_include_css = ["/assets/your_app/css/custom_style.css"]
\`\`\`

## Controller Patterns

\`\`\`python
import frappe
from frappe.model.document import Document

class MyDocType(Document):
    def validate(self):
        """Called before save, every time."""
        if self.value < 0:
            frappe.throw("Value cannot be negative")

    def before_save(self):
        """Called before insert or update."""
        self.full_name = f"{self.first_name} {self.last_name}"

    def before_insert(self):
        """Called only on first save."""
        pass

    def on_submit(self):
        """Called when document is submitted."""
        self.create_journal_entry()

    def on_cancel(self):
        """Called when submitted document is cancelled."""
        self.cancel_journal_entry()

    def autoname(self):
        """Custom naming logic."""
        self.name = f"CUST-{self.customer}-{frappe.utils.today()}"

    @frappe.whitelist()
    def get_customer_balance(self):
        """Whitelisted methods are callable from client-side JS."""
        return frappe.db.get_value("Customer", self.customer, "outstanding_amount")
\`\`\`

## Query Builder (preferred over raw SQL)

\`\`\`python
from frappe.qb import DocType
from frappe.qb.functions import Count, Sum

# Simple select
Item = DocType("Item")
items = (
    frappe.qb.from_(Item)
    .select(Item.name, Item.item_name, Item.standard_rate)
    .where((Item.disabled == 0) & (Item.item_group == "Raw Material"))
    .orderby(Item.item_name)
    .run(as_dict=True)
)

# Join
SO = DocType("Sales Order")
SOItem = DocType("Sales Order Item")
results = (
    frappe.qb.from_(SO)
    .join(SOItem).on(SOItem.parent == SO.name)
    .select(SO.name, SOItem.item_code, SOItem.qty)
    .where(SO.docstatus == 1)
    .run(as_dict=True)
)

# Aggregate
result = (
    frappe.qb.from_(SO)
    .select(Count("*").as_("count"), Sum(SO.grand_total).as_("total"))
    .where(SO.docstatus == 1)
    .run(as_dict=True)
)[0]
\`\`\`

## Permissions Patterns

\`\`\`json
{
  "permissions": [
    {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1},
    {"role": "Accounts Manager", "read": 1, "write": 1, "create": 1, "delete": 0},
    {"role": "Accounts User", "read": 1, "write": 0, "create": 0, "delete": 0}
  ]
}
\`\`\`

Permission levels:
- **0**: No access
- **1**: Full access
- **read**: Can view
- **write**: Can edit
- **create**: Can create new
- **delete**: Can delete
- **submit**: Can submit
- **cancel**: Can cancel
- **amend**: Can amend
- **report**: Can see in reports
- **export**: Can export
- **import**: Can import
- **share**: Can share
- **print**: Can print
- **email**: Can email

## Child Table Patterns

Parent DocType:
\`\`\`json
{"fieldname": "items", "fieldtype": "Table", "options": "MyChildTable", "reqd": 1}
\`\`\`

Child table DocType:
\`\`\`json
{
  "doctype": "DocType",
  "name": "MyChildTable",
  "istable": 1,
  "fields": [
    {"fieldname": "item", "fieldtype": "Link", "options": "Item"},
    {"fieldname": "qty", "fieldtype": "Float"},
    {"fieldname": "rate", "fieldtype": "Currency"}
  ]
}
\`\`\`

## Standard DocTypes (use these, don't recreate)

| Module | Standard DocTypes |
|--------|-------------------|
| CRM | Lead, Opportunity, Customer, Contact, Address, Email Account |
| Selling | Quotation, Sales Order, Sales Invoice, Delivery Note, Sales Taxes and Charges |
| Buying | Supplier, Purchase Order, Purchase Invoice, Purchase Receipt, Request for Quotation |
| Stock | Item, Warehouse, Stock Entry, Stock Reconciliation, Item Group, UOM |
| Accounting | Account, Journal Entry, Payment Entry, Purchase Invoice, Sales Invoice |
| Manufacturing | BOM, Work Order, Job Card, Operation, Workstation |
| HR | Employee, Leave Application, Expense Claim, Salary Slip, Attendance |
| Projects | Project, Task, Timesheet, Activity Type |
| Support | Issue, Maintenance Visit, Warranty Claim |
| Quality | Quality Inspection, Quality Goal, Quality Procedure |
| Assets | Asset, Asset Movement, Asset Maintenance |

## Common Mistakes

1. **Forgetting patches.txt**: Schema changes via bench console that aren't in patches.txt won't run on other environments
2. **Missing istable=1 on child tables**: Without this, child tables won't render properly
3. **Using raw SQL in controllers**: Breaks multi-tenant isolation, bypasses permissions
4. **Importing from erpnext.*** directly**: Use hooks instead; direct imports break on updates
5. **Not whitelisting client-callable methods**: Methods without @frappe.whitelist() are inaccessible from JS
6. **Hardcoding field values in Select**: Use translation functions instead of raw strings
7. **Missing __init__.py in module directories**: Python packages need this file

## Genesis ERP Integration

When working in a Genesis ERP project:
- \`genesis.json\` is the project config (single source of truth)
- \`requirements.md\` contains business requirements
- \`generated/\` holds all pipeline output
- Run \`genesis init <name>\` to create scaffold
- Run \`genesis analyze requirements.md\` for Business Analyst
- Run \`genesis generate\` for full 8-agent pipeline
- Run \`genesis validate-artifacts\` for per-DocType quality checks
- Run \`genesis justify\` to verify custom DocTypes against ERPNext standard

## Best Practices (ChatGPT Phase 3)

### Coding Standards
- **Python**: Follow PEP 8. Use 4-space indentation. Max line length 100 chars.
- **JavaScript**: Use Frappe's built-in ES6 modules. No jQuery for new code.
- **DocType naming**: PascalCase (e.g., \`SiteVisit\`, \`InspectionReport\`)
- **Field naming**: lowercase_underscore (e.g., \`customer_name\`, \`visit_date\`)
- **Module naming**: lowercase, no special chars (e.g., \`field_service\`)
- **Controller methods**: snake_case with descriptive names
- **Whitelisted methods**: prefix with \`get_\`, \`set_\`, \`validate_\`, or describe action

### Folder Structure
\`\`\`
your_app/
├── pyproject.toml          # App metadata + entry points
├── README.md               # App documentation
├── CHANGELOG.md            # Version history
├── hooks.py                # App configuration (REQUIRED)
├── modules.txt             # Module declarations (REQUIRED)
├── patches.txt             # Migration patches (REQUIRED)
├── fixtures/               # Custom Fields, Property Setters, etc.
├── your_app/
│   ├── __init__.py
│   ├── your_module/
│   │   ├── __init__.py
│   │   ├── doctype/
│   │   │   ├── your_doctype/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── your_doctype.json
│   │   │   │   ├── your_doctype.py
│   │   │   │   └── test_your_doctype.py
│   │   │   └── ...
│   │   ├── dashboard/
│   │   │   └── your_doctype.json
│   │   └── workspace/
│   │       └── your_module.json
│   ├── public/
│   │   ├── js/
│   │   └── css/
│   └── templates/
└── tests/
    └── __init__.py
\`\`\`

### Performance
- **Cache heavy queries**: Use \`frappe.cache()\` for frequently accessed data
- **Use \`get_list\` not \`get_all\`**: \`get_list\` respects permissions and limits
- **Avoid N+1 queries**: Use \`frappe.db.get_values()\` for bulk lookups instead of loops
- **Child table writes**: Use \`append()\` on child table, not full replacement
- **Index fields**: Mark frequently filtered fields with \`search_fields\` in DocType
- **Lazy-load JS**: Use \`frappe.require()\` instead of bundling everything

### Security
- **Never trust client input**: Validate all fields in \`validate()\` method
- **Use parameterized queries**: \`frappe.db.sql("... WHERE x=%s", (val,))\` — never f-strings
- **Check permissions**: \`frappe.has_permission()\` before sensitive operations
- **Whitelist carefully**: Only whitelist methods actually needed from client
- **CSRF**: Frappe handles this automatically via \`frappe.request.headers\`
- **Rate limiting**: Use \`frappe.rate_limiter\` decorator for public endpoints
- **File uploads**: Validate file type, size, and scan for malware before processing

### Permissions
- Always include **System Manager** with full access in DocType permissions
- Create role-based permission sets: read-only roles get read=1 only
- Use \`condition\` field in permissions for row-level filtering
- \`if_owner=1\` restricts to document creator
- Test permissions: \`bench execute frappe.tests.test_permissions\`

### Caching
- \`frappe.cache().get_value("key")\` / \`set_value("key", data, expires_in_sec=3600)\`
- \`frappe.cache().hget("hash", "field")\` for hash-based caching
- Clear cache on relevant DocType events via \`on_update\` hook
- Use \`frappe.clear_cache()\` sparingly — it clears everything

### Audit Trail
- Every submitted DocType automatically gets audit trail (version log)
- Use \`frappe.enqueue()\` for audit-related background jobs
- Never bypass \`docstatus\` checks — use proper cancel/amend flow
- Custom audit fields: \`modified_by\`, \`creation\`, \`modified\` are automatic

### Migrations (Patches)
- **One patch per file** in \`patches.txt\`, executed in order
- Patch naming: \`v{major}_{minor}_{description}\` (e.g., \`v1_0_add_status_field\`)
- Patches run once, tracked in \`tabPatch Log\`
- Never run DDL in \`hooks.py\` or \`install.py\` — use patches instead
- Use \`frappe.db.sql()\` in patches, never Query Builder (patch context has no ORM)

### Fixtures
- Export: \`bench --site <site> export-fixtures\`
- Types: Custom Field, Property Setter, Role Permission, Custom Script, Client Script
- Never edit exported fixture JSONs directly — modify in UI, then re-export
- Register all fixture types used in \`hooks.py\` → \`fixtures = ["Custom Field", ...]\`

### Localization
- Use \`frappe._()\` for translatable strings in Python
- Use \`__("text")\` in JavaScript
- Create \`translations/\` directory with \`.csv\` files per language
- Field labels and options should always be translatable

### Multi-Company / Multi-Currency
- Always add \`company\` field to transactional DocTypes
- Use \`frappe.defaults.get_user_default("company")\` for current company
- Currency fields auto-convert when ERPNext multi-currency is enabled
- Test multi-company: verify different companies can't see each other's data

## Company Standards (ChatGPT Phase 10)

### Every App Must Include:
1. **README.md**: Description, install instructions, module list, screenshots
2. **CHANGELOG.md**: Version history in Keep a Changelog format
3. **Tests**: At minimum one test per DocType (\`test_your_doctype.py\`)
4. **Fixtures**: Custom Fields, Property Setters — always exported, never hand-written
5. **Permissions**: Role matrix in every DocType JSON
6. **Translations**: \`translations/\` directory with at least English \`.csv\`
7. **Icons**: App icon in \`public/images/\`, DocType icons set in JSON
8. **Workspace**: At least one workspace JSON per module
9. **Reports**: At minimum a list view report per DocType
10. **Dashboard**: Dashboard JSON per primary DocType showing key metrics
11. **GitHub Actions**: CI pipeline running \`bench run-tests\`
12. **Docker**: Dockerfile or docker-compose for reproducible environments

### Pre-Deployment Checklist:
\`\`\`bash
# 1. All tests pass
bench --site <site> run-tests --app <app_name>

# 2. Migrations run clean
bench --site <site> migrate

# 3. Fixtures are current
bench --site <site> export-fixtures

# 4. No forbidden imports
grep -r "from erpnext" apps/<app_name>/ --include="*.py" && echo "WARNING: core imports found"

# 5. hooks.py is complete
grep -c "fixtures" apps/<app_name>/hooks.py
grep -c "doc_events" apps/<app_name>/hooks.py

# 6. All DocTypes have permissions
for f in apps/<app_name>/**/doctype/*/*.json; do
  python3 -c "import json; d=json.load(open('$f')); assert d.get('permissions'), f'$f missing permissions'"
done
\`\`\`

## Project Memory (ChatGPT Phase 5)

### Files the Agent Should Auto-Read Before Coding:
When entering an ERPNext app directory, read these files in order before making changes:

1. **README.md** — understand app purpose and scope
2. **hooks.py** — know registered DocTypes, events, fixtures
3. **modules.txt** — know app modules
4. **patches.txt** — know applied patches
5. **ARCHITECTURE.md** (if exists) — design decisions and constraints
6. **CHANGELOG.md** (if exists) — recent changes and version history
7. **ROADMAP.md** (if exists) — planned features
8. **genesis.json** (if exists) — project config and phase status

### Before Writing Code:
- Check if the DocType already exists in ERPNext standard
- Check if a Custom Field on a standard DocType would suffice
- Search for similar patterns in the existing app codebase
- Read the relevant DocType's JSON and controller if modifying
- Run existing tests to establish baseline
`

  return base
}
