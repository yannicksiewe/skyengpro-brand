# SkyEngPro EoR — Role & Access Design

This document defines the role architecture for the SkyEngPro ERPNext platform.
Edit this file to adjust roles, permissions, and workspace visibility before
running the automated setup.

---

## Platform Overview

```
SkyEngPro (parent company) ──────────────────────────────────────
├── INTERNAL STAFF (Level 1) ── sees all SkyEngPro + all partners
│   ├── 1A. Platform Admin ──── full system access
│   ├── 1B. Finance ─────────── accounting, invoicing, payroll
│   ├── 1C. Project Manager ─── projects, timesheets, resources
│   ├── 1D. Tech Support ────── support tickets, maintenance
│   └── 1E. Employee ─────────── self-service (same as partner employee)
│
├── Partner A (child company) ── sees only Partner A data
│   ├── 2A. Partner HR Manager ─ manages Partner A employees
│   └── 2B. Partner Employee ─── self-service only
│
├── Partner B (child company)
│   ├── 2A. Partner HR Manager
│   └── 2B. Partner Employee
└── ...
```

---

## LEVEL 1 — SkyEngPro Internal Staff

> All Level 1 users belong to SkyEngPro parent company.
> They can see ALL companies' data (no Company restriction).

---

### 1A. Platform Admin

> Full system access. Manages the platform, users, companies, settings.

| Field | Value |
|---|---|
| Profile name | `Platform Admin` |
| Example user | `yannick.siewe@gmail.com` |
| Module Profile | none (no restrictions) |
| Data scope | All companies |

#### Roles
- System Manager
- All other roles (full access)

#### Sees
- Everything — all workspaces, all modules, all companies

#### Can do
- Everything: create companies, manage users, configure system
- See all employees across all partner companies
- Generate cross-company reports
- Deploy updates, manage integrations

---

### 1B. SkyEngPro Finance

> Internal finance team. Handles accounting, invoicing, payroll processing.

| Field | Value |
|---|---|
| Profile name | `SkyEngPro Finance` |
| Module Profile | `SkyEngPro Finance` |
| Data scope | All companies (cross-company billing/payroll) |

#### Roles
- Accounts Manager
- Accounts User
- HR User (read-only for payroll context)
- Expense Approver
- Employee

#### Allowed modules (unblocked)
- Setup, Core, Frappe, ERPNext
- Accounts
- HR
- Frappe HR
- Payroll
- Buying
- Selling
- Projects

#### Workspace visibility

| Workspace | Visible | Notes |
|---|---|---|
| Home | ✅ | |
| Accounting | ✅ | Full access |
| Payables | ✅ | Vendor bills, payments |
| Receivables | ✅ | Client invoices |
| Financial Reports | ✅ | P&L, balance sheet |
| Buying | ✅ | Purchase orders |
| Selling | ✅ | Sales invoices |
| HR | ✅ | Read-only, for payroll context |
| Payroll | ✅ | Process payroll across companies |
| Salary Payout | ✅ | |
| Tax & Benefits | ✅ | |
| Expense Claims | ✅ | Approve expenses |
| Projects | ✅ | For billing context |
| CRM | ❌ | |
| Manufacturing | ❌ | |
| Stock | ❌ | |
| Quality | ❌ | |
| Support | ❌ | |
| Website | ❌ | |
| ERPNext Settings | ❌ | |
| Build | ❌ | |
| Users | ❌ | |

#### Can do
- Manage chart of accounts, journals, invoices
- Process payroll for all companies
- Approve expense claims
- Generate financial reports across companies
- Manage buying/selling transactions

#### Cannot do
- Change system settings
- Manage users
- Access CRM, manufacturing, stock

---

### 1C. SkyEngPro Project Manager

> Manages projects, assigns tasks, reviews timesheets across all companies.

| Field | Value |
|---|---|
| Profile name | `SkyEngPro Project Manager` |
| Module Profile | `SkyEngPro Project Manager` |
| Data scope | All companies |

#### Roles
- Projects Manager
- Projects User
- HR User (read-only, to see employee assignments)
- Employee

