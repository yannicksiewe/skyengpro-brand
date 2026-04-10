import frappe
import shutil
import os


BRAND_FILES = [
    "SkyEngPro_Logo_Primary_400px.png",
    "SkyEngPro_Icon_32px.png",
    "SkyEngPro_Icon_512px.png",
    "SkyEngPro_Logo_Tagline_800px.png",
    "SkyEngPro_Logo_White_800px.png",
]


def after_install():
    copy_brand_assets()
    apply_website_settings()
    apply_navbar_settings()
    apply_system_settings()
    frappe.db.commit()


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
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
            frappe.logger().info(f"SkyEngPro brand: copied {fname}")


def apply_website_settings():
    ws = frappe.get_single("Website Settings")
    ws.app_name = "SkyEngPro"
    ws.brand_image = "/files/SkyEngPro_Logo_Primary_400px.png"
    ws.favicon = "/files/SkyEngPro_Icon_32px.png"
    ws.splash_image = "/files/SkyEngPro_Logo_Tagline_800px.png"
    ws.save(ignore_permissions=True)


def apply_navbar_settings():
    ns = frappe.get_single("Navbar Settings")
    ns.app_logo = "/files/SkyEngPro_Logo_Primary_400px.png"
    ns.save(ignore_permissions=True)


def apply_system_settings():
    ss = frappe.get_single("System Settings")
    ss.app_name = "SkyEngPro"
    ss.save(ignore_permissions=True)
