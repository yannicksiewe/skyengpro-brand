"""
SkyEngPro Platform — Role & Access Configuration

This file defines ALL profiles, roles, module access, and workspace visibility.
Edit this file to adjust access before running setup.

Structure:
- PROFILES: dict of profile_name → {roles, allowed_modules, workspace_overrides}
- WORKSPACE_RESTRICTIONS: workspace_name → [roles that can see it]
- DESK_ROLES: roles that need Page doctype read permission
"""

# ─────────────────────────────────────────────────────────────
# Base modules that ALL profiles need (framework + desk basics)
# ─────────────────────────────────────────────────────────────
BASE_MODULES = ["Setup", "Core", "Frappe", "ERPNext"]

# ─────────────────────────────────────────────────────────────
# Profile definitions
# ─────────────────────────────────────────────────────────────
PROFILES = {
    # ── Level 1: SkyEngPro Internal Staff ──

    # 1A: Platform Admin — no module profile (sees everything)
    # Not defined here because admins have no restrictions.

    "SkyEngPro Finance": {
        "description": "Internal finance team — accounting, payroll, billing across all companies",
        "roles": [
            "Accounts Manager",
            "Accounts User",
            "HR User",
            "Expense Approver",
            "Employee",
            "Projects User",
            "Sales User",
            "Purchase User",
        ],
        "allowed_modules": BASE_MODULES + [
            "Accounts",
            "HR",
            "Frappe HR",
            "Payroll",
            "Buying",
            "Selling",
            "Projects",
        ],
        "company_scope": "all_eor",  # sees SkyEngPro + EoR partners
    },

    "SkyEngPro Project Manager": {
        "description": "Project management — projects, timesheets, resource planning",
        "roles": [
            "Projects Manager",
            "Projects User",
            "HR User",
            "Employee",
        ],
        "allowed_modules": BASE_MODULES + [
            "Projects",
            "HR",
            "Frappe HR",
        ],
        "company_scope": "all_eor",
    },

    "SkyEngPro Tech Support": {
        "description": "Technical support — tickets, SLA, maintenance",
        "roles": [
            "Support Team",
            "Projects User",
            "Employee",
        ],
        "allowed_modules": BASE_MODULES + [
            "Support",
            "Projects",
            "HR",
            "Frappe HR",
        ],
        "company_scope": "all",  # handles tickets from any company
    },

    "SkyEngPro Employee": {
        "description": "Internal SkyEngPro staff — self-service only",
        "roles": [
            "Employee",
            "Projects User",
        ],
        # HR / Frappe HR / Payroll are intentionally NOT in allowed_modules:
        # the Frappe HR app card disappears from /desk and the HR / Payroll
        # workspace sidebars are hidden. Doctype access (Leave Application,
        # Salary Slip, Expense Claim) still works — Block Module gates
        # workspaces, not DocPerm. The Self Service workspace surfaces
        # those three actions explicitly.
        "allowed_modules": BASE_MODULES + [
            "Projects",
        ],
        "company_scope": "own",
    },

    # ── Level 2: Independent Company (ALI Capital / MC Capital) ──

    "Company Admin": {
        "description": "Full business admin for an independent company",
        "roles": [
            "HR Manager",
            "HR User",
            "Accounts Manager",
            "Accounts User",
            "Sales Manager",
            "Sales User",
            "Purchase Manager",
            "Purchase User",
            "Projects Manager",
            "Projects User",
            "Leave Approver",
            "Expense Approver",
            "Stock Manager",
            "Stock User",
            "Support Team",
            "Employee",
        ],
        "allowed_modules": BASE_MODULES + [
            "HR",
            "Frappe HR",
            "Payroll",
            "Accounts",
            "Selling",
            "Buying",
            "Stock",
            "CRM",
            "Projects",
            "Support",
        ],
        "company_scope": "own",
    },

    "Company Finance": {
        "description": "Finance staff for independent company",
        "roles": [
            "Accounts Manager",
            "Accounts User",
            "Expense Approver",
            "Sales User",
            "Purchase User",
            "Employee",
        ],
        "allowed_modules": BASE_MODULES + [
            "Accounts",
            "Selling",
            "Buying",
            "HR",
            "Frappe HR",
        ],
        "company_scope": "own",
    },

    # ── Level 3: EoR Partner (adorsys under SkyEngPro) ──

    "Partner HR Manager": {
        "description": "Partner company HR manager — manages their employees",
        "roles": [
            "HR Manager",
            "HR User",
            "Leave Approver",
            "Expense Approver",
            "Employee",
            "Projects User",
            "Sales User",  # for shared CRM leads
        ],
        "allowed_modules": BASE_MODULES + [
            "HR",
            "Frappe HR",
            "Payroll",
            "Projects",
            "CRM",
            "Selling",  # for shared CRM
        ],
        "company_scope": "own",
    },

    "Partner Employee": {
        "description": "EoR partner employee — self-service + shared CRM + support tickets",
        "roles": [
            "Employee",
            "Projects User",
        ],
        # HR / Frappe HR / Payroll deliberately blocked — same rationale as
        # SkyEngPro Employee. Self Service workspace covers Leave / Salary
        # Slip / Expense Claim shortcuts.
        "allowed_modules": BASE_MODULES + [
            "Projects",
            "Support",  # raise support tickets
        ],
        "company_scope": "own",
    },

    # ── Shared: Employee Self Service (reused across levels) ──

    "Employee Self Service Profile": {
        "description": "Basic employee self-service (used by 1E, 2-E, 3B)",
        "roles": [
            "Employee",
            "Projects User",
        ],
        # HR / Frappe HR / Payroll deliberately blocked — Self Service
        # workspace gives the user Leave / Salary Slip / Expense Claim
        # without exposing the rest of the HR app surface.
        "allowed_modules": BASE_MODULES + [
            "Projects",
        ],
        "company_scope": "own",
    },
}


