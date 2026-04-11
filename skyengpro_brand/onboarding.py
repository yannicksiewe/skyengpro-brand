"""
SkyEngPro Platform — Company & User Onboarding

Reusable functions for:
- Creating companies (standalone or EoR partner)
- Creating users with proper roles and module profiles
- Setting data isolation (User Permissions)
- Creating employee records

Usage:
    from skyengpro_brand.onboarding import add_company, add_user, add_employee

    # Add a standalone company (like ALI Capital)
    add_company("ALI Capital", "ALI", country_template="cameroon")

    # Add an EoR partner under SkyEngPro
    add_company("adorsys Ireland", "ADO", country_template="ireland",
                parent_company="SkyEngPro Sarl")

    # Add a user with a profile
    add_user(
        email="admin@alicapital.com",
        first_name="John",
        last_name="Doe",
        profile="Company Admin",
        company="ALI Capital",
        password="SecurePass@2026"
    )

    # Add an employee record linked to the user
    add_employee(
        email="admin@alicapital.com",
        company="ALI Capital",
        designation="Managing Director"
    )
"""
import frappe
from skyengpro_brand.config import PROFILES, COMPANY_DEFAULTS
from skyengpro_brand.setup_roles import sync_user_module_profile


def add_company(company_name, abbreviation, country_template="cameroon",
                parent_company=None, is_group=False):
    """Create a company with country-appropriate defaults.

    Args:
        company_name: Display name (e.g. "ALI Capital")
        abbreviation: Short code (e.g. "ALI")
        country_template: Key from COMPANY_DEFAULTS ("cameroon", "ireland", "germany", "france")
        parent_company: Parent company name for EoR partners. None = standalone.
        is_group: True if this company will have children.

    Returns:
        The created Company doc, or existing if already exists.
    """
    if frappe.db.exists("Company", company_name):
        frappe.logger("skyengpro").info("Company '%s' already exists", company_name)
        return frappe.get_doc("Company", company_name)

    defaults = COMPANY_DEFAULTS.get(country_template, COMPANY_DEFAULTS["cameroon"])

    # If parent_company is set, ensure it's a group
    if parent_company and frappe.db.exists("Company", parent_company):
        parent = frappe.get_doc("Company", parent_company)
        if not parent.is_group:
            parent.is_group = 1
            parent.save(ignore_permissions=True)
            frappe.logger("skyengpro").info("Set '%s' as group company", parent_company)

    doc = frappe.get_doc({
        "doctype": "Company",
        "company_name": company_name,
        "abbr": abbreviation,
        "country": defaults["country"],
        "default_currency": defaults["currency"],
        "parent_company": parent_company or "",
        "is_group": int(is_group),
    })

    if defaults.get("chart_of_accounts"):
        doc.chart_of_accounts = defaults["chart_of_accounts"]

    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    frappe.logger("skyengpro").info(
        "Created company '%s' (%s, %s)%s",
        company_name, defaults["country"], defaults["currency"],
        " under " + parent_company if parent_company else " (standalone)"
    )
    return doc


