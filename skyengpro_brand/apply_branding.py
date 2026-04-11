"""
SkyEngPro — Apply Branding (single source of truth)

Run this to set ALL branding to a known good state.
Safe to re-run anytime — always produces the same result.

Usage:
    cd /home/frappe/frappe-bench
    env/bin/python -c "
    import frappe
    frappe.init(site='<site>', sites_path='/home/frappe/frappe-bench/sites')
    frappe.connect()
    frappe.set_user('Administrator')
    from skyengpro_brand.apply_branding import apply_all
    apply_all()
    frappe.destroy()
    "

Logo assignments:
    Login page:  SkyEngPro_Logo_Primary_400px.png  (orange+gray, visible on white bg)
    Navbar:      SkyEngPro_Logo_Primary_400px.png  (orange+gray, works on both light/dark)
    Favicon:     SkyEngPro_Icon_32px.png            (SEP mark)
    System name: SEP ERP
"""
import frappe
import shutil
import os


# ─── Logo file assignments (edit ONLY here to change) ───
LOGO_LOGIN = "/files/SkyEngPro_Logo_Primary_400px.png"    # login page splash
LOGO_NAVBAR = "/files/SkyEngPro_Logo_Primary_400px.png"   # navbar top-left
LOGO_BRAND = "/files/SkyEngPro_Logo_Primary_400px.png"    # website brand
FAVICON = "/files/SkyEngPro_Icon_32px.png"                # browser tab icon
APP_NAME = "SEP ERP"                                       # browser tab title

# All brand files to copy from app → site
BRAND_FILES = [
    "SkyEngPro_Logo_Primary_400px.png",
    "SkyEngPro_Icon_32px.png",
    "SkyEngPro_Icon_512px.png",
    "SkyEngPro_Logo_Tagline_800px.png",
    "SkyEngPro_Logo_White_800px.png",
    "SkyEngPro_Logo_Navbar.png",
    "SkyEngPro_Logo_White_Navbar.png",
]


def apply_all():
    """Apply all branding in one shot. Idempotent."""
    print("=== SkyEngPro Branding Setup ===")
    _copy_assets()
    _set_website_settings()
    _set_navbar_settings()
    _set_system_settings()
    frappe.db.commit()
    frappe.clear_cache()
    print("=== Done ===")
    print("  Login logo:  " + LOGO_LOGIN)
    print("  Navbar logo: " + LOGO_NAVBAR)
    print("  Favicon:     " + FAVICON)
    print("  App name:    " + APP_NAME)


def _copy_assets():
    app_dir = os.path.join(frappe.get_app_path("skyengpro_brand"), "public", "files")
    site_dir = os.path.join(frappe.get_site_path(), "public", "files")
    os.makedirs(site_dir, exist_ok=True)
    for f in BRAND_FILES:
        src = os.path.join(app_dir, f)
        dst = os.path.join(site_dir, f)
        if os.path.exists(src):
            shutil.copy2(src, dst)
    print("  Copied " + str(len(BRAND_FILES)) + " brand assets")


def _set_website_settings():
    ws = frappe.get_single("Website Settings")
    ws.app_name = APP_NAME
    ws.brand_image = LOGO_BRAND
    ws.favicon = FAVICON
    ws.splash_image = LOGO_LOGIN
    ws.save(ignore_permissions=True)
    print("  Website Settings updated")


def _set_navbar_settings():
    ns = frappe.get_single("Navbar Settings")
    ns.app_logo = LOGO_NAVBAR
    ns.save(ignore_permissions=True)
    print("  Navbar Settings updated")


def _set_system_settings():
    ss = frappe.get_single("System Settings")
    ss.app_name = APP_NAME
    ss.save(ignore_permissions=True)
    print("  System Settings updated")
