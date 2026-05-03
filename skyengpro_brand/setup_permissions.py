"""
SkyEngPro Platform — Desk & Workspace Permissions Setup

Sets up:
1. Page doctype read permission for desk roles
2. Workspace role restrictions (visibility filtering)

Idempotent: safe to run multiple times.
"""
import frappe
from skyengpro_brand.config import DESK_ACCESS_ROLES, WORKSPACE_RESTRICTIONS


def setup_desk_permissions():
    """Grant Page doctype read permission to all desk roles.

    Without this, non-admin users get:
    'User X does not have doctype access via role permission for document Page'
    """
    existing = set()
    for perm in frappe.get_all("Custom DocPerm", filters={"parent": "Page"}, fields=["role"]):
        existing.add(perm.role)

    for role in DESK_ACCESS_ROLES:
        if role not in existing and frappe.db.exists("Role", role):
            frappe.get_doc({
                "doctype": "Custom DocPerm",
                "parent": "Page",
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": role,
                "permlevel": 0,
                "read": 1,
            }).insert(ignore_permissions=True)
            frappe.logger("skyengpro").info("Added Page read permission for role: %s", role)

    frappe.db.commit()


def setup_workspace_restrictions():
    """Reconcile workspace role restrictions to match WORKSPACE_RESTRICTIONS.

    Authoritative — the listed roles become the EXACT set of roles on the
    workspace. Anything previously allowed but not in the list is pruned.
    This was previously additive-only, which left workspaces visible to
    pre-existing roles (e.g. ERPNext ships "Build" and "Users" with no
    role rows = visible to all; an additive add of System Manager doesn't
    actually hide them from Employee). Authoritative reconciliation closes
    that gap.

    Direct SQL (not Document layer) because ERPNext v16.x ships several
    workspaces with broken state (orphan Report links, NULL mandatory
    fields). Document.save() validates everything and aborts our edit on
    unrelated errors. The Workspace `roles` child uses doctype "Has Role"
    (same as User.roles): parent = workspace name, parenttype = Workspace.
    """
    for ws_name, roles in WORKSPACE_RESTRICTIONS.items():
        if not frappe.db.exists("Workspace", ws_name):
            frappe.logger("skyengpro").debug("Workspace '%s' not found, skipping", ws_name)
            continue

        existing_roles = {
            r["role"] for r in frappe.db.sql(
                """SELECT role FROM `tabHas Role`
                   WHERE parent = %s AND parenttype = 'Workspace'""",
                ws_name, as_dict=True,
            )
        }
        allowed = {r for r in roles if frappe.db.exists("Role", r)}
        to_remove = existing_roles - allowed
        to_add = allowed - existing_roles

        if to_remove:
            placeholders = ",".join(["%s"] * len(to_remove))
            frappe.db.sql(
                f"""DELETE FROM `tabHas Role`
                    WHERE parent = %s AND parenttype = 'Workspace'
                      AND role IN ({placeholders})""",
                (ws_name, *to_remove),
            )

        for i, role in enumerate(to_add, start=len(existing_roles - to_remove) + 1):
            frappe.db.sql(
                """INSERT INTO `tabHas Role`
                   (name, parent, parenttype, parentfield, idx, role,
                    creation, modified, modified_by, owner, docstatus)
                   VALUES (%s, %s, 'Workspace', 'roles', %s, %s,
                           NOW(), NOW(), 'Administrator', 'Administrator', 0)""",
                (frappe.generate_hash(length=10), ws_name, i, role),
            )

        if to_remove or to_add:
            frappe.logger("skyengpro").info(
                "Workspace '%s' reconciled: removed=%s added=%s final=%s",
                ws_name,
                ", ".join(sorted(to_remove)) or "-",
                ", ".join(sorted(to_add)) or "-",
                ", ".join(sorted(allowed)),
            )

    frappe.db.commit()


def setup_all_permissions():
    """Run all permission setups."""
    setup_desk_permissions()
    setup_workspace_restrictions()
