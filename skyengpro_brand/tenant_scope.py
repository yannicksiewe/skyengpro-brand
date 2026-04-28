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
