"""
SkyEngPro Platform — Role & Module Profile Setup

Creates Module Profiles, custom roles, and reconciles user assignments.
Idempotent: safe to run multiple times.
"""
import frappe
from skyengpro_brand.config import (
    CUSTOM_ROLES,
    DEFAULT_MODULE_PROFILE,
    DEFAULT_USER_ROLES,
    PROFILES,
)


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


def ensure_custom_roles():
    """Create the per-tab unlocking roles (Wave-2 placeholders).

    Idempotent — uses frappe.db.exists guards so re-runs leave
    user-edited Role docs alone. Roles must exist BEFORE any DocPerm
    rows can reference them, so this runs early in after_install.
    """
    for role_def in CUSTOM_ROLES:
        name = role_def["role_name"]
        if frappe.db.exists("Role", name):
            continue
        frappe.get_doc({
            "doctype":     "Role",
            "role_name":   name,
            "desk_access": role_def.get("desk_access", 1),
            "description": role_def.get("description", ""),
        }).insert(ignore_permissions=True)
        frappe.logger("skyengpro").info("Created Role: %s", name)


def apply_default_profile_to_existing():
    """Attach DEFAULT_MODULE_PROFILE to every enabled non-admin user
    that doesn't already have a profile, plus the canonical default
    roles (Employee + Employee Self Service).

    Skip rules:
      - user is Administrator or Guest
      - user already has a module_profile (admin assigned something
        specific — don't overwrite)
      - user has the System Manager role (platform admin — needs to
        see everything)
      - user.user_type != 'System User' (Website Users / portal-only
        users don't have desk; module_profile is a no-op)

    For each user we touch, also call sync_user_module_profile so the
    block_modules list is materialized immediately (Frappe's built-in
    sync runs in a background job that doesn't always fire on GKE).
    """
    if not frappe.db.exists("Module Profile", DEFAULT_MODULE_PROFILE):
        frappe.logger("skyengpro").warning(
            "apply_default_profile_to_existing: profile '%s' missing — "
            "did setup_module_profiles run?", DEFAULT_MODULE_PROFILE,
        )
        return

    users = frappe.get_all(
        "User",
        filters={"enabled": 1, "user_type": "System User"},
        fields=["name", "module_profile"],
    )
    touched = 0
    for u in users:
        if u.name in ("Administrator", "Guest"):
            continue
        if u.module_profile:
            continue
        if "System Manager" in (frappe.get_roles(u.name) or []):
            continue

        frappe.db.set_value(
            "User", u.name, "module_profile", DEFAULT_MODULE_PROFILE,
            update_modified=False,
        )
        ensure_user_has_default_roles(u.name)
        sync_user_module_profile(u.name)
        touched += 1

    frappe.db.commit()
    frappe.logger("skyengpro").info(
        "apply_default_profile_to_existing: assigned '%s' + default roles to %d user(s)",
        DEFAULT_MODULE_PROFILE, touched,
    )


def ensure_user_has_default_roles(user_email: str):
    """Make sure the user has the canonical employee roles.

    Idempotent — only adds the role if it's missing. Also requires the
    Role record to exist (Employee Self Service ships with frappe-hr;
    if not installed we skip).
    """
    user = frappe.get_doc("User", user_email)
    existing = {r.role for r in user.roles}
    added = False
    for role in DEFAULT_USER_ROLES:
        if role in existing:
            continue
        if not frappe.db.exists("Role", role):
            frappe.logger("skyengpro").debug(
                "ensure_user_has_default_roles: role '%s' missing, skipping for %s",
                role, user_email,
            )
            continue
        user.append("roles", {"role": role})
        added = True
    if added:
        user.save(ignore_permissions=True)


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
