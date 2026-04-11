# SkyEngPro Platform — Multi-Company Architecture

This document defines the company structure, data isolation, shared activities,
and inter-company relationships for the SkyEngPro ERPNext platform.

Edit this file before running the automated setup.

---

## Platform Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     ERPNEXT INSTANCE                            │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ ACCOUNT 1: SkyEngPro                                     │  │
│  │ Type: Full separate entity + EoR provider                │  │
│  │ Country: Cameroon | Currency: XAF                        │  │
│  │ Chart of Accounts: OHADA (SYSCOHADA)                     │  │
│  │                                                          │  │
│  │ Internal staff:                                          │  │
│  │   - Platform Admin                                       │  │
│  │   - Finance                                              │  │
│  │   - Project Manager                                      │  │
│  │   - Tech Support                                         │  │
│  │   - Employees (self-service)                             │  │
│  │                                                          │  │
│  │ EoR Partner:                                             │  │
│  │   ┌──────────────────────────────────────────────────┐   │  │
│  │   │ adorsys Ireland                                  │   │  │
│  │   │ Country: Ireland | Currency: EUR                 │   │  │
│  │   │ Chart of Accounts: Irish Standard                │   │  │
│  │   │                                                  │   │  │
│  │   │ Relationship: EoR (SkyEngPro manages HR+Payroll) │   │  │
│  │   │                                                  │   │  │
│  │   │ SHARED with SkyEngPro:                           │   │  │
│  │   │   - CRM (joint leads, shared opportunities)      │   │  │
│  │   │   - Support (employees raise support tickets)    │   │  │
│  │   │                                                  │   │  │
│  │   │ ISOLATED (adorsys only):                         │   │  │
│  │   │   - HR (employee records)                        │   │  │
│  │   │   - Payroll (salary, tax)                        │   │  │
│  │   │   - Accounting (own ledger)                      │   │  │
│  │   │                                                  │   │  │
│  │   │ Users:                                           │   │  │
│  │   │   - HR Manager (manages adorsys employees)       │   │  │
│  │   │   - Employees (self-service + CRM + support)     │   │  │
│  │   └──────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ ACCOUNT 2: ALI Capital                                    │  │
│  │ Type: Full separate entity (standalone business)          │  │
│  │ Country: Cameroon | Currency: XAF                         │  │
│  │ Chart of Accounts: OHADA (SYSCOHADA)                      │  │
│  │                                                           │  │
│  │ Completely independent:                                   │  │
│  │   - Own Accounting                                        │  │
│  │   - Own HR                                                │  │
│  │   - Own CRM                                               │  │
│  │   - Own Projects                                          │  │
│  │   - Own Selling / Buying                                  │  │
│  │                                                           │  │
│  │ NO data shared with SkyEngPro or MC Capital               │  │
│  │                                                           │  │
│  │ Users:                                                    │  │
│  │   - Admin (ALI Capital)                                   │  │
│  │   - Finance                                               │  │
│  │   - Employees                                             │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ ACCOUNT 3: MC Capital                                     │  │
│  │ Type: Full separate entity (standalone business)          │  │
│  │ Country: Cameroon | Currency: XAF                         │  │
│  │ Chart of Accounts: OHADA (SYSCOHADA)                      │  │
│  │                                                           │  │
│  │ Completely independent:                                   │  │
│  │   - Own Accounting                                        │  │
│  │   - Own HR                                                │  │
│  │   - Own CRM                                               │  │
│  │   - Own Projects                                          │  │
│  │   - Own Selling / Buying                                  │  │
│  │                                                           │  │
│  │ NO data shared with SkyEngPro or ALI Capital              │  │
│  │                                                           │  │
│  │ Users:                                                    │  │
│  │   - Admin (MC Capital)                                    │  │
│  │   - Finance                                               │  │
│  │   - Employees                                             │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  PLATFORM SUPER ADMIN (you)                                     │
│  Can see: ALL accounts, ALL companies, ALL data                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Company hierarchy in ERPNext

```
(no parent — top-level independent companies)

SkyEngPro Sarl ──────── is_group: Yes
└── adorsys Ireland ─── is_group: No (EoR partner, child of SkyEngPro)

ALI Capital ─────────── is_group: No (standalone, no parent)

MC Capital ──────────── is_group: No (standalone, no parent)
```

