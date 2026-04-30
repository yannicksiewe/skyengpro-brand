"""Per-tenant scope for shared master DocTypes.

This site runs five Companies on one Frappe install. Stock ERPNext leaves
the shared masters (Customer, Supplier, Item, Letter Head) globally visible
across all companies — every tenant's user can see, and sometimes edit,
every other tenant's records. This module wires Frappe's
`permission_query_conditions` + `has_permission` hooks for any doctype to
filter rows by the user's resolved company.

User → company resolution mirrors `theme._resolve_brand_slug` in priority
order so the same user gets the same tenant identity for branding and for
data scope:

  1. Employee.user_id → Employee.company  (HR primary linkage)
  2. User Permission allow=Company
  3. frappe.defaults.get_user_default("company")  (per-user, falls back to Global)
  4. None (admin / unscoped)

Bypass: Administrator, Guest, and any user with the System Manager role
see all rows — they need the unrestricted view to administer the site.

Behaviour for NULL company:
  - Customer / Supplier / Item: NULL is treated as "missing" and the row
    is hidden. before_insert auto-fills company from the user, so new rows
    are always tagged. Existing NULL rows must be backfilled at install
    time (see install.ensure_tenant_company_fields).
  - Letter Head: NULL is treated as "shared/global". A letterhead with no
    company is visible to every tenant — useful for fixtures like the
    default "Company Letterhead" shipped with ERPNext.

This split is encoded per-doctype in SCOPED_DOCTYPES below.
"""
from __future__ import annotations

import frappe


# (doctype, company_field_name, allow_null_as_global)
SCOPED_DOCTYPES = (
    ("Customer",    "company", False),
    ("Supplier",    "company", False),
    ("Item",        "company", False),
    ("Letter Head", "company", True),
)


# ─────────────────────────────────────────────────────────────
# User → Company resolver
# ─────────────────────────────────────────────────────────────

def get_user_company(user: str | None = None) -> str | None:
    """Return the Company name this user belongs to, or None for admin/guest.

    Mirrors theme._resolve_brand_slug — same priority order so branding and
    data scope agree. Returns None on the bypass path.

    Bypass paths:
      - `Administrator` (root user) and `Guest` (unauthenticated) are
        always bypassed.
      - Any user with the **System Manager** role is bypassed. System
        Manager has full doctype access in stock Frappe anyway, so
        scoping their list views adds friction without any security
        gain — they could just toggle off the User Permission and see
        everything regardless. The platform admin (a normal user with
        System Manager) typically needs cross-tenant visibility to
        manage all tenants from one account.

    Anyone else resolves to their tenant via Employee → User Permission
    → user/global default chain.
    """
    user = user or frappe.session.user
    if not user or user in ("Guest", "Administrator"):
        return None

    # System Manager bypass — platform admins need cross-tenant view.
    try:
        if "System Manager" in (frappe.get_roles(user) or []):
            return None
    except Exception:
        pass

    # 1) Employee linkage (most specific signal for HR-managed users)
    try:
        emp_company = frappe.db.get_value(
            "Employee",
            {"user_id": user, "status": "Active"},
            "company",
        )
        if emp_company:
            return emp_company
    except Exception:
        pass

    # 2) User Permission allow=Company
    try:
        rows = frappe.db.get_all(
            "User Permission",
            filters={"user": user, "allow": "Company"},
            fields=["for_value"],
            limit=1,
            ignore_permissions=True,
        )
        if rows and rows[0].for_value:
            return rows[0].for_value
    except Exception:
        pass

    # 3) Per-user / Global default. Note: get_user_default falls back to
    #    Global Defaults silently — this is intentionally LAST so the
    #    above more-specific lookups win.
    try:
        company = frappe.defaults.get_user_default("company")
        if company:
            return company
    except Exception:
        pass

    return None


# ─────────────────────────────────────────────────────────────
# Generic permission_query_conditions builder
# ─────────────────────────────────────────────────────────────

