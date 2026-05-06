"""Create the 7 Accounting sub-workspaces that the modal expects but
that are missing on this site (Payments / Banking / Taxes / Budget /
Share Management / Subscription / Accounts Setup).

Why this exists
───────────────
ERPNext ships only `Invoicing` and `Financial Reports` as Accounts
workspaces. The other names appear in older onboarding references and
in our `config.WORKSPACE_RESTRICTIONS` map, but they were never
created on this site, so clicking them in the sidebar/modal does
nothing — the `/app/<name>` route resolves to no Workspace and the UI
silently refuses to navigate.

This module creates simple, opinionated workspaces for the seven
missing names. Each one is:

  * `module = Accounts`, `public = 1`
  * gated by the roles already declared in `WORKSPACE_RESTRICTIONS`
    (so regular employees keep their clean sidebar)
  * populated with a header + a single Card Break grouping the 3-6
    most-relevant DocType / Report links

The function is idempotent — re-running on every migrate is safe and
cheap (existing workspaces are skipped, never overwritten, so any
manual edits in the UI survive).
"""
import json

import frappe

from skyengpro_brand.config import WORKSPACE_RESTRICTIONS


# ─────────────────────────────────────────────────────────────
# Specs
# ─────────────────────────────────────────────────────────────

# Each entry: name → (icon, card_label, [(label, link_type, link_to, dependencies?), ...])
_SPECS = {
    "Payments": (
        "accounting",
        "Payments & Vouchers",
        [
            ("Payment Entry",          "DocType", "Payment Entry"),
            ("Payment Request",        "DocType", "Payment Request"),
            ("Payment Reconciliation", "DocType", "Payment Reconciliation"),
            ("Journal Entry",          "DocType", "Journal Entry"),
            ("Journal Entry Template", "DocType", "Journal Entry Template"),
            ("Mode of Payment",        "DocType", "Mode of Payment"),
        ],
    ),
    "Banking": (
        "non_profit",
        "Banking",
        [
            ("Bank",                          "DocType", "Bank"),
            ("Bank Account",                  "DocType", "Bank Account"),
            ("Bank Transaction",              "DocType", "Bank Transaction"),
            ("Bank Clearance",                "DocType", "Bank Clearance"),
            ("Bank Reconciliation Tool",      "DocType", "Bank Reconciliation Tool"),
            ("Bank Reconciliation Statement", "Report",  "Bank Reconciliation Statement"),
        ],
    ),
    "Taxes": (
        "accounting",
        "Tax Masters",
        [
            ("Sales Taxes and Charges Template",    "DocType", "Sales Taxes and Charges Template"),
            ("Purchase Taxes and Charges Template", "DocType", "Purchase Taxes and Charges Template"),
            ("Item Tax Template",                   "DocType", "Item Tax Template"),
            ("Tax Category",                        "DocType", "Tax Category"),
            ("Tax Rule",                            "DocType", "Tax Rule"),
            ("Tax Withholding Category",            "DocType", "Tax Withholding Category"),
        ],
    ),
    # Named "Budgeting" (not "Budget") — Frappe's
    # validate_route_conflict refuses to register a Workspace whose
    # route collides with an existing DocType, and the Budget DocType
    # already owns /app/budget.
    "Budgeting": (
        "accounting",
        "Cost Center & Budgeting",
        [
            ("Budget",                  "DocType", "Budget"),
            ("Cost Center",             "DocType", "Cost Center"),
            ("Cost Center Allocation",  "DocType", "Cost Center Allocation"),
            ("Accounting Dimension",    "DocType", "Accounting Dimension"),
            ("Monthly Distribution",    "DocType", "Monthly Distribution"),
            ("Budget Variance Report",  "Report",  "Budget Variance Report"),
        ],
    ),
    "Share Management": (
        "non_profit",
        "Share Management",
        [
            ("Shareholder",     "DocType", "Shareholder"),
            ("Share Transfer",  "DocType", "Share Transfer"),
            ("Share Ledger",    "Report",  "Share Ledger"),
            ("Share Balance",   "Report",  "Share Balance"),
        ],
    ),
    # Named "Subscriptions" (plural) — same route-collision reason as
    # Budgeting above; the Subscription DocType owns /app/subscription.
    "Subscriptions": (
        "non_profit",
        "Subscription Management",
        [
            ("Subscription",          "DocType", "Subscription"),
            ("Subscription Plan",     "DocType", "Subscription Plan"),
            ("Subscription Settings", "DocType", "Subscription Settings"),
        ],
    ),
    "Accounts Setup": (
        "settings",
        "Accounting Masters",
        [
            ("Company",            "DocType", "Company"),
            ("Chart of Accounts",  "DocType", "Account"),
            ("Accounts Settings",  "DocType", "Accounts Settings"),
            ("Fiscal Year",        "DocType", "Fiscal Year"),
            ("Finance Book",       "DocType", "Finance Book"),
            ("Accounting Period",  "DocType", "Accounting Period"),
            ("Payment Term",       "DocType", "Payment Term"),
        ],
    ),
}


