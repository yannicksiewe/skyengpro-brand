"""Workspace Sidebar controller override.

Frappe's stock `WorkspaceSidebar.is_item_allowed` has a hardcoded
`if item_type == "dashboard": return True` (see
frappe/desk/doctype/workspace_sidebar/workspace_sidebar.py). That
bypass means a dashboard sidebar item — e.g. the auto-rendered
"Dashboard" entry under each module workspace — is shown to every
user regardless of `frappe.has_permission(...)` on the underlying
Dashboard doc.

This override delegates dashboard items through `has_permission`
instead, so our `Dashboard` has_permission hook
(`skyengpro_brand.dashboard_perm.dashboard_has_perm`) actually
controls visibility.

Wired via `hooks.override_doctype_class`.
"""
import frappe
from frappe.desk.doctype.workspace_sidebar.workspace_sidebar import WorkspaceSidebar


class PatchedWorkspaceSidebar(WorkspaceSidebar):
    def is_item_allowed(self, name, item_type, allowed_workspaces):
        if item_type and item_type.lower() == "dashboard":
            if frappe.session.user == "Administrator":
                return True
            try:
                return bool(frappe.has_permission("Dashboard", "read", doc=name))
            except Exception:
                # Defensive: if anything blows up resolving permissions,
                # fall back to the original "always show" behaviour
                # rather than break workspace navigation for everyone.
                return True
        return super().is_item_allowed(name, item_type, allowed_workspaces)
