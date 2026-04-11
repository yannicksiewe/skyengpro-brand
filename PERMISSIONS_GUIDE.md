# SkyEngPro — Permissions & Roles Deep Dive

This document explains every layer of access control used in the platform,
how they interact, and how to troubleshoot permission issues.

---

## The 4 layers of access control

ERPNext/Frappe uses 4 independent layers. ALL must pass for a user to access something.

```
┌─────────────────────────────────────────────────────┐
│ Layer 1: ROLES                                      │
│ "What TYPES of things can this user do?"            │
│ Controls: which DocTypes they can read/write/delete │
│ Set on: User → Roles table                          │
├─────────────────────────────────────────────────────┤
│ Layer 2: MODULE PROFILE                             │
│ "Which MODULES appear in the sidebar?"              │
│ Controls: sidebar workspace visibility              │
│ Set on: User → Module Profile field                 │
├─────────────────────────────────────────────────────┤
│ Layer 3: USER PERMISSIONS                           │
│ "Which RECORDS can this user see?"                  │
│ Controls: data filtering (e.g. only Company=X)     │
│ Set on: User Permission doctype                     │
├─────────────────────────────────────────────────────┤
│ Layer 4: WORKSPACE ROLE RESTRICTIONS                │
│ "Which WORKSPACES appear for this role?"            │
│ Controls: individual workspace visibility           │
│ Set on: Workspace → Roles table                     │
└─────────────────────────────────────────────────────┘
```

---

## Layer 1: Roles — "what can they do?"

Roles control which DocTypes a user can access and what operations they can perform.

### How it works

Each DocType has a **Permission** table (DocPerm) that maps roles to operations:

```
DocType: Employee
  Role: HR Manager     → Read ✓  Write ✓  Create ✓  Delete ✓
  Role: HR User        → Read ✓  Write ✓  Create ✓  Delete ✗
  Role: Employee       → Read ✓  Write ✗  Create ✗  Delete ✗  (if_owner=1)
```

`if_owner=1` means: the user can only read records they own (their own employee record).

### Roles used per profile

#### Platform Admin
| Role | What it unlocks |
|---|---|
| System Manager | EVERYTHING — all DocTypes, all operations, all settings |

#### SkyEngPro Finance
| Role | What it unlocks |
|---|---|
| Accounts Manager | Chart of Accounts, Journal Entry, Payment Entry, Period Closing — full write |
| Accounts User | Invoice, Payment, Ledger — read + create |
| HR User | Employee list, leave balance — read only (for payroll context) |
| Expense Approver | Expense Claim — approve/reject |
| Employee | Own employee self-service |
| Projects User | Timesheet, Project — read + create (for billing) |
| Sales User | Sales Invoice, Quotation — read + create |
| Purchase User | Purchase Invoice, Purchase Order — read + create |

#### SkyEngPro Project Manager
| Role | What it unlocks |
|---|---|
| Projects Manager | Project — full CRUD, can assign users, manage milestones |
| Projects User | Timesheet — read + create |
| HR User | Employee list — read only (to see who to assign to projects) |
| Employee | Own self-service |

#### SkyEngPro Tech Support
| Role | What it unlocks |
|---|---|
| Support Team | Issue (ticket) — full CRUD, Assignment Rule, SLA |
| Projects User | Timesheet — for logging support hours |
| Employee | Own self-service |

#### SkyEngPro Employee / Partner Employee / Company Employee
| Role | What it unlocks |
|---|---|
| Employee | Leave Application — create own, Expense Claim — create own, Salary Slip — read own, Attendance — read own |
| Projects User | Timesheet — create own, Task — read assigned |

#### Company Admin (ALI Capital / MC Capital)
| Role | What it unlocks |
|---|---|
| HR Manager | Employee — full CRUD, Payroll Entry — full, Leave Application — approve |
| HR User | Employee — read + create |
| Accounts Manager | Journal Entry, Chart of Accounts — full |
| Accounts User | Invoice, Payment — read + create |
| Sales Manager | Sales pipeline — full management |
| Sales User | Lead, Quotation, Sales Order — read + create |
| Purchase Manager | Purchase pipeline — full management |
| Purchase User | Purchase Order, Supplier — read + create |
| Projects Manager | Project — full CRUD |
| Projects User | Timesheet — read + create |
| Leave Approver | Leave Application — approve/reject |
| Expense Approver | Expense Claim — approve/reject |
| Stock Manager | Warehouse, Stock Entry — full |
| Stock User | Stock Entry — read + create |
| Support Team | Issue — full CRUD |
| Employee | Own self-service |