# ─────────────────────────────────────────────────────────────
# Workspace role restrictions
# Only users with at least one of these roles see the workspace.
# If empty list → visible to all (no restriction).
# ─────────────────────────────────────────────────────────────
WORKSPACE_RESTRICTIONS = {
    # Admin-only workspaces
    "ERPNext Settings":  ["System Manager"],
    "Build":             ["System Manager"],
    "Users":             ["System Manager"],
    "Integrations":      ["System Manager"],
    "ERPNext Integrations": ["System Manager"],
    "Welcome Workspace": ["System Manager"],
    "Settings":          ["System Manager"],
    "Customization":     ["System Manager"],
    "Tools":             ["System Manager"],
    "Automation":        ["System Manager"],

    # ── Accounting/Finance — fully hidden from non-Accounts users ──
    # User explicitly asked: "completely remove 'Accounting' from user".
    # The Accounting workspace + Payments + Accounts Setup all live here.
    "Accounting":        ["Accounts Manager", "Accounts User"],
    "Accounts":          ["Accounts Manager", "Accounts User"],
    "Payments":          ["Accounts Manager", "Accounts User"],
    "Accounts Setup":    ["Accounts Manager"],
    "Salary Payout":     ["HR Manager", "Accounts Manager"],
    "Tax & Benefits":    ["HR Manager", "Accounts Manager"],
    "Payables":          ["Accounts User", "Accounts Manager"],
    "Receivables":       ["Accounts User", "Accounts Manager"],
    "Financial Reports": ["Accounts User", "Accounts Manager"],

    # ── Buying & Selling — hidden from regular employees ──
    "Buying":            ["Purchase Manager", "Purchase User"],
    "Selling":           ["Sales Manager", "Sales User"],
    "CRM":               ["Sales Manager", "Sales User"],

    # ── Stock & Manufacturing — hidden from regular employees ──
    "Stock":             ["Stock Manager", "Stock User"],
    "Manufacturing":     ["Manufacturing Manager", "Manufacturing User"],
    "Assets":            ["Accounts Manager", "Stock Manager"],
    "Quality":           ["Stock Manager", "Manufacturing Manager"],
    "Subcontracting":    ["Manufacturing User", "Manufacturing Manager"],
    "Maintenance":       ["Stock Manager", "Manufacturing Manager"],

    # ── Vertical apps — hidden from default org ──
    "Healthcare":        ["Healthcare Administrator"],
    "Education":         ["Academics User"],
    "Non Profit":        ["NPO Admin"],
    "Hospitality":       ["Restaurant Manager"],
    "Agriculture":       ["Agriculture User", "Agriculture Manager"],
    "Loan":              ["Loan Manager"],

    # ── HR — split: regular employees see HR shell, sub-workspaces gated ──
    # HR workspace itself stays accessible to Employee role so the cards
    # for Expenses / Leaves / Payroll are reachable. The sub-workspaces
    # listed below are HR-Manager-only.
    "HR":                ["HR Manager", "HR User", "Employee"],
    "Recruitment":       ["HR Manager"],
    "Employee Lifecycle": ["HR Manager"],
    "Performance":       ["HR Manager"],
    "Shift & Attendance": ["HR Manager"],
    "HR Settings":       ["HR Manager"],

    # Payroll — visible to employees so they can read their own payslip.
    # The doctype-level "Employee Self Service" role + the Salary Slip
    # User Permission (created in install.py) restrict to own records.
    "Payroll":           ["HR Manager", "HR User", "Employee"],

    # ── Misc ──
    "Support":           ["Support Team", "System Manager"],
    "Helpdesk":          ["Support Team", "Agent"],
    "Frappe CRM":        ["Sales Manager", "Sales User"],
    "HR Setup":          ["HR Manager"],
    "Tenure":            ["HR Manager"],
    "Website":           ["System Manager", "Website Manager"],
}


