"""Make Gameplan's on_login hook safe for our multi-tenant deployment.

Gameplan registers `on_login = "gameplan.www.g.on_login"`, which
calls `get_default_route()` -> `frappe.db.get_all("GP Team", limit=1)`
on every successful login. In our multi-tenant ERPNext site, users
without a Gameplan role hit a permission-check failure on the
underlying DocType meta lookup ("User Guest does not have doctype
access via role permission for document DocType"), and login fails
site-wide.

Fix: monkey-patch `gameplan.www.g.get_default_route` to:
  - bypass the perm check via `ignore_permissions=True`
  - swallow any unexpected error and fall back to "/home" so login
    always completes

Patch is applied from skyengpro_brand/__init__.py at module import
time, so it runs once per gunicorn worker boot before any login fires.
Idempotent and a no-op when Gameplan isn't in the bench.
"""
import frappe


def _safe_get_default_route():
    try:
        if not frappe.db.get_all("GP Team", limit=1, ignore_permissions=True):
            return "/onboarding"
        return "/home"
    except Exception:
        frappe.logger("skyengpro").exception(
            "gameplan_patch: get_default_route failed; falling back to /home"
        )
        return "/home"


def apply_patch():
    try:
        from gameplan.www import g as gameplan_g
    except ImportError:
        return
    gameplan_g.get_default_route = _safe_get_default_route