**Key design decision**: ALI Capital and MC Capital are NOT children of
SkyEngPro. They are fully independent top-level companies. SkyEngPro cannot
see their data through consolidated reports — only the Platform Super Admin
(you) can see all three by having no Company restriction.

---

## Data isolation matrix

| Data type | SkyEngPro staff | adorsys HR Mgr | adorsys Employee | ALI Capital users | MC Capital users |
|---|---|---|---|---|---|
| **SkyEngPro HR** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **SkyEngPro Accounting** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **SkyEngPro CRM** | ✅ | ✅ shared leads | ✅ assigned leads | ❌ | ❌ |
| **SkyEngPro Support** | ✅ | ❌ | ✅ raise tickets | ❌ | ❌ |
| **adorsys HR** | ✅ (as EoR) | ✅ | own only | ❌ | ❌ |
| **adorsys Payroll** | ✅ (processes it) | ✅ | own slips | ❌ | ❌ |
| **adorsys Accounting** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **ALI Capital (all)** | ❌ | ❌ | ❌ | ✅ | ❌ |
| **MC Capital (all)** | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Cross-account** | only Super Admin | ❌ | ❌ | ❌ | ❌ |

---

## Shared activities: SkyEngPro ↔ adorsys

### CRM (shared leads)

| What | How it works |
|---|---|
| Joint leads | Lead belongs to SkyEngPro, but adorsys employees assigned to it can view/edit |
| Implementation | User Permission: allow `Lead` where `assigned_to` includes the user, OR share specific Leads via Frappe's sharing feature |
| adorsys HR Manager | Can see all leads where any adorsys employee is assigned |
| adorsys Employee | Can see only leads they are personally assigned to |
| ALI / MC Capital | Cannot see any SkyEngPro or adorsys leads |

#### Roles needed for adorsys CRM access
- adorsys HR Manager: add role `Sales User` (read-only on Lead, Opportunity)
- adorsys Employee: add role `Sales User` (filtered to assigned leads only)
- Unblock modules: `CRM`, `Selling` for adorsys users
- Add User Permission: allow `Lead` where `_assign like %user_email%`

#### CRM workspace visibility

| User | CRM workspace | Frappe CRM workspace |
|---|---|---|
| SkyEngPro staff | ✅ | ✅ |
| adorsys HR Manager | ✅ (shared leads) | ❌ |
| adorsys Employee | ✅ (assigned leads) | ❌ |
| ALI / MC Capital | own CRM | ❌ |

### Support (adorsys employees raise tickets)

| What | How it works |
|---|---|
| Ticket creation | adorsys employees can create support tickets (Issue doctype) |
| Ticket visibility | Employee sees only their own tickets |
| Ticket assignment | SkyEngPro Tech Support handles all tickets |
| Implementation | adorsys employees get `Customer` role for portal, OR `Support Team` role with User Permission filter |

#### Roles needed for adorsys Support access
- adorsys Employee: add role `Customer` (for Issue creation via portal) OR add custom role `Support User` with read/create on Issue
- Unblock module: `Support` for adorsys employees
- User Permission: Employee can only see Issues where `raised_by = self`

#### Support workspace visibility

| User | Support workspace |
|---|---|
| SkyEngPro Tech Support | ✅ (all tickets) |
| adorsys HR Manager | ❌ (not their job) |
| adorsys Employee | ✅ (own tickets only) |
| ALI / MC Capital | own support (if enabled) |

---

## Account-specific settings

### Account 1: SkyEngPro Sarl

| Setting | Value |
|---|---|
| Company name | SkyEngPro Sarl |
| Abbreviation | SEP |
| Country | Cameroon |
| Currency | XAF |
| Chart of Accounts | OHADA (SYSCOHADA) |
| Fiscal Year | January – December |
| Tax | TVA Cameroon (19.25%) |
| Holiday List | Cameroon Public Holidays |
| Letter Head | SkyEngPro branded |
| Employee naming | SEP-EMP-.##### |
| is_group | Yes (has adorsys as child) |

#### EoR Partner: adorsys Ireland

| Setting | Value |
|---|---|
| Company name | adorsys Ireland |
| Abbreviation | ADO |
| Country | Ireland |
| Currency | EUR |
| Chart of Accounts | Irish Standard |
| Fiscal Year | January – December |
| Tax | Irish VAT (23% / 13.5% / 9%) |
| Holiday List | Ireland Public Holidays |
| Letter Head | adorsys branded OR SkyEngPro EoR |
| Employee naming | ADO-EMP-.##### |
| Parent company | SkyEngPro Sarl |
| is_group | No |