# ─────────────────────────────────────────────────────────────
# Custom roles created by skyengpro_brand
#
# These are "soft-assignable" roles a Manager grants on demand to
# selectively unlock tabs/sections that Wave-2 permlevel gates have
# locked. Created in setup_roles.ensure_custom_roles().
# ─────────────────────────────────────────────────────────────
CUSTOM_ROLES = [
    {
        "role_name": "Project Costing Viewer",
        "desk_access": 1,
        "description": (
            "Grants visibility on the Project doctype's Costing tab "
            "(total_costing_amount, total_purchase_cost, gross_margin, "
            "etc.). Assign per-user — not granted by default."
        ),
    },
    {
        "role_name": "Project More Info Viewer",
        "desk_access": 1,
        "description": (
            "Grants visibility on the Project doctype's More Info "
            "section (estimated_costing, actual + planned amounts, "
            "internal notes). Assign per-user — not granted by default."
        ),
    },
]


# ─────────────────────────────────────────────────────────────
# Default Module Profile auto-attached to new + existing users
# without a profile (skips Administrator + System Managers).
# Picks "SkyEngPro Employee" because it matches the canonical
# regular-employee persona (Expenses / Leaves / Payslip / Projects).
# ─────────────────────────────────────────────────────────────
DEFAULT_MODULE_PROFILE = "SkyEngPro Employee"

# Roles to auto-attach to a brand-new user along with the default
# Module Profile. "Employee Self Service" is the canonical Frappe role
# that grants owner-only Leave/Expense/Salary Slip access — without
# this the user can't see their own payslip even with Module Profile
# saying "Payroll" is allowed.
DEFAULT_USER_ROLES = ["Employee", "Employee Self Service"]


# ─────────────────────────────────────────────────────────────
# Employee Self Service read-perm grants
#
# The Expense Claim and Employee Advance forms link to Account /
# Currency / Mode of Payment / Cost Center records during their
# autocomplete. Frappe's Account/Cost Center are scoped to
# Accounts module which the Module Profile blocks for regular
# employees — so the autocomplete fails with "Insufficient
# Permission for Account/Currency/...". Granting read on ESS at
# permlevel 0 is the canonical answer and matches what stock
# Frappe ships before the per-tenant lockdown rewrites the
# Custom DocPerm rows.
# ─────────────────────────────────────────────────────────────
ESS_READ_DOCTYPES = [
    "Account",
    "Currency",
    "Mode of Payment",
    "Cost Center",
]


# ─────────────────────────────────────────────────────────────
# Wave 2: field-level permlevel gates
#
# Each entry hides a doctype's tab/section by raising the `permlevel`
# of every field in it. Standard DocPerm rules grant non-admin roles
# read at permlevel 0 only — fields at permlevel >0 silently disappear
# from the form, list, and REST API. An assignable role (with read at
# the elevated permlevel via Custom DocPerm) becomes the unlock key.
#
# CRITICAL: mandatory fields (reqd=1) are excluded from gating —
# raising permlevel on a mandatory field breaks save for everyone
# without that level. The architect's pre-flight: every field listed
# below must be reqd=0 in its doctype JSON.
#
# Schema: {role_name: {permlevel: [list of fieldnames]}}
# ─────────────────────────────────────────────────────────────

