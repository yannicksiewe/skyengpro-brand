"""Per-dashboard role gates.

Frappe's workspace sidebar auto-injects a "Dashboard" entry under
each module that has a `Dashboard` doc with `module=<workspace>`.
This injection is independent of `Workspace Link` rows — gating
the underlying Report (which we already do for Project Summary)
makes the dashboard render empty but does NOT remove the sidebar
entry, because the entry's visibility is decided by
`frappe.has_permission("Dashboard", "read", doc=<dashboard_name>)`.

This module wires `has_permission` for the Dashboard doctype so
specific dashboards can be gated to specific roles. Currently:

  - `Project` dashboard → Projects Manager / System Manager only.

Side effect: the auto-injected sidebar entry disappears for users
without the listed roles, and `/app/dashboard-view/Project`
returns a permission error.
"""
import frappe


# Dashboard name -> roles allowed to view. Anything not listed here
# is left untouched (returns True = no opinion, DocPerm decides).
DASHBOARD_ROLE_GATES = {
    "Project": {"Projects Manager", "System Manager"},
}


def dashboard_has_perm(doc, ptype="read", user=None):
    """has_permission hook for Dashboard. ANDs with DocPerm."""
    name = getattr(doc, "name", None) or (doc.get("name") if hasattr(doc, "get") else None)
    if not name:
        return True
    gates = DASHBOARD_ROLE_GATES.get(name)
    if not gates:
        return True
    user_roles = set(frappe.get_roles(user or frappe.session.user))
    return bool(gates & user_roles)
