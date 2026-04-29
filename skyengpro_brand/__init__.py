__version__ = "1.0.0"

# Monkey-patch gameplan.www.g.get_default_route so its on_login hook
# can't take down login site-wide. See gameplan_patch.py for the why.
# Runs once per gunicorn worker boot; no-op if gameplan isn't in apps/.
try:
    from skyengpro_brand.gameplan_patch import apply_patch as _apply_gameplan_patch
    _apply_gameplan_patch()
except Exception:
    pass