#### Allowed modules (unblocked)
- Setup, Core, Frappe, ERPNext
- Projects
- HR
- Frappe HR

#### Workspace visibility

| Workspace | Visible | Notes |
|---|---|---|
| Home | ✅ | |
| Projects | ✅ | Full project management |
| HR | ✅ | Read-only, see employee list |
| Leaves | ✅ | See team availability |
| Payroll | ❌ | |
| Accounting | ❌ | |
| CRM | ❌ | |
| Selling | ❌ | |
| Buying | ❌ | |
| *(all others)* | ❌ | |

#### Can do
- Create and manage projects
- Assign tasks to employees across companies
- Review and approve timesheets
- View team leave calendar (for resource planning)
- Generate project reports

#### Cannot do
- Access financials (payroll, accounting, invoices)
- Manage HR (recruitment, lifecycle)
- Change system settings

---

### 1D. SkyEngPro Tech Support

> Handles support tickets and technical maintenance for partner companies.

| Field | Value |
|---|---|
| Profile name | `SkyEngPro Tech Support` |
| Module Profile | `SkyEngPro Tech Support` |
| Data scope | All companies |

#### Roles
- Support Team
- Projects User
- Employee

#### Allowed modules (unblocked)
- Setup, Core, Frappe, ERPNext
- Support
- Projects
- HR
- Frappe HR

#### Workspace visibility

| Workspace | Visible | Notes |
|---|---|---|
| Home | ✅ | |
| Support | ✅ | Tickets, SLA, maintenance |
| Projects | ✅ | For technical projects |
| HR | ❌ | |
| Payroll | ❌ | |
| Accounting | ❌ | |
| *(all others)* | ❌ | |

#### Can do
- Manage support tickets (create, assign, resolve)
- Track SLAs and response times
- Work on technical projects
- View employee contact info (for ticket assignment)

#### Cannot do
- Access HR data (payroll, leave, expenses)
- Access financials
- Change system settings

---

### 1E. SkyEngPro Employee

> Internal SkyEngPro staff who use self-service features.
> Same access as Partner Employee (Level 2B) but belongs to SkyEngPro company.

| Field | Value |
|---|---|
| Profile name | `SkyEngPro Employee` |
| Module Profile | `Employee Self Service Profile` |
| Data scope | Own records only (SkyEngPro company) |

#### Roles
- Employee
- Projects User

#### Workspace visibility
- *(Same as Level 2B — Partner Employee below)*

#### Can do
- *(Same as Level 2B — Partner Employee below)*

---

## LEVEL 2 — Independent Company Admin (ALI Capital / MC Capital)

> Separate people who manage their own standalone business.
> Full access to THEIR company only. Cannot see SkyEngPro or other accounts.

---

### 2. Company Admin

> One per independent company. Full business management within their company.

| Field | Value |
|---|---|
| Profile name | `Company Admin` |
| Example users | `admin@alicapital.com`, `admin@mccapital.com` |
| Module Profile | `Company Admin` |
| Data scope | Own company only (via User Permission) |

#### Roles
- HR Manager
- HR User
- Accounts Manager
- Accounts User
- Sales Manager
- Sales User
- Purchase Manager
- Purchase User
- Projects Manager
- Projects User
- Leave Approver
- Expense Approver
- Stock Manager
- Stock User
- Employee

#### Allowed modules (unblocked)
- Setup, Core, Frappe, ERPNext
- HR, Frappe HR, Payroll
- Accounts, Selling, Buying, Stock
- CRM, Projects, Support

#### Blocked modules
- Manufacturing
- Quality Management
- Website
- Automation (Tools)
- Integrations
- ERPNext Integrations
- Telephony, EDI, Subcontracting, Bulk Transaction
- Regional, Maintenance, Portal
- Lead Syncing, FCRM
- Payment Gateways, Payments

#### Workspace visibility