def _scope_query(doctype: str, field: str, allow_null_global: bool, user=None) -> str:
    """Return a SQL WHERE fragment that limits rows on `doctype` to those
    where the company `field` matches the user's company.

    `allow_null_global=True` lets rows with NULL company be visible to
    everyone (used for Letter Head's shared fixtures).
    """
    company = get_user_company(user)
    if not company:
        return ""  # Admin / bypass — no restriction.

    quoted = frappe.db.escape(company)
    table = "`tab" + doctype + "`"
    col = "`" + field + "`"

    if allow_null_global:
        return f"({table}.{col} = {quoted} OR {table}.{col} IS NULL OR {table}.{col} = '')"
    return f"({table}.{col} = {quoted})"


def _scope_has_perm(field: str, allow_null_global: bool, doc, user=None) -> bool:
    """has_permission hook — block direct desk-URL access to docs whose
    company doesn't match this user's tenant."""
    company = get_user_company(user)
    if not company:
        return True

    doc_company = doc.get(field) if hasattr(doc, "get") else getattr(doc, field, None)
    if not doc_company:
        # Untagged row. Visible to all only if globals are allowed.
        return allow_null_global
    return doc_company == company


# ─────────────────────────────────────────────────────────────
# Per-doctype handlers (one pair each — referenced by hooks.py)
#
# These thin shims exist because Frappe's hook signature is fixed at
# fn(user) / fn(doc, ptype, user) — there's no parameter for "which
# doctype are we filtering". Each shim binds its doctype + field at
# import time via closure-of-constants.
# ─────────────────────────────────────────────────────────────

def customer_query(user=None):
    return _scope_query("Customer", "company", False, user)

def customer_has_perm(doc, ptype="read", user=None):
    return _scope_has_perm("company", False, doc, user)


def supplier_query(user=None):
    return _scope_query("Supplier", "company", False, user)

def supplier_has_perm(doc, ptype="read", user=None):
    return _scope_has_perm("company", False, doc, user)


def item_query(user=None):
    return _scope_query("Item", "company", False, user)

def item_has_perm(doc, ptype="read", user=None):
    return _scope_has_perm("company", False, doc, user)


def letter_head_query(user=None):
    return _scope_query("Letter Head", "company", True, user)

def letter_head_has_perm(doc, ptype="read", user=None):
    return _scope_has_perm("company", True, doc, user)


# Company doctype is special: the document's primary key (`name`) IS the
# company name, so the scope field is `name` instead of `company`. Without
# this filter, every company-Link autocomplete (Payment Reconciliation,
# Sales Invoice, etc.) shows all 5 companies.
def company_query(user=None):
    return _scope_query("Company", "name", False, user)

def company_has_perm(doc, ptype="read", user=None):
    company = get_user_company(user)
    if not company:
        return True
    return doc.name == company if hasattr(doc, "name") else doc.get("name") == company


# ─────────────────────────────────────────────────────────────
# before_insert auto-tagger
#
# When a Customer / Supplier / Item is created without `company`, fill it
# from the current user. Without this, every new record would be NULL and
# (because we hide NULL for these doctypes) invisible immediately after
# save — confusing UX. Letter Head intentionally not covered: leaving its
# company empty is the documented way to mark a letterhead as shared.
# ─────────────────────────────────────────────────────────────

def auto_tag_company(doc, method=None):
    """doc_events handler — Customer/Supplier/Item before_insert."""
    if getattr(doc, "company", None):
        return
    company = get_user_company()
    if company:
        doc.company = company


# ─────────────────────────────────────────────────────────────
# Per-user Project scoping
#
# ERPNext leaves Projects globally visible inside a Company — every
# user with the Projects User role sees every project. We narrow to
# "user is on the project team": Project.users child row, or
# document owner. (ERPNext v16 dropped the legacy `project_manager`
# scalar field — the canonical way to mark a PM is to add them to
# Project.users; the role/manager distinction is informational.)
# The tenant scope (project.company = user_company) is preserved
# with explicit AND so the tenant guard cannot be associativity-
# dropped by the assignment OR-clause.
#
# Same scoping is mirrored on:
#   - Project User (child table — direct /api/resource/Project User
#     leaks parent project names otherwise)
#   - Task (project-scoped)
#   - Timesheet Detail (where users actually log time)
# Without scoping the children, name-leak via Link autocomplete on
# related doctypes survives the Project filter.
#
# Bypass: Administrator + System Manager — same policy as the rest of
# tenant_scope. Non-admin with no resolvable company is fail-closed
# (returns "1=0" — denies all rather than unscoping).
# ─────────────────────────────────────────────────────────────