#### Company Finance (ALI Capital / MC Capital)
| Role | What it unlocks |
|---|---|
| Accounts Manager | Full accounting access |
| Accounts User | Invoice, Payment — read + create |
| Expense Approver | Expense Claim — approve |
| Sales User | Sales Invoice — read (for revenue tracking) |
| Purchase User | Purchase Invoice — read + create |
| Employee | Own self-service |

#### Partner HR Manager (adorsys)
| Role | What it unlocks |
|---|---|
| HR Manager | Employee — full CRUD within their company |
| HR User | Employee — read + create |
| Leave Approver | Leave Application — approve/reject |
| Expense Approver | Expense Claim — approve/reject |
| Employee | Own self-service |
| Projects User | Timesheet — read + create |
| Sales User | Lead, Opportunity — read (for shared CRM) |

---

## Layer 2: Module Profile — "what modules in the sidebar?"

Module Profiles block entire modules from appearing in the sidebar.
A "module" maps to one or more workspaces.

### How it works

```
Module Profile: "Partner HR Manager"
  Blocked modules: Accounts, CRM, Selling, Buying, Stock, Manufacturing, ...
  Allowed modules: Setup, Core, Frappe, ERPNext, HR, Frappe HR, Payroll, Projects
```

When a user with this profile logs in, they ONLY see workspaces whose
`module` field matches one of the allowed modules.

### Module → Workspace mapping

| Module | Workspaces it controls |
|---|---|
| Setup | Home, ERPNext Settings |
| Core | Users, Welcome Workspace |
| HR | HR, Leaves, Expense Claims, Recruitment, Employee Lifecycle, Performance, Shift & Attendance |
| Frappe HR | (extends HR workspaces) |
| Payroll | Payroll, Salary Payout, Tax & Benefits |
| Projects | Projects |
| Accounts | Accounting, Payables, Receivables, Financial Reports |
| Selling | Selling |
| Buying | Buying |
| CRM | CRM |
| Stock | Stock |
| Support | Support |
| Manufacturing | Manufacturing |
| Quality Management | Quality |
| Automation | Tools |
| Integrations | Integrations |
| ERPNext Integrations | ERPNext Integrations |
| Website | Website |

### Profiles and their allowed modules

| Profile | Allowed modules (everything else blocked) |
|---|---|
| SkyEngPro Finance | Setup, Core, Frappe, ERPNext, Accounts, HR, Frappe HR, Payroll, Buying, Selling, Projects |
| SkyEngPro Project Manager | Setup, Core, Frappe, ERPNext, Projects, HR, Frappe HR |
| SkyEngPro Tech Support | Setup, Core, Frappe, ERPNext, Support, Projects, HR, Frappe HR |
| SkyEngPro Employee | Setup, Core, Frappe, ERPNext, HR, Frappe HR, Payroll, Projects |
| Company Admin | Setup, Core, Frappe, ERPNext, HR, Frappe HR, Payroll, Accounts, Selling, Buying, Stock, CRM, Projects, Support |
| Company Finance | Setup, Core, Frappe, ERPNext, Accounts, Selling, Buying, HR, Frappe HR |
| Partner HR Manager | Setup, Core, Frappe, ERPNext, HR, Frappe HR, Payroll, Projects, CRM, Selling |
| Partner Employee | Setup, Core, Frappe, ERPNext, HR, Frappe HR, Payroll, Projects, Support |
| Employee Self Service Profile | Setup, Core, Frappe, ERPNext, HR, Frappe HR, Payroll, Projects |

---

## Layer 3: User Permissions — "which records can they see?"

This is the DATA ISOLATION layer. It filters every database query.

### How it works