| Workspace | Visible | Notes |
|---|---|---|
| Home | ✅ | |
| Accounting | ✅ | Full access (own company) |
| Payables | ✅ | |
| Receivables | ✅ | |
| Financial Reports | ✅ | |
| Buying | ✅ | |
| Selling | ✅ | |
| HR | ✅ | Full HR management |
| Leaves | ✅ | |
| Expense Claims | ✅ | |
| Recruitment | ✅ | |
| Employee Lifecycle | ✅ | |
| Performance | ✅ | |
| Shift & Attendance | ✅ | |
| Payroll | ✅ | |
| Salary Payout | ✅ | |
| Tax & Benefits | ✅ | |
| CRM | ✅ | Own leads/opportunities |
| Projects | ✅ | |
| Support | ✅ | Own tickets |
| Stock | ✅ | If needed |
| Manufacturing | ❌ | |
| Quality | ❌ | |
| Website | ❌ | |
| Users | ❌ | Only Platform Super Admin |
| ERPNext Settings | ❌ | Only Platform Super Admin |
| Build | ❌ | |
| Tools | ❌ | |

#### Can do
- Everything within their company (HR, accounting, CRM, projects, support)
- Run payroll, approve expenses, manage employees
- Create sales/purchase invoices
- Manage their own CRM pipeline

#### Cannot do
- See any other company's data (SkyEngPro, other accounts)
- Access system settings
- Manage platform users (only Super Admin)
- See consolidated reports across accounts

---

### 2-F. Company Finance

> Finance staff for independent companies (ALI / MC Capital).

| Field | Value |
|---|---|
| Profile name | `Company Finance` |
| Module Profile | `Company Finance` |
| Data scope | Own company only |

#### Roles
- Accounts Manager
- Accounts User
- Expense Approver
- Employee

#### Workspace visibility
| Workspace | Visible |
|---|---|
| Home | ✅ |
| Accounting | ✅ |
| Payables | ✅ |
| Receivables | ✅ |
| Financial Reports | ✅ |
| Buying | ✅ |
| Selling | ✅ |
| Expense Claims | ✅ |
| *(all others)* | ❌ |

---

### 2-E. Company Employee

> Self-service employee for independent companies (ALI / MC Capital).
> Same as Level 3 Partner Employee below.

| Field | Value |
|---|---|
| Profile name | `Company Employee` |
| Module Profile | `Employee Self Service Profile` |
| Data scope | Own records only + own company |

#### Roles
- Employee
- Projects User

#### Workspace visibility
- *(Same as Level 3B — Partner Employee)*

---

## LEVEL 3 — EoR Partner Company Users (under SkyEngPro)

> Partner users are restricted to their own partner company
> via User Permission on Company field.

---

### 2A. Partner HR Manager

> One per client company. Manages their own employees.

| Field | Value |
|---|---|
| Profile name | `Partner HR Manager` |
| Example user | `lausonobase.odine@adorsys.com` |
| Module Profile | `Partner HR Manager` |
| Data scope | Own company only (via User Permission) |

#### Roles
- HR Manager
- HR User
- Leave Approver
- Expense Approver
- Employee
- Projects User

#### Allowed modules (unblocked)
- Setup (for Home workspace)
- Core (for desk functionality)
- Frappe (framework)
- ERPNext (base)
- HR
- Frappe HR (HRMS app module)
- Payroll
- Projects

#### Blocked modules (everything else)
<!-- Add or remove from this list to adjust what the HR Manager sees -->
- Accounts
- CRM
- FCRM
- Selling
- Buying
- Stock
- Manufacturing
- Quality Management
- Support
- Assets
- Website
- Automation (Tools)
- Integrations
- ERPNext Integrations
- Telephony
- Communication
- EDI
- Subcontracting
- Bulk Transaction
- Regional
- Maintenance
- Portal
- Utilities
- Social
- Contacts
- Printing
- Desk
- Geo
- Custom
- Email
- Workflow
- Lead Syncing
- Payment Gateways
- Payments

#### Workspace visibility

| Workspace | Visible | Notes |
|---|---|---|
| Home | ✅ | |
| HR | ✅ | Main HR workspace |
| Leaves | ✅ | Approve/reject leave requests |
| Expense Claims | ✅ | Approve/reject expenses |
| Recruitment | ✅ | Manage job openings, applicants |
| Employee Lifecycle | ✅ | Onboarding, transfers, separation |
| Performance | ✅ | Appraisals, goals |
| Shift & Attendance | ✅ | Manage shifts, attendance |
| Payroll | ✅ | Run payroll, view all payslips |
| Salary Payout | ✅ | Process payouts |
| Tax & Benefits | ✅ | Tax slabs, benefits |
| Projects | ✅ | Manage projects, view timesheets |
| Accounting | ❌ | |
| CRM | ❌ | |
| Selling | ❌ | |
| Buying | ❌ | |
| *(all others)* | ❌ | |