def _is_project_bypass(user: str | None) -> bool:
    """True if this user should see all projects unrestricted."""
    user = user or frappe.session.user
    if not user or user in ("Guest", "Administrator"):
        return True
    try:
        if "System Manager" in (frappe.get_roles(user) or []):
            return True
    except Exception:
        pass
    return False


def project_query(user=None):
    """permission_query_conditions for Project: tenant + assignment.

    SQL shape:
      (company = X) AND ((owner = u) OR EXISTS row in `tabProject User`)

    The outer AND with parens is CRITICAL — a flat OR of company +
    assignment would let a user see every project they're assigned to
    regardless of company, defeating the tenant boundary.

    The EXISTS subquery correlates `pu.parent = tabProject.name` —
    without that correlation it returns true for everyone with any
    assignment anywhere (silent fail-open).
    """
    user = user or frappe.session.user
    if _is_project_bypass(user):
        return ""

    company = get_user_company(user)
    if not company:
        return "1=0"

    qc = frappe.db.escape(company)
    u = frappe.db.escape(user)

    return (
        f"(`tabProject`.company = {qc}) "
        f"AND ((`tabProject`.owner = {u}) "
        f"OR EXISTS (SELECT 1 FROM `tabProject User` pu "
        f"WHERE pu.parent = `tabProject`.name AND pu.user = {u}))"
    )


def project_has_perm(doc, ptype="read", user=None):
    """has_permission for Project — mirrors project_query for direct
    desk-URL access (`/app/project/<name>`) and REST get-by-name."""
    user = user or frappe.session.user
    if _is_project_bypass(user):
        return True

    company = get_user_company(user)
    if not company:
        return False

    doc_company = doc.get("company") if hasattr(doc, "get") else getattr(doc, "company", None)
    if doc_company and doc_company != company:
        return False

    doc_owner = doc.get("owner") if hasattr(doc, "get") else getattr(doc, "owner", None)
    if doc_owner == user:
        return True

    name = doc.get("name") if hasattr(doc, "get") else getattr(doc, "name", None)
    if not name:
        return False
    try:
        rows = frappe.get_all(
            "Project User",
            filters={"parent": name, "user": user},
            limit=1, ignore_permissions=True,
        )
        return bool(rows)
    except Exception:
        return False


def project_user_query(user=None):
    """Scope Project User child rows so /api/resource/Project User
    can't enumerate cross-tenant team membership."""
    user = user or frappe.session.user
    if _is_project_bypass(user):
        return ""

    company = get_user_company(user)
    if not company:
        return "1=0"

    qc = frappe.db.escape(company)
    u = frappe.db.escape(user)

    return (
        f"EXISTS (SELECT 1 FROM `tabProject` p "
        f"WHERE p.name = `tabProject User`.parent "
        f"AND p.company = {qc} "
        f"AND ((p.owner = {u}) "
        f"OR EXISTS (SELECT 1 FROM `tabProject User` pu2 "
        f"WHERE pu2.parent = p.name AND pu2.user = {u})))"
    )


def project_user_has_perm(doc, ptype="read", user=None):
    user = user or frappe.session.user
    if _is_project_bypass(user):
        return True
    parent = doc.get("parent") if hasattr(doc, "get") else getattr(doc, "parent", None)
    if not parent:
        return False
    try:
        proj = frappe.get_doc("Project", parent)
    except Exception:
        return False
    return project_has_perm(proj, ptype, user)