```
User Permission:
  user: admin@alicapital.cm
  allow: Company
  for_value: ALI Capital
  apply_to_all_doctypes: Yes
```

This means: every time `admin@alicapital.cm` queries ANY DocType that has a
`company` field, Frappe automatically adds `WHERE company = 'ALI Capital'`
to the SQL query. They physically cannot see data from other companies.

### Who gets User Permissions

| User type | User Permission | Effect |
|---|---|---|
| Platform Admin | NONE | Sees all companies |
| SkyEngPro Finance | Company=skyengpro Sarl + Company=adorsys | Sees both (EoR management) |
| SkyEngPro PM | Company=skyengpro Sarl + Company=adorsys | Sees both |
| SkyEngPro Tech Support | NONE (needs cross-company tickets) | Sees all |
| SkyEngPro Employee | Company=skyengpro Sarl | Sees only SkyEngPro |
| Company Admin (ALI) | Company=ALI Capital | Sees only ALI Capital |
| Company Finance (ALI) | Company=ALI Capital | Sees only ALI Capital |
| Company Employee (ALI) | Company=ALI Capital | Sees only ALI Capital |
| Partner HR Manager | Company=adorsys | Sees only adorsys |
| Partner Employee | Company=adorsys | Sees only adorsys |

### Employee-level isolation (additional)

For self-service DocTypes, the `Employee` role has `if_owner = 1` permission:

| DocType | What `if_owner` means |
|---|---|
| Leave Application | Employee sees only leaves where `employee = self` |
| Expense Claim | Employee sees only claims where `employee = self` |
| Salary Slip | Employee sees only their own payslip |
| Timesheet | Employee sees only timesheets where `employee = self` |
| Attendance | Employee sees only their own attendance |

So even within the same company, employees can't see each other's salaries.

### Default Company

Each restricted user also gets a **default company** set in `tabDefaultValue`:
```
parent: admin@alicapital.cm
defkey: company
defvalue: ALI Capital
```

This ensures forms pre-fill with the correct company and dashboard charts
load without "Company is mandatory" errors.

---

## Layer 4: Workspace Role Restrictions — "which workspaces in the sidebar?"

Even if a module is allowed (Layer 2), individual workspaces can be hidden
based on roles.

### How it works

Each Workspace has a `roles` child table. If roles are set, ONLY users with
at least one of those roles see the workspace. If no roles are set, everyone
who has the module sees it.

### Current restrictions

| Workspace | Restricted to roles | Who sees it |
|---|---|---|
| ERPNext Settings | System Manager | Admin only |
| Build | System Manager | Admin only |
| Users | System Manager | Admin only |
| Integrations | System Manager | Admin only |
| ERPNext Integrations | System Manager | Admin only |
| Welcome Workspace | System Manager | Admin only |
| HR | HR Manager, HR User | Admin + Finance + PM + Company Admin + Partner HR |
| Recruitment | HR Manager | Admin + Company Admin + Partner HR |
| Employee Lifecycle | HR Manager | Admin + Company Admin + Partner HR |
| Performance | HR Manager | Admin + Company Admin + Partner HR |
| Shift & Attendance | HR Manager | Admin + Company Admin + Partner HR |
| Salary Payout | HR Manager, Accounts Manager | Admin + Finance + Company Admin + Partner HR |
| Tax & Benefits | HR Manager, Accounts Manager | Admin + Finance + Company Admin + Partner HR |
| Payables | Accounts User, Accounts Manager | Admin + Finance + Company Admin/Finance |
| Receivables | Accounts User, Accounts Manager | Admin + Finance + Company Admin/Finance |
| Financial Reports | Accounts User, Accounts Manager | Admin + Finance + Company Admin/Finance |
| Support | Support Team | Admin + Tech Support + Company Admin |

### Workspaces with NO restriction (visible to all with the module)
- Home
- Leaves
- Expense Claims
- Payroll
- Projects
- Accounting
- Buying
- Selling
- CRM
- Stock

---

## Page DocType Permission

Frappe requires explicit `Page` DocType read permission for users to load the
desk UI. Without this, users get "Not permitted for document Page".

