__version__ = "1.0.0"

# Monkey-patch gameplan.www.g.get_default_route so its on_login hook
# can't take down login site-wide. See gameplan_patch.py for the why.
# Runs once per gunicorn worker boot; no-op if gameplan isn't in apps/.
try:
    from skyengpro_brand.gameplan_patch import apply_patch as _apply_gameplan_patch
    _apply_gameplan_patch()
except Exception:
    pass

# Tighten Frappe HR's `add_to_apps_screen` permission gate so the
# app card disappears from /desk when HR + Payroll modules are
# blocked. See hrms_apps_patch.py — bootinfo.apps_data["apps"] is
# populated AFTER our boot_session hook so per-app has_permission
# callbacks are the only handle.
try:
    from skyengpro_brand.hrms_apps_patch import apply_patch as _apply_hrms_apps_patch
    _apply_hrms_apps_patch()
except Exception:
    pass
