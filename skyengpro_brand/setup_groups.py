"""
SkyEngPro — Group (Role Profile) Setup

Defines groups as combinations of role sets.
Users are assigned to groups → get all roles from that group.

To change what a group can do: edit GROUPS dict below.
To add/remove users from groups: edit the CSV or use ERPNext UI → User → Role Profile.

Usage:
    from skyengpro_brand.setup_groups import setup_groups, assign_user_to_group
    setup_groups()  # creates all Role Profiles
    assign_user_to_group("john@example.com", "Finance + HR", ["Company A"])
"""
import frappe


# ─── Group definitions ───
# Each group = a set of Frappe roles
GROUPS = {
    "Finance": [
        "Accounts Manager",
        "Accounts User",
        "Expense Approver",
        "Sales User",
        "Sales Manager",
        "Purchase User",
        "Purchase Manager",
    ],
    "HR": [
        "HR Manager",
        "HR User",
        "Leave Approver",
        "Expense Approver",
        "Employee",
    ],
    "Management": [
        "System Manager",
    ],
}

# ─── Combined Role Profiles (groups users can belong to) ───
# Each profile = list of group names to merge
PROFILES = {
    "Finance + HR": ["Finance", "HR"],
    "Finance + HR + Management": ["Finance", "HR", "Management"],
    "HR Only": ["HR"],
    "Finance Only": ["Finance"],
}

# Base roles every user gets regardless of group
BASE_ROLES = ["Employee", "Projects User"]


def setup_groups():
    """Create or update all Role Profiles from GROUPS + PROFILES config."""
    for profile_name, group_names in PROFILES.items():
        roles = set(BASE_ROLES)
        for g in group_names:
            roles.update(GROUPS.get(g, []))

        if frappe.db.exists("Role Profile", profile_name):
            rp = frappe.get_doc("Role Profile", profile_name)
            rp.roles = []
            for r in sorted(roles):
                rp.append("roles", {"role": r})
            rp.save(ignore_permissions=True)
        else:
            rp = frappe.get_doc({
                "doctype": "Role Profile",
                "role_profile": profile_name,
                "roles": [{"role": r} for r in sorted(roles)],
            })
            rp.insert(ignore_permissions=True)

        frappe.logger("skyengpro").info(
            "Role Profile '%s': %d roles", profile_name, len(roles)
        )

    frappe.db.commit()


def assign_user_to_group(email, profile_name, companies=None):
    """Assign a user to a group (Role Profile) + set company access.

    Args:
        email: user email
        profile_name: name from PROFILES (e.g. "Finance + HR")
        companies: list of company names. None = no restriction (sees all).
                   Use pipe-separated string for CSV compat: "Company A|Company B"
    """
    if not frappe.db.exists("User", email):
        frappe.throw("User '{}' not found".format(email))

    if not frappe.db.exists("Role Profile", profile_name):
        frappe.throw("Role Profile '{}' not found. Run setup_groups() first.".format(profile_name))

    # Get roles from profile
    rp = frappe.get_doc("Role Profile", profile_name)
    roles = [{"role": r.role} for r in rp.roles]

    # Update user
    user = frappe.get_doc("User", email)
    user.roles = roles
    user.role_profile_name = profile_name
    user.save(ignore_permissions=True)

    # Handle companies
    if isinstance(companies, str):
        companies = [c.strip() for c in companies.split("|") if c.strip()]

    # Clear old company permissions
    frappe.db.sql(
        "DELETE FROM `tabUser Permission` WHERE user=%s AND allow='Company'", email
    )

    if companies:
        for company in companies:
            frappe.get_doc({
                "doctype": "User Permission",
                "user": email,
                "allow": "Company",
                "for_value": company,
                "apply_to_all_doctypes": 1,
            }).insert(ignore_permissions=True)
        frappe.defaults.set_user_default("company", companies[0], user=email)

    frappe.db.commit()
    frappe.logger("skyengpro").info(
        "User '%s' assigned to group '%s', companies: %s",
        email, profile_name, companies or "ALL"
    )


def remove_user_from_group(email):
    """Remove a user's group assignment (keeps the user, removes roles + permissions)."""
    if not frappe.db.exists("User", email):
        return

    user = frappe.get_doc("User", email)
    user.roles = [{"role": "Employee"}]  # minimum role
    user.role_profile_name = ""
    user.save(ignore_permissions=True)

    frappe.db.sql(
        "DELETE FROM `tabUser Permission` WHERE user=%s AND allow='Company'", email
    )
    frappe.db.commit()


def list_groups():
    """Print all groups and their members."""
    for profile_name in PROFILES:
        if not frappe.db.exists("Role Profile", profile_name):
            continue
        rp = frappe.get_doc("Role Profile", profile_name)
        roles = [r.role for r in rp.roles]
        users = frappe.get_all("User", filters={"role_profile_name": profile_name, "enabled": 1}, fields=["name", "full_name"])
        print(profile_name + " (" + str(len(roles)) + " roles):")
        for u in users:
            perms = frappe.get_all("User Permission", filters={"user": u.name, "allow": "Company"}, fields=["for_value"])
            co = ", ".join(p.for_value for p in perms) if perms else "ALL"
            print("  " + u.name + " (" + u.full_name + ") → " + co)
        if not users:
            print("  (no users)")