### Roles with Page read permission

These roles are added to the `Custom DocPerm` table for the `Page` DocType:

- HR Manager, HR User
- Employee
- Projects User, Projects Manager
- Accounts User, Accounts Manager
- Sales User, Sales Manager
- Purchase User, Purchase Manager
- Stock User, Stock Manager
- Support Team
- Leave Approver, Expense Approver

System Manager and Administrator already have this by default.

---

## How the 4 layers interact — example

**User: `employee@alicapital.cm`**

```
Step 1 — Can they access the desk?
  Layer 1: Has "Employee" role → Page DocType read = YES ✓

Step 2 — What modules appear in sidebar?
  Layer 2: Module Profile = "Employee Self Service Profile"
    Allowed: Setup, Core, Frappe, ERPNext, HR, Frappe HR, Payroll, Projects
    → Sidebar shows: Home, HR-related, Payroll, Projects

Step 3 — Which workspaces within those modules?
  Layer 4: Workspace restrictions filter further:
    HR workspace → requires HR Manager role → HIDDEN ✗
    Recruitment → requires HR Manager → HIDDEN ✗
    Leaves → no restriction → VISIBLE ✓
    Expense Claims → no restriction → VISIBLE ✓
    Payroll → no restriction → VISIBLE ✓
    Projects → no restriction → VISIBLE ✓

Step 4 — What data do they see in those workspaces?
  Layer 3: User Permission = Company: ALI Capital
    → All queries filtered to ALI Capital data only
  Layer 1: Employee role has if_owner=1 on Leave/Expense/Salary
    → Sees only their OWN leave, expenses, payslips

Result: sidebar shows Home, Leaves, Expense Claims, Payroll, Projects.
        Data is filtered to ALI Capital AND their own records only.
```

---

## Troubleshooting

### "Not permitted for document Page"
**Cause:** User's role doesn't have Page DocType read permission.
**Fix:** Check if their role is in `DESK_ACCESS_ROLES` in `config.py`. If not, add it.

### "Company is mandatory"
**Cause:** User has no default company set.
**Fix:** Set via `tabDefaultValue` with `defkey=company`.

### User sees a workspace they shouldn't
**Cause:** Their module is allowed (Layer 2) AND the workspace has no role restriction (Layer 4).
**Fix:** Add a role restriction to the workspace in `WORKSPACE_RESTRICTIONS` in `config.py`.

### User can't see a workspace they should
**Check in order:**
1. Is the module allowed in their Module Profile? (Layer 2)
2. Does the workspace have a role restriction? Do they have the required role? (Layer 4)
3. Is the workspace `public = 1`?

### User can see data from another company
**Cause:** Missing User Permission for Company.
**Fix:** Add `User Permission: Company = <their company>` with `apply_to_all_doctypes=1`.

### Employee can see other employees' salary
**Cause:** The `if_owner` permission isn't set on Salary Slip for Employee role.
**Fix:** Check `DocPerm` for Salary Slip → Employee role should have `if_owner=1`.

### "Page home not found"
**Cause:** The `Setup` module is blocked in the user's Module Profile.
**Fix:** Ensure `Setup` is in the allowed modules list (Home workspace belongs to Setup module).

---

## Where permissions are stored in the database

| What | Table | Key fields |
|---|---|---|
| Role assignments | tabHas Role | parent (user), role |
| DocType permissions | tabDocPerm | parent (DocType), role, read, write, create, delete, if_owner |
| Custom DocType permissions | tabCustom DocPerm | same as above (overrides) |
| Module Profile definitions | tabModule Profile + tabBlock Module | module_profile_name, module |
| User's blocked modules | tabBlock Module (parenttype=User) | parent (user), module |
| User Permissions (data isolation) | tabUser Permission | user, allow, for_value, apply_to_all_doctypes |
| User defaults | tabDefaultValue | parent (user), defkey, defvalue |
| Workspace role restrictions | tabHas Role (parenttype=Workspace) | parent (workspace), role |

---

## Changelog

| Date | Change | Author |
|---|---|---|
| 2026-04-11 | Initial permissions guide | YSI + Claude |