### Account 2: ALI Capital

| Setting | Value |
|---|---|
| Company name | ALI Capital |
| Abbreviation | ALI |
| Country | Cameroon |
| Currency | XAF |
| Chart of Accounts | OHADA (SYSCOHADA) |
| Fiscal Year | January – December |
| Tax | TVA Cameroon (19.25%) |
| Holiday List | Cameroon Public Holidays |
| Letter Head | ALI Capital branded (separate branding) |
| Employee naming | ALI-EMP-.##### |
| Parent company | none (standalone) |
| is_group | No |

### Account 3: MC Capital

| Setting | Value |
|---|---|
| Company name | MC Capital |
| Abbreviation | MCC |
| Country | Cameroon |
| Currency | XAF |
| Chart of Accounts | OHADA (SYSCOHADA) |
| Fiscal Year | January – December |
| Tax | TVA Cameroon (19.25%) |
| Holiday List | Cameroon Public Holidays |
| Letter Head | MC Capital branded (separate branding) |
| Employee naming | MCC-EMP-.##### |
| Parent company | none (standalone) |
| is_group | No |

---

## Role design per account

### SkyEngPro roles (see ROLE_DESIGN.md for full details)

| Role | Sees | Data scope |
|---|---|---|
| 1A. Platform Admin | Everything | All accounts |
| 1B. Finance | Accounting, HR, Payroll, Buying, Selling | SkyEngPro + adorsys |
| 1C. Project Manager | Projects, HR | SkyEngPro + adorsys |
| 1D. Tech Support | Support, Projects | All (handles tickets from adorsys) |
| 1E. Employee | Self-service | Own records, SkyEngPro only |

### adorsys roles (EoR partner with shared CRM + Support)

| Role | Sees | Special |
|---|---|---|
| 2A. HR Manager | HR, Payroll, Projects, **CRM (shared)** | adorsys only |
| 2B. Employee | Self-service, **CRM (assigned)**, **Support (own tickets)** | Own records + assigned leads + own tickets |

### ALI Capital roles (fully independent)

| Role | Sees | Data scope |
|---|---|---|
| Admin | Everything for ALI Capital | ALI Capital only |
| Finance | Accounting, Buying, Selling | ALI Capital only |
| Employee | Self-service | Own records, ALI Capital only |

### MC Capital roles (fully independent)

| Role | Sees | Data scope |
|---|---|---|
| Admin | Everything for MC Capital | MC Capital only |
| Finance | Accounting, Buying, Selling | MC Capital only |
| Employee | Self-service | Own records, MC Capital only |

---

## User Permission design

### Platform Super Admin (you)
```
No User Permission — sees ALL companies, ALL data
```

### SkyEngPro internal staff (1B–1D)
```
User Permission:
  allow: Company
  for_value: SkyEngPro Sarl
  apply_to_all_doctypes: Yes

  (+ additional permission)
  allow: Company
  for_value: adorsys Ireland
  apply_to_all_doctypes: Yes
```
They need access to BOTH companies because they manage adorsys as EoR.

### SkyEngPro Employee (1E)
```
User Permission:
  allow: Company
  for_value: SkyEngPro Sarl
  apply_to_all_doctypes: Yes
```

### adorsys HR Manager
```
User Permission:
  allow: Company
  for_value: adorsys Ireland
  apply_to_all_doctypes: Yes
```

### adorsys Employee
```
User Permission:
  allow: Company
  for_value: adorsys Ireland
  apply_to_all_doctypes: Yes

Note: CRM leads visible via Frappe sharing or _assign field filter
Note: Support tickets visible via raised_by filter
```

### ALI Capital users
```
User Permission:
  allow: Company
  for_value: ALI Capital
  apply_to_all_doctypes: Yes
```

### MC Capital users
```
User Permission:
  allow: Company
  for_value: MC Capital
  apply_to_all_doctypes: Yes
```

---

## Inter-company transactions

### SkyEngPro → adorsys (EoR service billing)