#### Can do
- View and manage ALL employees in their company
- Approve/reject leave requests
- Approve/reject expense claims
- Run payroll for their company
- View all timesheets in their company
- Manage projects assigned to their company
- Recruit new employees (create applicants, job openings)

#### Cannot do
- See other companies' data
- Access Accounting, CRM, Selling, Buying
- Change system settings
- Create or manage users (only Platform Admin can onboard)

---

### 2B. Partner Employee (Self-Service)

> Individual employees. Can only see and manage their own data.

| Field | Value |
|---|---|
| Profile name | `Partner Employee` |
| Example user | `ysi@adorsys.com` |
| Module Profile | `Employee Self Service Profile` |
| Data scope | Own records only + own company |

#### Roles
- Employee
- Projects User

#### Allowed modules (unblocked)
- Setup (for Home workspace)
- Core (for desk functionality)
- Frappe (framework)
- ERPNext (base)
- HR
- Frappe HR (HRMS app module)
- Payroll
- Projects

#### Workspace visibility

| Workspace | Visible | Notes |
|---|---|---|
| Home | ✅ | |
| Leaves | ✅ | Apply for leave, check balance |
| Expense Claims | ✅ | Submit own expenses |
| Payroll | ✅ | View own salary slips only |
| Projects | ✅ | Tasks + timesheets assigned to them |
| HR | ❌ | Hidden via role restriction (requires HR Manager) |
| Recruitment | ❌ | Hidden via role restriction |
| Employee Lifecycle | ❌ | Hidden via role restriction |
| Performance | ❌ | Hidden via role restriction |
| Shift & Attendance | ❌ | Hidden via role restriction |
| Salary Payout | ❌ | Hidden via role restriction |
| Tax & Benefits | ❌ | Hidden via role restriction |
| Accounting | ❌ | |
| CRM | ❌ | |
| *(all others)* | ❌ | |

#### Can do
- Apply for leave
- Submit expense claims with receipts
- View and print own salary slips (PDF download)
- Log timesheets on assigned projects/tasks
- View assigned tasks
- Update own profile information

#### Cannot do
- See other employees' data (salary, leave, expenses)
- Approve anything (leave, expenses)
- Access HR management pages (recruitment, lifecycle, performance)
- Run payroll
- Change any system settings
- Create new employees or users

---

## Summary: Workspace visibility matrix

### SkyEngPro internal staff

| Workspace | 1A Admin | 1B Finance | 1C PM | 1D Support | 1E Employee |
|---|---|---|---|---|---|
| Home | ✅ | ✅ | ✅ | ✅ | ✅ |
| Accounting | ✅ | ✅ | ❌ | ❌ | ❌ |
| Payables | ✅ | ✅ | ❌ | ❌ | ❌ |
| Receivables | ✅ | ✅ | ❌ | ❌ | ❌ |
| Financial Reports | ✅ | ✅ | ❌ | ❌ | ❌ |
| Buying | ✅ | ✅ | ❌ | ❌ | ❌ |
| Selling | ✅ | ✅ | ❌ | ❌ | ❌ |
| HR | ✅ | ✅ | ✅ | ❌ | ❌ |
| Leaves | ✅ | ✅ | ✅ | ✅ | ✅ |
| Expense Claims | ✅ | ✅ | ❌ | ❌ | ✅ |
| Recruitment | ✅ | ❌ | ❌ | ❌ | ❌ |
| Employee Lifecycle | ✅ | ❌ | ❌ | ❌ | ❌ |
| Performance | ✅ | ❌ | ❌ | ❌ | ❌ |
| Shift & Attendance | ✅ | ❌ | ❌ | ❌ | ❌ |
| Payroll | ✅ | ✅ | ❌ | ❌ | ✅ |
| Salary Payout | ✅ | ✅ | ❌ | ❌ | ❌ |
| Tax & Benefits | ✅ | ✅ | ❌ | ❌ | ❌ |
| Projects | ✅ | ✅ | ✅ | ✅ | ✅ |
| CRM | ✅ | ❌ | ❌ | ❌ | ❌ |
| Support | ✅ | ❌ | ❌ | ✅ | ❌ |
| Stock | ✅ | ❌ | ❌ | ❌ | ❌ |
| Users | ✅ | ❌ | ❌ | ❌ | ❌ |
| ERPNext Settings | ✅ | ❌ | ❌ | ❌ | ❌ |
| Build | ✅ | ❌ | ❌ | ❌ | ❌ |
| Tools | ✅ | ❌ | ❌ | ❌ | ❌ |
| Integrations | ✅ | ❌ | ❌ | ❌ | ❌ |

