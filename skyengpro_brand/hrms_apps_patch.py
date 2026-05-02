"""Make Frappe HR's `add_to_apps_screen` permission stricter.

HRMS ships with `add_to_apps_screen.has_permission` set to
`hrms.hr.utils.check_app_permission`, which returns True for any
user with read on Employee — i.e. every employee. That keeps the
Frappe HR app card on `/desk` even for users whose HR / Payroll
modules are blocked at the Module Profile level.

This patch wraps the original callback: it ALSO requires that at
least one of {HR, Payroll} not be in the user's Block Module list.
Once both are blocked, the user has no useful HR workspaces — so
the app card should disappear from the apps grid.

Why a monkey-patch and not a hooks-level override:
`bootinfo["apps_data"]["apps"]` is populated by `frappe.apps.get_apps()`
in `frappe.sessions.get()` AFTER the boot_session and extend_bootinfo
hooks run. There's no post-hook between apps_data assignment and the
HTTP response, so the only way to influence what the apps grid shows
is to make the per-app `has_permission` callback say no.

Patch is applied from skyengpro_brand/__init__.py at module import
time, so it runs once per gunicorn worker boot before any /desk
request fires. Idempotent and a no-op when HRMS isn't installed.
"""
import frappe


def _patched_check_app_permission():
    """Frappe HR app-card permission gate.

    Original behaviour:
      - True for Administrator
      - False for Website Users
      - True if user has read on Employee (i.e. every linked employee)

    Added: even if the original returns True, we also require that
    at least one of HR / Payroll modules is NOT blocked for the user.
    Once both are blocked, the user reaches no HR workspaces, so
    keeping the card around is just clutter.
    """
    if frappe.session.user == "Administrator":
        return True
    try:
        from hrms.hr.utils import check_app_permission as _orig
    except ImportError:
        return True

    # Run the original gate first — preserves Website User block etc.
    if not _orig():
        return False

    # Module-block gate: hide the card when both HR + Payroll are blocked.
    blocked = set(
        frappe.db.get_all(
            "Block Module",
            filters={
                "parent": frappe.session.user,
                "parenttype": "User",
            },
            pluck="module",
        )
        or []
    )
    if "HR" in blocked and "Payroll" in blocked:
        return False
    return True


def apply_patch():
    try:
        import hrms.hr.utils as _hrms_utils
    except ImportError:
        return
    _hrms_utils.check_app_permission = _patched_check_app_permission
