"""
SkyEngPro Platform — Role & Module Profile Setup

Creates Module Profiles and syncs blocked modules to users.
Idempotent: safe to run multiple times.
"""
import frappe
from skyengpro_brand.config import PROFILES


def setup_module_profiles():
    """Create or update all Module Profiles defined in config."""
    all_modules = get_all_module_names()

    for profile_name, profile in PROFILES.items():
        allowed = set(profile["allowed_modules"])
        blocked = [m for m in all_modules if m not in allowed]

        _upsert_module_profile(profile_name, blocked)
        frappe.logger("skyengpro").info(
            "Module Profile '%s': %d allowed, %d blocked",
            profile_name, len(allowed), len(blocked)
        )

    frappe.db.commit()


def sync_user_module_profile(user_email):
    """Sync a user's block_modules from their assigned Module Profile.

    Call this after assigning a Module Profile to a user, because
    Frappe's built-in sync (Module Profile.on_update) uses background
    jobs that may not run reliably in all environments.
    """
    user = frappe.get_doc("User", user_email)
    if not user.module_profile:
        return

    profile = frappe.get_doc("Module Profile", user.module_profile)
    blocked_modules = [d.module for d in profile.block_modules]

    # Clear existing and re-insert
    frappe.db.sql(
        "DELETE FROM `tabBlock Module` WHERE parent=%s AND parenttype='User'",
        user_email
    )
    for i, module in enumerate(blocked_modules):
        frappe.db.sql(
            """INSERT INTO `tabBlock Module`
            (name, parent, parenttype, parentfield, idx, module,
             creation, modified, modified_by, owner, docstatus)
            VALUES (%s, %s, 'User', 'block_modules', %s, %s,
                    NOW(), NOW(), 'Administrator', 'Administrator', 0)""",
            (frappe.generate_hash(length=10), user_email, i + 1, module)
        )

    frappe.db.commit()


def sync_all_users_profiles():
    """Sync block_modules for ALL users who have a Module Profile."""
    users = frappe.get_all(
        "User",
        filters={"module_profile": ["is", "set"], "enabled": 1},
        fields=["name", "module_profile"]
    )
    for user in users:
        sync_user_module_profile(user.name)
        frappe.logger("skyengpro").info(
            "Synced modules for %s (profile: %s)", user.name, user.module_profile
        )


def get_all_module_names():
    """Return sorted list of all module names in the system."""
    return sorted([
        m.module_name
        for m in frappe.get_all("Module Def", fields=["module_name"])
    ])


def _upsert_module_profile(name, blocked_modules):
    """Create or update a Module Profile with the given blocked modules."""
    # Delete existing (clean slate)
    if frappe.db.exists("Module Profile", name):
        frappe.db.sql(
            "DELETE FROM `tabBlock Module` WHERE parent=%s AND parenttype='Module Profile'",
            name
        )
        frappe.db.sql("DELETE FROM `tabModule Profile` WHERE name=%s", name)

    # Insert profile
    frappe.db.sql(
        """INSERT INTO `tabModule Profile`
        (name, creation, modified, modified_by, owner, module_profile_name)
        VALUES (%s, NOW(), NOW(), 'Administrator', 'Administrator', %s)""",
        (name, name)
    )

    # Insert blocked modules
    for i, module in enumerate(blocked_modules):
        frappe.db.sql(
            """INSERT INTO `tabBlock Module`
            (name, parent, parenttype, parentfield, idx, module,
             creation, modified, modified_by, owner, docstatus)
            VALUES (%s, %s, 'Module Profile', 'block_modules', %s, %s,
                    NOW(), NOW(), 'Administrator', 'Administrator', 0)""",
            (frappe.generate_hash(length=10), name, i + 1, module)
        )