### Independent company users (ALI Capital / MC Capital)

| Workspace | 2 Admin | 2-F Finance | 2-E Employee |
|---|---|---|---|
| Home | ✅ | ✅ | ✅ |
| Accounting | ✅ | ✅ | ❌ |
| Payables | ✅ | ✅ | ❌ |
| Receivables | ✅ | ✅ | ❌ |
| Financial Reports | ✅ | ✅ | ❌ |
| Buying | ✅ | ✅ | ❌ |
| Selling | ✅ | ✅ | ❌ |
| HR | ✅ | ❌ | ❌ |
| Leaves | ✅ | ❌ | ✅ |
| Expense Claims | ✅ | ✅ | ✅ |
| Recruitment | ✅ | ❌ | ❌ |
| Employee Lifecycle | ✅ | ❌ | ❌ |
| Performance | ✅ | ❌ | ❌ |
| Shift & Attendance | ✅ | ❌ | ❌ |
| Payroll | ✅ | ❌ | ✅ |
| Salary Payout | ✅ | ❌ | ❌ |
| Tax & Benefits | ✅ | ❌ | ❌ |
| Projects | ✅ | ❌ | ✅ |
| CRM | ✅ | ❌ | ❌ |
| Support | ✅ | ❌ | ❌ |
| Stock | ✅ | ❌ | ❌ |
| Users | ❌ | ❌ | ❌ |
| ERPNext Settings | ❌ | ❌ | ❌ |
| Build | ❌ | ❌ | ❌ |

### EoR partner users (adorsys under SkyEngPro)

| Workspace | 3A HR Manager | 3B Employee |
|---|---|---|
| Home | ✅ | ✅ |
| HR | ✅ | ❌ |
| Leaves | ✅ | ✅ |
| Expense Claims | ✅ | ✅ |
| Recruitment | ✅ | ❌ |
| Employee Lifecycle | ✅ | ❌ |
| Performance | ✅ | ❌ |
| Shift & Attendance | ✅ | ❌ |
| Payroll | ✅ | ✅ (own slips) |
| Salary Payout | ✅ | ❌ |
| Tax & Benefits | ✅ | ❌ |
| Projects | ✅ | ✅ |
| CRM | ✅ (shared leads) | ✅ (assigned leads) |
| Support | ❌ | ✅ (own tickets) |
| Accounting | ❌ | ❌ |
| *(all others)* | ❌ | ❌ |

---

## Workspace role restrictions

These workspaces are restricted to specific roles. Users without the role
don't see them in the sidebar, even if the module is unblocked.

| Workspace | Restricted to role | Who sees it |
|---|---|---|
| ERPNext Settings | System Manager | Admin only |
| Build | System Manager | Admin only |
| Users | System Manager | Admin only |
| Integrations | System Manager | Admin only |
| ERPNext Integrations | System Manager | Admin only |
| Welcome Workspace | System Manager | Admin only |
| Recruitment | HR Manager | Admin + Partner HR Manager |
| Employee Lifecycle | HR Manager | Admin + Partner HR Manager |
| Performance | HR Manager | Admin + Partner HR Manager |
| Shift & Attendance | HR Manager | Admin + Partner HR Manager |
| Salary Payout | HR Manager, Accounts Manager | Admin + Finance + Partner HR |
| Tax & Benefits | HR Manager, Accounts Manager | Admin + Finance + Partner HR |
| HR | HR Manager, HR User | Admin + Finance + PM + Partner HR |
| Support | Support Team | Admin + Tech Support |
| Payables | Accounts User | Admin + Finance |
| Receivables | Accounts User | Admin + Finance |
| Financial Reports | Accounts User | Admin + Finance |