def add_user(email, first_name, last_name, profile, company=None,
             password=None, send_welcome=False, extra_roles=None):
    """Create a user with the specified profile and company restriction.

    Args:
        email: User email (login)
        first_name: First name
        last_name: Last name
        profile: Profile name from config.PROFILES (e.g. "Company Admin", "Partner Employee")
                 Use "Platform Admin" for no restrictions (System Manager).
        company: Company name to restrict to. None = no restriction (sees all).
        password: Initial password. If None, user must reset via email.
        send_welcome: Send welcome email?
        extra_roles: Additional roles beyond what the profile defines.

    Returns:
        The created User doc, or existing if already exists.
    """
    if frappe.db.exists("User", email):
        frappe.logger("skyengpro").info("User '%s' already exists", email)
        return frappe.get_doc("User", email)

    # Platform Admin = System Manager, no module profile
    if profile == "Platform Admin":
        roles = [{"role": "System Manager"}, {"role": "Administrator"}]
        module_profile = None
    else:
        profile_config = PROFILES.get(profile)
        if not profile_config:
            frappe.throw("Profile '{}' not found in config.PROFILES".format(profile))
        roles = [{"role": r} for r in profile_config["roles"]]
        module_profile = profile

    if extra_roles:
        existing_role_names = {r["role"] for r in roles}
        for role in extra_roles:
            if role not in existing_role_names:
                roles.append({"role": role})

    user_data = {
        "doctype": "User",
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "enabled": 1,
        "send_welcome_email": int(send_welcome),
        "roles": roles,
    }

    if module_profile:
        user_data["module_profile"] = module_profile

    if password:
        user_data["new_password"] = password

    user = frappe.get_doc(user_data)
    user.insert(ignore_permissions=True)
    frappe.db.commit()

    # Sync module profile → user's block_modules
    if module_profile:
        sync_user_module_profile(email)

    # Set company restriction if specified
    if company:
        _set_company_permission(email, company)

    frappe.logger("skyengpro").info(
        "Created user '%s' with profile '%s'%s",
        email, profile,
        " restricted to " + company if company else " (no company restriction)"
    )
    return user


def add_user_company_access(email, company):
    """Grant a user access to an additional company.

    Use this for SkyEngPro staff who need to see EoR partner data.
    """
    _set_company_permission(email, company)
    frappe.logger("skyengpro").info(
        "Granted '%s' access to company '%s'", email, company
    )


def add_employee(email, company, designation=None, department=None,
                 date_of_birth="1990-01-01", date_of_joining=None,
                 gender="Male"):
    """Create an Employee record linked to a user and company.

    Args:
        email: User email (must exist as a User)
        company: Company name
        designation: Job title (e.g. "Software Engineer"). Created if doesn't exist.
        department: Department name. Optional.
        date_of_birth: DOB string (YYYY-MM-DD)
        date_of_joining: Joining date. Defaults to today.
        gender: "Male", "Female", or "Other"

    Returns:
        The created Employee doc, or existing if already exists.
    """
    if frappe.db.exists("Employee", {"user_id": email}):
        frappe.logger("skyengpro").info("Employee for '%s' already exists", email)
        return frappe.get_doc("Employee", {"user_id": email})

    if not frappe.db.exists("User", email):
        frappe.throw("User '{}' does not exist. Create the user first.".format(email))

    user = frappe.get_doc("User", email)

    # Create designation if it doesn't exist
    if designation and not frappe.db.exists("Designation", designation):
        frappe.get_doc({
            "doctype": "Designation",
            "designation_name": designation,
        }).insert(ignore_permissions=True)

    if not date_of_joining:
        date_of_joining = frappe.utils.today()

    emp = frappe.get_doc({
        "doctype": "Employee",
        "first_name": user.first_name,
        "last_name": user.last_name or "",
        "employee_name": user.full_name,
        "company": company,
        "status": "Active",
        "gender": gender,
        "date_of_birth": date_of_birth,
        "date_of_joining": date_of_joining,
        "user_id": email,
    })

    if designation:
        emp.designation = designation
    if department:
        emp.department = department

    emp.insert(ignore_permissions=True)
    frappe.db.commit()
    frappe.logger("skyengpro").info(
        "Created employee '%s' in company '%s'", user.full_name, company
    )
    return emp


def setup_company_letterhead(company_name, letterhead_image, company_logo=None):
    """Create a Letter Head for a company and set it as the company default.

    Args:
        company_name: Company name (used as Letter Head name too)
        letterhead_image: Path to letterhead image (e.g. "/files/ALI_Capital_Letterhead.png")
        company_logo: Path to company logo. Optional.
    """
    if not frappe.db.exists("Letter Head", company_name):
        frappe.get_doc({
            "doctype": "Letter Head",
            "letter_head_name": company_name,
            "source": "Image",
            "image": letterhead_image,
            "is_default": 0,
        }).insert(ignore_permissions=True)

    frappe.db.set_value("Company", company_name, "default_letter_head", company_name)

    if company_logo:
        frappe.db.set_value("Company", company_name, "company_logo", company_logo)

    frappe.db.commit()
    frappe.logger("skyengpro").info(
        "Letter Head set for '%s': %s", company_name, letterhead_image
    )


