"""
SkyEngPro Platform — Post-install / Post-migrate Setup

Runs automatically on:
  - bench --site <site> install-app skyengpro_brand
  - bench --site <site> migrate

Idempotent: safe to run repeatedly.
"""
import frappe
import shutil
import os


BRAND_FILES = [
    "SkyEngPro_Logo_Primary_400px.png",
    "SkyEngPro_Icon_32px.png",
    "SkyEngPro_Icon_512px.png",
    "SkyEngPro_Logo_Tagline_800px.png",
    "SkyEngPro_Logo_White_800px.png",
    "SkyEngPro_Logo_Navbar.png",
    "SkyEngPro_Logo_White_Navbar.png",
]


def after_install():
    """Main entry point — called by hooks.py on install and migrate."""
    frappe.logger("skyengpro").info("SkyEngPro setup: starting...")

    # 1. Branding (logos, favicon, system name)
    copy_brand_assets()
    apply_website_settings()
    apply_navbar_settings()
    apply_system_settings()

    # 2. Module Profiles (from config.py)
    from skyengpro_brand.setup_roles import setup_module_profiles, sync_all_users_profiles
    setup_module_profiles()
    sync_all_users_profiles()

    # 3. Desk & Workspace Permissions
    from skyengpro_brand.setup_permissions import setup_all_permissions
    setup_all_permissions()

    frappe.db.commit()
    frappe.logger("skyengpro").info("SkyEngPro setup: complete.")


# ─────────────────────────────────────────────────────────────
# Branding
# ─────────────────────────────────────────────────────────────

def copy_brand_assets():
    """Copy logo files from the app's public/files into the site's public/files."""
    app_files_dir = os.path.join(
        frappe.get_app_path("skyengpro_brand"), "public", "files"
    )
    site_files_dir = os.path.join(
        frappe.get_site_path(), "public", "files"
    )
    os.makedirs(site_files_dir, exist_ok=True)

    for fname in BRAND_FILES:
        src = os.path.join(app_files_dir, fname)
        dst = os.path.join(site_files_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            frappe.logger("skyengpro").info("Copied brand asset: %s", fname)


def apply_website_settings():
    ws = frappe.get_single("Website Settings")
    ws.app_name = "SEP ERP"
    ws.brand_image = "/files/SkyEngPro_Logo_Primary_400px.png"
    ws.favicon = "/files/SkyEngPro_Icon_32px.png"
    ws.splash_image = "/files/SkyEngPro_Logo_Tagline_800px.png"
    ws.save(ignore_permissions=True)


def apply_navbar_settings():
    ns = frappe.get_single("Navbar Settings")
    ns.app_logo = "/files/SkyEngPro_Logo_White_Navbar.png"
    ns.save(ignore_permissions=True)


def apply_system_settings():
    ss = frappe.get_single("System Settings")
    ss.app_name = "SkyEngPro"
    ss.save(ignore_permissions=True)