---

## Data isolation

### SkyEngPro internal staff (Level 1)
- **No Company restriction** — they see all companies
- Individual data isolation for Employee self-service features
  (own payslips, own leave, etc.)

### Partner users (Level 2)
Data isolation is enforced via **User Permission** on the `Company` field:

```
User Permission:
  user: <partner user email>
  allow: Company
  for_value: <partner company name>
  apply_to_all_doctypes: Yes
```

This means:
- Every database query for that user is automatically filtered by Company
- They literally cannot access other companies' data, even via URL manipulation
- Works across ALL doctypes (Employee, Salary Slip, Leave Application, etc.)

### Employee-level isolation (both Level 1E and 2B)
Employees see only their OWN records because the `Employee` role has
`if_owner` permission on self-service doctypes:
- Leave Application: can only see/create where `employee = self`
- Expense Claim: can only see/create where `employee = self`
- Salary Slip: can only view where `employee = self`
- Timesheet: can only see/create where `employee = self`

---

## How to add a new partner company

1. **Create the Company** in ERPNext (as child of SkyEngPro)
2. **Create the HR Manager user** with:
   - Module Profile: `Partner HR Manager`
   - Roles: HR Manager, HR User, Leave Approver, Expense Approver, Employee, Projects User
   - User Permission: Company = `<new company>`
3. **Create Employee users** with:
   - Module Profile: `Employee Self Service Profile`
   - Roles: Employee, Projects User
   - User Permission: Company = `<new company>`
4. **Create Employee records** linked to the new Company and User

## How to add a new SkyEngPro internal staff member

1. **Create the User** with the appropriate Module Profile:
   - Finance → `SkyEngPro Finance`
   - Project Manager → `SkyEngPro Project Manager`
   - Tech Support → `SkyEngPro Tech Support`
   - Employee only → `Employee Self Service Profile`
2. **Assign roles** as listed above for that level
3. **No User Permission needed** — internal staff see all companies
4. **Create Employee record** linked to SkyEngPro company

---

## Summary: All profiles

| # | Profile | Company scope | Data scope | Key modules |
|---|---|---|---|---|
| **1A** | Platform Admin | ALL | ALL | Everything |
| **1B** | SkyEngPro Finance | SkyEngPro + EoR partners | ALL in scope | Accounting, HR, Payroll, Buying, Selling |
| **1C** | SkyEngPro PM | SkyEngPro + EoR partners | ALL in scope | Projects, HR |
| **1D** | SkyEngPro Tech Support | ALL (for tickets) | ALL in scope | Support, Projects |
| **1E** | SkyEngPro Employee | SkyEngPro only | Own records | Self-service |
| **2** | Company Admin (ALI/MC) | Own company only | ALL in company | Full business |
| **2-F** | Company Finance (ALI/MC) | Own company only | Financial data | Accounting, Buying, Selling |
| **2-E** | Company Employee (ALI/MC) | Own company only | Own records | Self-service |
| **3A** | Partner HR Manager (adorsys) | Own company only | ALL in company | HR, Payroll, CRM (shared), Projects |
| **3B** | Partner Employee (adorsys) | Own company only | Own records | Self-service, CRM (assigned), Support (own) |

---

## Changelog

| Date | Change | Author |
|---|---|---|
| 2026-04-11 | Initial design | YSI + Claude |
| 2026-04-11 | Added Level 1 sub-groups: Finance, PM, Tech Support, Employee | YSI + Claude |
| 2026-04-11 | Added Level 2: independent company roles (ALI/MC Capital) | YSI + Claude |
| 2026-04-11 | Renumbered: Level 2 = independent, Level 3 = EoR partner | YSI + Claude |
| | | |