def task_query(user=None):
    """Scope Task to tasks whose parent Project is visible to user."""
    user = user or frappe.session.user
    if _is_project_bypass(user):
        return ""

    company = get_user_company(user)
    if not company:
        return "1=0"

    qc = frappe.db.escape(company)
    u = frappe.db.escape(user)

    # Tasks with NULL project (rare — standalone tasks) are denied for
    # non-admins. If the org needs standalone tasks, relax this.
    return (
        f"`tabTask`.project IS NOT NULL "
        f"AND EXISTS (SELECT 1 FROM `tabProject` p "
        f"WHERE p.name = `tabTask`.project "
        f"AND p.company = {qc} "
        f"AND ((p.owner = {u}) "
        f"OR EXISTS (SELECT 1 FROM `tabProject User` pu "
        f"WHERE pu.parent = p.name AND pu.user = {u})))"
    )


def task_has_perm(doc, ptype="read", user=None):
    user = user or frappe.session.user
    if _is_project_bypass(user):
        return True
    project = doc.get("project") if hasattr(doc, "get") else getattr(doc, "project", None)
    if not project:
        return False
    try:
        proj = frappe.get_doc("Project", project)
    except Exception:
        return False
    return project_has_perm(proj, ptype, user)


def timesheet_detail_query(user=None):
    """Scope Timesheet Detail rows by their project field. Closes the
    leak where a user could see other users' hours via
    /api/resource/Timesheet Detail filtered by project name. Rows
    with no project (non-billable internal time) pass through —
    parent Timesheet ownership protects them via Frappe's owner-perm."""
    user = user or frappe.session.user
    if _is_project_bypass(user):
        return ""

    company = get_user_company(user)
    if not company:
        return "1=0"

    qc = frappe.db.escape(company)
    u = frappe.db.escape(user)

    return (
        f"((`tabTimesheet Detail`.project IS NULL "
        f"OR `tabTimesheet Detail`.project = '') "
        f"OR EXISTS (SELECT 1 FROM `tabProject` p "
        f"WHERE p.name = `tabTimesheet Detail`.project "
        f"AND p.company = {qc} "
        f"AND ((p.owner = {u}) "
        f"OR EXISTS (SELECT 1 FROM `tabProject User` pu "
        f"WHERE pu.parent = p.name AND pu.user = {u}))))"
    )


# ─────────────────────────────────────────────────────────────
# Server-side validation: Timesheet save
#
# permission_query_conditions filters list views and Link autocompletes
# but Frappe's `validate_link` only checks DocType existence — a user
# could craft an HTTP POST with a project name they can't read and the
# row would save. This hook closes that bypass.
# ─────────────────────────────────────────────────────────────

def validate_timesheet_projects(doc, method=None):
    """Timesheet.validate — reject if any time_logs row references a
    project the user isn't assigned to."""
    user = frappe.session.user
    if _is_project_bypass(user):
        return

    for row in (doc.get("time_logs") or []):
        project = row.get("project") if hasattr(row, "get") else getattr(row, "project", None)
        if not project:
            continue
        try:
            proj = frappe.get_doc("Project", project)
        except Exception:
            frappe.throw(
                f"Project '{project}' not found or you don't have access.",
                title="Timesheet: project access denied",
            )
        if not project_has_perm(proj, "read", user):
            frappe.throw(
                f"You are not assigned to project '{project}'. Ask the "
                f"project owner to add you under Project > Users "
                f"before logging time.",
                title="Timesheet: project access denied",
            )


# ─────────────────────────────────────────────────────────────
# Auto-add project creator to Project.users
#
# project_query already grants visibility via the `owner = user` clause,
# but Project's Users tab is the canonical team UI — keeping it
# populated avoids "I created the project but the team list is empty"
# UX confusion and gives PMs a single place to manage membership.
# ─────────────────────────────────────────────────────────────

def auto_add_project_creator(doc, method=None):
    """Project.before_insert — append the creator (frappe.session.user)
    to Project.users if not already there. Skipped for Administrator
    (bench-driven creation, no UX expectation)."""
    user = frappe.session.user
    if user in ("Administrator", "Guest"):
        return

    existing = {(row.get("user") if hasattr(row, "get") else getattr(row, "user", None))
                for row in (doc.get("users") or [])}
    if user in existing:
        return

    doc.append("users", {"user": user, "welcome_email_sent": 1})