# Project fields → gated by Project Costing Viewer (Costing tab) or
# Project More Info Viewer (Notes/Progress tab). `company` (reqd=1)
# stays at permlevel 0 — leave it visible.
PROJECT_FIELD_PERMLEVELS = {
    "Project Costing Viewer": {
        2: [
            # Section: Costing and Billing
            "project_details",
            "estimated_costing",
            "total_costing_amount",
            "total_purchase_cost",
            "column_break_28",
            "total_sales_amount",
            "total_billable_amount",
            "total_billed_amount",
            "total_consumed_material_cost",
            "cost_center",
            # Section: Margin
            "margin",
            "gross_margin",
            "column_break_37",
            "per_gross_margin",
        ],
    },
    "Project More Info Viewer": {
        3: [
            # Section: Notes
            "section_break0",
            "notes",
            # Progress-collection fields (post-margin)
            "collect_progress",
            "holiday_list",
            "frequency",
            "from_time",
            "to_time",
            "first_email",
            "second_email",
            "daily_time_to_send",
            "day_to_send",
            "weekly_time_to_send",
            "column_break_45",
            "message",
            # naming_series is reqd=1 — kept at permlevel 0
            "subject",
        ],
    },
}

# Company fields → Accounts/Stock/Buying-Selling tabs. Mandatory
# fields kept at permlevel 0: company_name, abbr, default_currency,
# country.
COMPANY_FIELD_PERMLEVELS = {
    "Accounts User": {
        4: [
            # Default Accounts section
            "default_settings",
            "default_bank_account",
            "default_cash_account",
            "default_receivable_account",
            "round_off_account",
            "round_off_cost_center",
            "write_off_account",
            "exchange_gain_loss_account",
            "unrealized_exchange_gain_loss_account",
            "column_break0",
            "allow_account_creation_against_child_company",
            "default_payable_account",
            "default_expense_account",
            "default_income_account",
            "default_deferred_revenue_account",
            "default_deferred_expense_account",
            "cost_center",
            "credit_limit",
            "payment_terms",
            # Stock Settings (financial side)
            "auto_accounting_for_stock_settings",
            "enable_perpetual_inventory",
            "default_inventory_account",
            "stock_adjustment_account",
            "column_break_32",
            "stock_received_but_not_billed",
            "accumulated_depreciation_account",
            "depreciation_expense_account",
            "series_for_depreciation_entry",
            "column_break_40",
            "disposal_account",
            "depreciation_cost_center",
            "capital_work_in_progress_account",
            "asset_received_but_not_billed",
            # Budget Detail
            "budget_detail",
            "exception_budget_approver_role",
            # Chart of Accounts
            "section_break_28",
            "enable_provisional_accounting_for_non_stock_items",
            "default_provisional_account",
            # Advance Payments
            "advance_payments_section",
            "default_advance_received_account",
            "default_advance_paid_account",
            "column_break_fwcf",
            "book_advance_payments_in_separate_party_account",
            # Exchange Rate
            "exchange_rate_revaluation_settings_section",
            "auto_exchange_rate_revaluation",
            "auto_err_frequency",
            "submit_err_jv",
            # Other accounting-flavoured fields
            "default_selling_terms",
            "default_buying_terms",
            "default_in_transit_warehouse",
            "unrealized_profit_loss_account",
            "default_discount_account",
        ],
    },
    "Sales User": {
        5: [
            # Buying & Selling Settings section
            "sales_settings",
            "sales_monthly_history",
            "transactions_annual_history",
            "monthly_sales_target",
            "column_break_goals",
            "total_monthly_sales",
            # Tab Break — hides the whole Buying and Selling tab header.
            # Without gating the Tab Break itself, the tab still renders
            # (empty) when its child sections are hidden by permlevel.
            "buying_and_selling_tab",
        ],
    },
}

# Wave 2.5 additions — gate the Tab Break fields themselves so the tab
# headers disappear, not just the inner sections. Council finding: in
# v16, hiding inner fields leaves an empty tab header visible until
# the Tab Break field gets permlevel >0 too.
COMPANY_FIELD_PERMLEVELS["Accounts User"][4].extend([
    "accounts_tab",
    "accounts_closing_tab",
    "stock_tab",
    "dashboard_tab",
])

# HR & Payroll tab on Company is added by HRMS as Custom Fields, not
# standard DocFields. Gate at permlevel 6 (same level we use for the
# Employee Salary tab) so HR User unlocks BOTH tabs with the one role.
# Fields involved (all Custom Fields):
#   - hr_and_payroll_tab           (Tab Break)
#   - hr_settings_section          (Section Break inside the tab)
#   - default_payroll_payable_account  (Link)
COMPANY_FIELD_PERMLEVELS["HR User"] = {
    6: [
        "hr_and_payroll_tab",
        "hr_settings_section",
        "default_payroll_payable_account",
    ],
}