```
SkyEngPro Sarl creates:
  Sales Invoice → adorsys Ireland
    Items: "EoR Service Fee - March 2026"
    Amount: employee count × monthly rate

ERPNext auto-creates (if enabled):
  Purchase Invoice → adorsys side
    Linked to SkyEngPro invoice
```

### No inter-company between ALI / MC / SkyEngPro

ALI Capital and MC Capital are fully independent. No shared transactions,
no consolidated reporting across accounts. Only the Platform Super Admin
can view them all.

---

## Shared activity implementation details

### CRM sharing: SkyEngPro ↔ adorsys

**Option A: Frappe Document Sharing (recommended)**
- SkyEngPro creates a Lead
- SkyEngPro shares the Lead with specific adorsys users
- adorsys users see it in their Lead list
- Granular: share per-document, can revoke anytime

**Option B: User Permission on Lead**
- Add User Permission: `Lead` where `company = SkyEngPro Sarl` for adorsys HR Manager
- Broader: they see ALL SkyEngPro leads (may be too much)

**Option C: Custom field + filter**
- Add custom field `partner_company` on Lead
- Set to "adorsys" for shared leads
- adorsys users have User Permission on Lead filtered by `partner_company`
- Most flexible, cleanest for EoR model

**Recommendation: Option C** — gives you explicit control over which leads
are shared with which partner.

### Support sharing: adorsys employees → SkyEngPro

**Implementation:**
1. adorsys employees get role: `Issue Creator` (custom, or use `Customer`)
2. They can create Issues (support tickets)
3. `raised_by` field auto-set to their email
4. They see only Issues where `raised_by = their email`
5. SkyEngPro Tech Support sees ALL Issues

---

## Onboarding checklist

### New independent account (like ALI Capital / MC Capital)

- [ ] Create Company (no parent, standalone)
- [ ] Configure: country, currency, chart of accounts, tax, holidays
- [ ] Create Letter Head with their branding
- [ ] Create Admin user with Module Profile: `Company Admin`
- [ ] Set User Permission: Company = `<new company>`
- [ ] Create Employee records
- [ ] **No access to SkyEngPro or any other account**

### New EoR partner under SkyEngPro (like adorsys)

- [ ] Create Company as child of SkyEngPro Sarl
- [ ] Configure: country, currency, chart of accounts, tax, holidays
- [ ] Create HR Manager user (Module Profile: `Partner HR Manager`)
- [ ] Set User Permission: Company = `<partner>`
- [ ] Create Employee users (Module Profile: `Employee Self Service Profile`)
- [ ] Set User Permission: Company = `<partner>`
- [ ] **If CRM shared:** add custom field `partner_company` on Leads, configure sharing
- [ ] **If Support shared:** add Issue Creator role to employees
- [ ] Configure Inter-Company Transaction Settings for billing
- [ ] SkyEngPro Finance gets User Permission for the new partner company

---

## Design decisions (resolved)

| # | Question | Answer |
|---|---|---|
| 1 | ALI / MC Capital country + currency | Cameroon, XAF |
| 2 | ALI / MC Capital admin | Separate people (own admin user per company) |
| 3 | CRM sharing between ALI / MC and SkyEngPro | No — ALI and MC have their own isolated CRM |
| 4 | ALI / MC need EoR partners? | No — standalone businesses |
| 5 | Branding | Separate branding per account (own logos + letter heads) |

## Branding per account

Each account gets its own:
- Letter Head (for invoices, payslips, contracts)
- Company logo
- Login page can show brand based on company (future: subdomain routing)

Implementation: each company's Letter Head is created with their own logo.
The main ERPNext navbar shows SkyEngPro branding (platform owner), but
printed documents use the company's own Letter Head.

| Account | Letter Head | Logo | Login page |
|---|---|---|---|
| SkyEngPro | SkyEngPro branded | SkyEngPro logo | SkyEngPro (default) |
| ALI Capital | ALI Capital branded | ALI Capital logo | SkyEngPro (shared login) |
| MC Capital | MC Capital branded | MC Capital logo | SkyEngPro (shared login) |

Note: all users log in via the same URL (`erp.homelab.local`). The navbar
always shows SkyEngPro (platform owner). But when they print an invoice or
payslip, it uses THEIR company's Letter Head with THEIR branding.

---

## Changelog

| Date | Change | Author |
|---|---|---|
| 2026-04-11 | Initial design: 3 accounts + EoR partner + shared CRM/Support | YSI + Claude |
| | | |
