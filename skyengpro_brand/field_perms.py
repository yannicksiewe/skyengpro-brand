"""Wave 2: field-level permlevel gates on Project + Company.

Two coordinated mechanisms:

1) Property Setter on each gated field — bumps `permlevel` from 0 to
   the gating level. Standard DocPerm rules grant non-admin roles
   read at permlevel 0 only, so once the field is at permlevel >0 it
   silently disappears from form/list/REST.

2) Custom DocPerm row at the gating permlevel for the unlock role.
   Assigning that role to a user grants read at the elevated level,
   restoring visibility of the gated fields without granting
   anything else.

Idempotent: re-running on every migrate is safe and cheap. Existing
Property Setter / Custom DocPerm rows with the same composite key
are left untouched (no DELETE+INSERT — protects user-edited rows).

Pre-flight:
  - Mandatory fields (reqd=1) are excluded from the gates by
    construction (see config.py). Raising permlevel on a reqd=1
    field breaks save for every user without that level.
  - Custom DocPerm rows are added at the elevated permlevel only;
    permlevel 0 access for the role still flows through the doctype's
    standard role table (Projects User has read at 0 by default).
"""
import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from skyengpro_brand.config import (
    COMPANY_FIELD_PERMLEVELS,
    EMPLOYEE_FIELD_PERMLEVELS,
    PROJECT_FIELD_PERMLEVELS,
)


def apply_field_permlevels():
    """Entry point — wired into install.py after_install."""
    _apply_doctype_gates("Project", PROJECT_FIELD_PERMLEVELS)
    _apply_doctype_gates("Company", COMPANY_FIELD_PERMLEVELS)
    _apply_doctype_gates("Employee", EMPLOYEE_FIELD_PERMLEVELS)
    frappe.db.commit()


def _apply_doctype_gates(doctype: str, gates: dict):
    """For a doctype: bump field permlevels + add Custom DocPerm rows
    granting read at those permlevels for the named role.

    `gates` shape: {role_name: {permlevel: [fieldnames]}}
    """
    # Step 1: set Property Setter for each (doctype, fieldname) -> permlevel
    for role, level_map in gates.items():
        for permlevel, fieldnames in level_map.items():
            for fieldname in fieldnames:
                _set_field_permlevel(doctype, fieldname, permlevel)

    # Step 2: add Custom DocPerm row granting read at each permlevel
    for role, level_map in gates.items():
        if not frappe.db.exists("Role", role):
            frappe.logger("skyengpro").warning(
                "field_perms: role '%s' missing — Custom DocPerm skipped", role
            )
            continue
        for permlevel in level_map.keys():
            _ensure_custom_docperm(doctype, role, permlevel)


def _set_field_permlevel(doctype: str, fieldname: str, permlevel: int):
    """Property Setter on (doctype, fieldname).permlevel.

    Looks up the field in BOTH `tabDocField` (standard fields) and
    `tabCustom Field` (admin- and app-added fields). HRMS for example
    adds the Company "HR & Payroll" tab as a Custom Field — without
    the Custom Field fallback, the existence check would fail and we'd
    silently skip the permlevel bump.

    Skip if the field doesn't exist (defensive — field name typos in
    config.py shouldn't error the install). Skip if the field is
    mandatory (reqd=1) — raising permlevel on a reqd field breaks
    save for everyone without that level.
    """
    field_meta = frappe.db.get_value(
        "DocField",
        {"parent": doctype, "fieldname": fieldname},
        ["fieldname", "reqd", "fieldtype"],
        as_dict=True,
    )
    if not field_meta:
        field_meta = frappe.db.get_value(
            "Custom Field",
            {"dt": doctype, "fieldname": fieldname},
            ["fieldname", "reqd", "fieldtype"],
            as_dict=True,
        )
    if not field_meta:
        frappe.logger("skyengpro").debug(
            "field_perms: %s.%s not found in DocField or Custom Field — skipping",
            doctype, fieldname,
        )
        return

    if field_meta.reqd:
        frappe.logger("skyengpro").warning(
            "field_perms: refusing to gate mandatory field %s.%s (would break save)",
            doctype, fieldname,
        )
        return

    try:
        make_property_setter(
            doctype,
            fieldname,
            "permlevel",
            permlevel,
            "Int",
            for_doctype=False,
            validate_fields_for_doctype=False,
        )
    except Exception:
        frappe.logger("skyengpro").exception(
            "field_perms: make_property_setter failed for %s.%s", doctype, fieldname
        )


def _ensure_custom_docperm(doctype: str, role: str, permlevel: int):
    """Idempotently insert a Custom DocPerm row granting `read` to
    `role` at `permlevel` on `doctype`.

    Match key: (parent=doctype, role=role, permlevel=permlevel). If
    a row already exists with that triplet, leave it alone — admins
    may have edited individual flags (write/create/delete).
    """
    filters = {"parent": doctype, "role": role, "permlevel": permlevel}
    if frappe.db.exists("Custom DocPerm", filters):
        return
    try:
        frappe.get_doc({
            "doctype":     "Custom DocPerm",
            "parent":      doctype,
            "parenttype":  "DocType",
            "parentfield": "permissions",
            "role":        role,
            "permlevel":   permlevel,
            "read":        1,
            # write/create/delete intentionally NOT set — costing/more-info
            # viewers are read-only by design.
        }).insert(ignore_permissions=True)
        frappe.logger("skyengpro").info(
            "field_perms: Custom DocPerm %s/%s/permlevel=%d -> read=1 created",
            doctype, role, permlevel,
        )
    except Exception:
        frappe.logger("skyengpro").exception(
            "field_perms: failed creating Custom DocPerm for %s/%s@%d",
            doctype, role, permlevel,
        )