# Employee fields — hide the Salary tab from Employee Self Service.
# Tab Break `salary_information` gates the whole tab header. The
# inner field gates (ctc, salary_currency, etc.) are defence-in-depth
# in case a custom view bypasses the Tab Break check.
EMPLOYEE_FIELD_PERMLEVELS = {
    "HR User": {
        6: [
            "salary_information",        # Tab Break — hides "Salary" tab
            "ctc",
            "salary_currency",
            "salary_mode",
            "bank_details_section",      # Section Break inside Salary tab
            "bank_name",
            "bank_ac_no",
            "iban",
        ],
    },
}


# ─────────────────────────────────────────────────────────────
# Wave 2.5: Custom DocPerm write-strip
#
# Each (doctype, role) tuple gets a Custom DocPerm row that mirrors
# the role's read/if_owner flags but forces write=0, create=0,
# delete=0. Used to plug write leaks where a role currently has
# write=1 it shouldn't (e.g. Employee Self Service writing on
# Employee, which lets a user edit her own salary).
#
# Implementation pattern (from architect's brief): NEVER delete the
# standard DocPerm row — bench migrate recreates it. Frappe resolves
# perms by replacing standard with Custom DocPerm whenever ANY Custom
# DocPerm exists for (parent, role). We mirror the standard row's
# read flags and only flip write/create/delete to 0.
# ─────────────────────────────────────────────────────────────
DOCPERM_WRITE_LOCKDOWN = [
    # Plug the salary-self-edit leak — ESS users can read their own
    # Employee record (if_owner already 0 in the existing Custom row,
    # but User Permission still scopes them to themselves) but cannot
    # edit ANY field. Salary fields are also gated at permlevel 6.
    ("Employee", "Employee Self Service"),

    # Lock Company write for every non-finance / non-admin role that
    # might ship with default write. Keep write only on Accounts
    # Manager and System Manager.
    ("Company",  "Employee"),
    ("Company",  "Employee Self Service"),
    ("Company",  "HR User"),
    ("Company",  "HR Manager"),
    ("Company",  "Sales User"),
    ("Company",  "Sales Manager"),
    ("Company",  "Purchase User"),
    ("Company",  "Purchase Manager"),
    ("Company",  "Stock User"),
    ("Company",  "Stock Manager"),
    ("Company",  "Projects User"),
    ("Company",  "Projects Manager"),
    ("Company",  "Accounts User"),

    # Address + Contact: stock Frappe grants the implicit "All" role
    # write+create on these doctypes — every user can create a new
    # Address linked to any Company. Strip "All" plus all HR/Projects
    # roles. Sales/Purchase/Maintenance/Accounts retain their own
    # write rows from standard DocPerm, which is correct (they need
    # to add Customer/Supplier/Vendor addresses).
    ("Address",  "All"),
    ("Address",  "Employee"),
    ("Address",  "Employee Self Service"),
    ("Address",  "HR User"),
    ("Address",  "HR Manager"),
    ("Address",  "Projects User"),
    ("Address",  "Projects Manager"),

    ("Contact",  "All"),
    ("Contact",  "Employee"),
    ("Contact",  "Employee Self Service"),
    ("Contact",  "HR User"),
    ("Contact",  "HR Manager"),
    ("Contact",  "Projects User"),
    ("Contact",  "Projects Manager"),
]


# ─────────────────────────────────────────────────────────────
# Roles that need Page doctype read permission (for desk access)
# Without this, users get "Not permitted for document Page" error.
# ─────────────────────────────────────────────────────────────
DESK_ACCESS_ROLES = [
    "HR Manager",
    "HR User",
    "Employee",
    "Projects User",
    "Projects Manager",
    "Accounts User",
    "Accounts Manager",
    "Sales User",
    "Sales Manager",
    "Purchase User",
    "Purchase Manager",
    "Stock User",
    "Stock Manager",
    "Support Team",
    "Leave Approver",
    "Expense Approver",
]


# ─────────────────────────────────────────────────────────────
# Company templates
# ─────────────────────────────────────────────────────────────
COMPANY_DEFAULTS = {
    "cameroon": {
        "country": "Cameroon",
        "currency": "XAF",
        "chart_of_accounts": "Syscohada - Plan Comptable",
        "tax_rate": 19.25,
    },
    "ireland": {
        "country": "Ireland",
        "currency": "EUR",
        "chart_of_accounts": None,  # use ERPNext default for Ireland
        "tax_rate": 23.0,
    },
    "germany": {
        "country": "Germany",
        "currency": "EUR",
        "chart_of_accounts": "SKR04 mit Kontonummern",
        "tax_rate": 19.0,
    },
    "france": {
        "country": "France",
        "currency": "EUR",
        "chart_of_accounts": None,
        "tax_rate": 20.0,
    },
}
