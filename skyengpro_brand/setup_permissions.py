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
    """Set role restrictions on workspaces so only authorized roles see them.

    Uses the Workspace.roles child table. If a workspace has roles set,
    only users with at least one of those roles will see it in the sidebar.
    """
    for ws_name, roles in WORKSPACE_RESTRICTIONS.items():
        if not frappe.db.exists("Workspace", ws_name):
            frappe.logger("skyengpro").warning("Workspace '%s' not found, skipping", ws_name)
            continue

        ws = frappe.get_doc("Workspace", ws_name)
        existing_roles = set(r.role for r in ws.roles) if ws.roles else set()

        changed = False
        for role in roles:
            if role not in existing_roles and frappe.db.exists("Role", role):
                ws.append("roles", {"role": role})
                existing_roles.add(role)
                changed = True

        if changed:
            ws.save(ignore_permissions=True)
            frappe.logger("skyengpro").info(
                "Workspace '%s' restricted to: %s", ws_name, ", ".join(existing_roles)
            )

    frappe.db.commit()


def setup_all_permissions():
    """Run all permission setups."""
    setup_desk_permissions()
    setup_workspace_restrictions()
