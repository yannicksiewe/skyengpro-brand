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
    """Set role restrictions on workspaces so only authorized roles
    see them in the sidebar.

    Implementation note — we INSERT directly into `tabHas Role` rather
    than going through `frappe.get_doc("Workspace").save()`. ERPNext
    ships several workspaces with broken state in the v16.x line
    (Stock has stale Report links to removed doctypes like
    "BOM Stock Report"; Helpdesk ships with a NULL `type` that the
    schema marks mandatory). The Document layer validates EVERYTHING
    on save — orphan links, missing mandatory, etc. — so our
    role-only edit triggers unrelated failures and aborts the entire
    install pipeline.

    The Workspace `roles` child uses doctype "Has Role" (same as
    User.roles), parent = workspace name, parenttype = "Workspace",
    parentfield = "roles". Direct SQL is the only stable path here.

    Idempotent: skip if a (workspace, role) row already exists.
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

        added = []
        for role in roles:
            if role in existing_roles:
                continue
            if not frappe.db.exists("Role", role):
                continue
            frappe.db.sql(
                """INSERT INTO `tabHas Role`
                   (name, parent, parenttype, parentfield, idx, role,
                    creation, modified, modified_by, owner, docstatus)
                   VALUES (%s, %s, 'Workspace', 'roles', %s, %s,
                           NOW(), NOW(), 'Administrator', 'Administrator', 0)""",
                (
                    frappe.generate_hash(length=10),
                    ws_name,
                    len(existing_roles) + len(added) + 1,
                    role,
                ),
            )
            added.append(role)

        if added:
            frappe.logger("skyengpro").info(
                "Workspace '%s' role-restricted: added %s (now: %s)",
                ws_name, ", ".join(added),
                ", ".join(sorted(existing_roles | set(added))),
            )

    frappe.db.commit()


def setup_all_permissions():
    """Run all permission setups."""
    setup_desk_permissions()
    setup_workspace_restrictions()