def remove_user(email):
    """Disable a user and remove their permissions.

    Does NOT delete — preserves audit trail (important for ISO 27001).
    """
    if not frappe.db.exists("User", email):
        return

    frappe.db.set_value("User", email, "enabled", 0)
    frappe.db.sql(
        "DELETE FROM `tabUser Permission` WHERE user=%s", email
    )
    frappe.db.commit()
    frappe.logger("skyengpro").info("Disabled user '%s' and removed permissions", email)


def onboard_partner(company_name, abbreviation, country_template,
                    parent_company, hr_manager_email, hr_manager_first,
                    hr_manager_last, hr_manager_password=None,
                    enable_shared_crm=False, enable_shared_support=False):
    """One-call onboarding for a new EoR partner company.

    Creates the company, HR Manager user, Employee record,
    and optionally enables CRM/Support sharing.

    Returns:
        dict with created objects
    """
    # 1. Create company
    company = add_company(
        company_name, abbreviation,
        country_template=country_template,
        parent_company=parent_company
    )

    # 2. Determine profile based on sharing
    if enable_shared_crm or enable_shared_support:
        profile = "Partner HR Manager"
    else:
        profile = "Partner HR Manager"

    # 3. Create HR Manager
    hr_roles = None
    if enable_shared_support:
        hr_roles = ["Support Team"]

    user = add_user(
        email=hr_manager_email,
        first_name=hr_manager_first,
        last_name=hr_manager_last,
        profile=profile,
        company=company_name,
        password=hr_manager_password,
        extra_roles=hr_roles,
    )

    # 4. Create Employee record
    employee = add_employee(
        email=hr_manager_email,
        company=company_name,
        designation="HR Manager",
    )

    frappe.logger("skyengpro").info(
        "Onboarded partner '%s' with HR Manager '%s'", company_name, hr_manager_email
    )

    return {
        "company": company,
        "user": user,
        "employee": employee,
    }


def onboard_employee(email, first_name, last_name, company,
                     profile="Employee Self Service Profile",
                     designation=None, password=None,
                     enable_support_tickets=False):
    """One-call onboarding for a new employee.

    Creates the user, sets permissions, creates Employee record.

    Returns:
        dict with created objects
    """
    extra_roles = []
    if enable_support_tickets:
        extra_roles.append("Support Team")

    user = add_user(
        email=email,
        first_name=first_name,
        last_name=last_name,
        profile=profile,
        company=company,
        password=password,
        extra_roles=extra_roles if extra_roles else None,
    )

    employee = add_employee(
        email=email,
        company=company,
        designation=designation,
    )

    return {
        "user": user,
        "employee": employee,
    }


# ─────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────

def _set_company_permission(email, company):
    """Add a User Permission restricting the user to a company + set default."""
    if not frappe.db.exists("User Permission", {
        "user": email, "allow": "Company", "for_value": company
    }):
        frappe.get_doc({
            "doctype": "User Permission",
            "user": email,
            "allow": "Company",
            "for_value": company,
            "apply_to_all_doctypes": 1,
        }).insert(ignore_permissions=True)

    # Set as the user's default company (avoids "Company is mandatory" errors)
    if not frappe.db.exists("DefaultValue", {
        "parent": email, "defkey": "company", "defvalue": company
    }):
        frappe.db.sql(
            """INSERT INTO tabDefaultValue
            (name, parent, parenttype, parentfield, defkey, defvalue,
             creation, modified, modified_by, owner, docstatus, idx)
            VALUES (%s, %s, 'User', 'defaults', 'company', %s,
                    NOW(), NOW(), 'Administrator', 'Administrator', 0, 0)""",
            (frappe.generate_hash(length=10), email, company)
        )

    frappe.db.commit()
