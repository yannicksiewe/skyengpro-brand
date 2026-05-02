"""Wave 2.5: Custom DocPerm write-strip.

Closes write-access leaks where a role ships with `write=1` on a
doctype it shouldn't be editing — most critically:

  - `Employee Self Service` writes on `Employee` → user can edit her
    own salary (`ctc`, `salary_mode`, etc.). Permlevel-6 gate on
    salary fields hides them from form, but the Custom DocPerm row
    still allows write at permlevel 0 on every other Employee field
    (joining_date, status, reports_to, …) — all forge-able.

  - Various roles (`HR User`, `Sales User`, `Purchase User`, …) ship
    with `write=1` on `Company` from stock ERPNext profiles. Result:
    any employee with one of those roles can rewrite the company
    address, tax_id, default letter head, etc.

Implementation note (architect's brief): NEVER delete the standard
DocPerm row — `bench migrate` recreates it from the doctype JSON.
Frappe's permission resolver REPLACES standard DocPerm with Custom
DocPerm whenever ANY Custom DocPerm exists for `(parent, role,
permlevel)`. So we insert/update a Custom DocPerm row that mirrors
the existing flags (read, if_owner, etc.) and only flips write,
create, and delete to 0.

Idempotent: re-running on every migrate is safe. If a Custom DocPerm
row already exists for the (parent, role, permlevel) triplet, we
only flip write/create/delete to 0 — `read`, `if_owner`, and admin-
edited submit/cancel/amend flags are preserved.
"""
import frappe

from skyengpro_brand.config import DOCPERM_WRITE_LOCKDOWN

# Flags to mirror from the source row (standard or existing custom).
# We preserve read, if_owner, and document-flow flags; we always force
# write/create/delete to 0.
_MIRROR_FLAGS = (
    "read", "if_owner", "submit", "cancel", "amend",
    "report", "export", "print", "email", "share",
)


def apply_docperm_lockdowns():
    """Force write=0 / create=0 / delete=0 for each (doctype, role)
    in DOCPERM_WRITE_LOCKDOWN. See module docstring for rationale."""
    for doctype, role in DOCPERM_WRITE_LOCKDOWN:
        if not frappe.db.exists("Role", role):
            frappe.logger("skyengpro").debug(
                "docperm_lockdown: role '%s' missing — skipping %s/%s",
                role, doctype, role,
            )
            continue
        if not frappe.db.exists("DocType", doctype):
            continue
        _force_no_write(doctype, role, permlevel=0)
    frappe.db.commit()


def _force_no_write(doctype: str, role: str, permlevel: int = 0):
    """Idempotently force write/create/delete=0 on (doctype, role,
    permlevel), preserving every other flag.

    Branch 1: Custom DocPerm row already exists. Only flip the three
    target flags; admin may have edited read/if_owner/submit
    intentionally.

    Branch 2: No Custom DocPerm yet. Mirror the flags from the
    standard DocPerm row (if any) and insert a new Custom DocPerm
    with write/create/delete forced to 0. If no standard row exists
    either (rare — role doesn't appear on the doctype at all), insert
    a minimal read-only row.
    """
    filters = {"parent": doctype, "role": role, "permlevel": permlevel}

    existing = frappe.db.get_value(
        "Custom DocPerm", filters,
        ["name"] + list(_MIRROR_FLAGS) + ["write", "create", "delete"],
        as_dict=True,
    )
    if existing:
        # Branch 1 — flip target flags only if any are still 1.
        changes = {}
        for flag in ("write", "create", "delete"):
            if existing.get(flag):
                changes[flag] = 0
        if not changes:
            return  # already locked down — nothing to do
        for flag, value in changes.items():
            frappe.db.set_value(
                "Custom DocPerm", existing["name"], flag, value,
                update_modified=False,
            )
        frappe.logger("skyengpro").info(
            "docperm_lockdown: %s/%s flipped %s -> 0",
            doctype, role, ",".join(changes.keys()),
        )
        return

    # Branch 2 — no Custom DocPerm yet. Mirror flags from standard.
    std = frappe.db.get_value(
        "DocPerm", filters, list(_MIRROR_FLAGS), as_dict=True,
    ) or {}

    new_row = {
        "doctype":     "Custom DocPerm",
        "parent":      doctype,
        "parenttype":  "DocType",
        "parentfield": "permissions",
        "role":        role,
        "permlevel":   permlevel,
        "read":        std.get("read", 1),
        "write":       0,
        "create":      0,
        "delete":      0,
        "if_owner":    std.get("if_owner", 0),
        "submit":      std.get("submit", 0),
        "cancel":      std.get("cancel", 0),
        "amend":       std.get("amend", 0),
        "report":      std.get("report", 1),
        "export":      std.get("export", 0),
        "print":       std.get("print", 1),
        "email":       std.get("email", 1),
        "share":       std.get("share", 1),
    }
    try:
        frappe.get_doc(new_row).insert(ignore_permissions=True)
        frappe.logger("skyengpro").info(
            "docperm_lockdown: %s/%s Custom DocPerm inserted (write=0)",
            doctype, role,
        )
    except Exception:
        frappe.logger("skyengpro").exception(
            "docperm_lockdown: insert failed for %s/%s", doctype, role,
        )
