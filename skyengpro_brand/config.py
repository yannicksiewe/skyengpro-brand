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
        "allowed_modules": BASE_MODULES + [
            "HR",
            "Frappe HR",
            "Payroll",
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
        "allowed_modules": BASE_MODULES + [
            "HR",
            "Frappe HR",
            "Payroll",
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
        "allowed_modules": BASE_MODULES + [
            "HR",
            "Frappe HR",
            "Payroll",
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
    "ERPNext Settings": ["System Manager"],
    "Build": ["System Manager"],
    "Users": ["System Manager"],
    "Integrations": ["System Manager"],
    "ERPNext Integrations": ["System Manager"],
    "Welcome Workspace": ["System Manager"],

    # HR Manager workspaces (admin + HR managers)
    "HR": ["HR Manager", "HR User"],
    "Recruitment": ["HR Manager"],
    "Employee Lifecycle": ["HR Manager"],
    "Performance": ["HR Manager"],
    "Shift & Attendance": ["HR Manager"],

    # Finance workspaces (admin + accounts roles)
    "Salary Payout": ["HR Manager", "Accounts Manager"],
    "Tax & Benefits": ["HR Manager", "Accounts Manager"],
    "Payables": ["Accounts User", "Accounts Manager"],
    "Receivables": ["Accounts User", "Accounts Manager"],
    "Financial Reports": ["Accounts User", "Accounts Manager"],

    # Support workspace
    "Support": ["Support Team", "System Manager"],
}


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
        "chart_of_accounts": "SYSCOHADA - Plan Comptable",
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