# ─────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────

def ensure_accounting_workspaces():
    """Create the 7 Accounting sub-workspaces if they don't exist.

    Idempotent. Existing workspaces are left untouched (so admin's
    in-UI edits survive every migrate). Roles are sourced from
    `config.WORKSPACE_RESTRICTIONS`; if the entry is missing there,
    we default to `Accounts Manager` (most restrictive sensible
    default — never broadens visibility unintentionally)."""
    for idx, (name, (icon, card_label, links)) in enumerate(_SPECS.items(), start=20):
        if frappe.db.exists("Workspace", name):
            continue
        # Skip rows whose target DocType doesn't exist on this site
        # (e.g. Subscription is gated behind the payments app — if the
        # app isn't installed, the link target won't resolve).
        usable_links = [
            (label, ltype, ltarget) for (label, ltype, ltarget) in links
            if ltype != "DocType" or frappe.db.exists("DocType", ltarget)
        ]
        if not usable_links:
            frappe.logger("skyengpro").info(
                "ensure_accounting_workspaces: skipping %s — no usable links",
                name,
            )
            continue
        try:
            _create_workspace(name, icon, card_label, usable_links, sequence_id=idx)
        except Exception:
            frappe.logger("skyengpro").exception(
                "ensure_accounting_workspaces: failed for %s", name,
            )
    frappe.db.commit()


def _create_workspace(name, icon, card_label, links, sequence_id):
    """Insert one Workspace doc + child rows."""
    # Build the content JSON: header + spacer + card block.
    content = json.dumps([
        {"id": _id(), "type": "header", "data": {
            "text": f'<span class="h4"><b>{name}</b></span>',
            "col": 12,
        }},
        {"id": _id(), "type": "card", "data": {
            "card_name": card_label, "col": 4,
        }},
    ])

    ws = frappe.new_doc("Workspace")
    ws.name = name
    ws.label = name
    ws.title = name
    ws.module = "Accounts"
    ws.public = 1
    ws.icon = icon
    ws.sequence_id = sequence_id
    ws.content = content

    # links table: one Card Break + N child links
    ws.append("links", {
        "type":             "Card Break",
        "label":            card_label,
        "icon":             icon,
        "hidden":           0,
        "onboard":          0,
        "is_query_report":  0,
    })
    for label, link_type, link_to in links:
        ws.append("links", {
            "type":             "Link",
            "label":            label,
            "link_type":        link_type,
            "link_to":          link_to,
            "icon":             icon,
            "hidden":           0,
            "onboard":          0,
            "is_query_report":  1 if link_type == "Report" else 0,
        })

    # roles: from WORKSPACE_RESTRICTIONS, with a safe fallback.
    role_names = WORKSPACE_RESTRICTIONS.get(name) or ["Accounts Manager"]
    for role in role_names:
        if not frappe.db.exists("Role", role):
            continue
        ws.append("roles", {"role": role})

    ws.insert(ignore_permissions=True)
    frappe.logger("skyengpro").info(
        "ensure_accounting_workspaces: created %s (roles=%s, links=%d)",
        name, role_names, len(links),
    )


def _id():
    """Generate a short id matching the Frappe content-block id format."""
    import secrets
    return secrets.token_urlsafe(7)[:10]
