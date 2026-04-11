"""
SkyEngPro Platform — Bench CLI Commands

Usage (from bench console or bench execute):

    # Full platform setup (run once after install)
    bench --site <site> execute skyengpro_brand.commands.setup_platform

    # Add a standalone company (ALI Capital, MC Capital style)
    bench --site <site> execute skyengpro_brand.commands.add_standalone_company \
        --kwargs '{"company_name":"ALI Capital","abbreviation":"ALI","country_template":"cameroon"}'

    # Add an EoR partner under SkyEngPro
    bench --site <site> execute skyengpro_brand.commands.add_eor_partner \
        --kwargs '{"company_name":"adorsys Ireland","abbreviation":"ADO","country_template":"ireland","parent_company":"SkyEngPro Sarl","hr_email":"hr@adorsys.com","hr_first":"John","hr_last":"Doe","hr_password":"Secure@2026"}'

    # Add a user to any company
    bench --site <site> execute skyengpro_brand.commands.add_company_user \
        --kwargs '{"email":"john@ali.com","first_name":"John","last_name":"Doe","profile":"Company Admin","company":"ALI Capital","password":"Pass@2026"}'

    # Add an employee
    bench --site <site> execute skyengpro_brand.commands.add_company_employee \
        --kwargs '{"email":"john@ali.com","company":"ALI Capital","designation":"CEO"}'

    # Show current setup summary
    bench --site <site> execute skyengpro_brand.commands.show_summary
"""
import frappe
from skyengpro_brand.onboarding import (
    add_company, add_user, add_employee,
    onboard_partner, onboard_employee,
    add_user_company_access,
)
from skyengpro_brand.setup_roles import setup_module_profiles, sync_all_users_profiles
from skyengpro_brand.setup_permissions import setup_all_permissions


def setup_platform():
    """Run full platform setup: profiles + permissions + workspace restrictions.

    Safe to run multiple times. Does NOT create companies or users.
    """
    print("Setting up Module Profiles...")
    setup_module_profiles()

    print("Setting up desk & workspace permissions...")
    setup_all_permissions()

    print("Syncing user module profiles...")
    sync_all_users_profiles()

    frappe.db.commit()
    print("Platform setup complete.")


def add_standalone_company(company_name, abbreviation, country_template="cameroon"):
    """Create a standalone company (no parent, fully independent)."""
    company = add_company(company_name, abbreviation, country_template=country_template)
    print("Company created: " + company.name)
    return company.name


def add_eor_partner(company_name, abbreviation, country_template,
                    parent_company, hr_email, hr_first, hr_last,
                    hr_password=None, shared_crm=False, shared_support=False):
    """Onboard a complete EoR partner: company + HR Manager + employee record."""
    result = onboard_partner(
        company_name=company_name,
        abbreviation=abbreviation,
        country_template=country_template,
        parent_company=parent_company,
        hr_manager_email=hr_email,
        hr_manager_first=hr_first,
        hr_manager_last=hr_last,
        hr_manager_password=hr_password,
        enable_shared_crm=shared_crm,
        enable_shared_support=shared_support,
    )
    print("Partner onboarded: " + company_name)
    print("  HR Manager: " + hr_email)
    return result


def add_company_user(email, first_name, last_name, profile, company=None,
                     password=None):
    """Add a user with a profile, optionally restricted to a company."""
    user = add_user(
        email=email,
        first_name=first_name,
        last_name=last_name,
        profile=profile,
        company=company,
        password=password,
    )
    print("User created: " + email + " (profile: " + profile + ")")
    return user.name


def add_company_employee(email, company, designation=None):
    """Create an Employee record for an existing user."""
    emp = add_employee(email=email, company=company, designation=designation)
    print("Employee created: " + email + " in " + company)
    return emp.name


def grant_company_access(email, company):
    """Give a user access to an additional company (for cross-company staff)."""
    add_user_company_access(email, company)
    print("Granted " + email + " access to " + company)


def show_summary():
    """Print a summary of the current platform setup."""
    print("\n" + "=" * 60)
    print("SKYENGPRO PLATFORM SUMMARY")
    print("=" * 60)

    # Companies
    companies = frappe.get_all(
        "Company",
        fields=["name", "parent_company", "country", "default_currency", "is_group"],
        order_by="name"
    )
    print("\nCOMPANIES (" + str(len(companies)) + "):")
    for c in companies:
        parent = " (child of " + c.parent_company + ")" if c.parent_company else ""
        group = " [GROUP]" if c.is_group else ""
        print("  " + c.name + " — " + c.country + " / " + c.default_currency + parent + group)

    # Module Profiles
    profiles = frappe.get_all("Module Profile", fields=["name"])
    print("\nMODULE PROFILES (" + str(len(profiles)) + "):")
    for p in profiles:
        count = frappe.db.count("Block Module", {"parent": p.name, "parenttype": "Module Profile"})
        users = frappe.db.count("User", {"module_profile": p.name, "enabled": 1})
        print("  " + p.name + " — " + str(count) + " blocked modules, " + str(users) + " users")

    # Users by profile
    print("\nUSERS:")
    users = frappe.get_all(
        "User",
        filters={"enabled": 1, "user_type": "System User"},
        fields=["name", "full_name", "module_profile"],
        order_by="name"
    )
    for u in users:
        if u.name in ("Administrator", "Guest"):
            continue
        profile = u.module_profile or "Platform Admin (no profile)"
        # Get company restrictions
        perms = frappe.get_all(
            "User Permission",
            filters={"user": u.name, "allow": "Company"},
            fields=["for_value"]
        )
        companies_str = ", ".join(p.for_value for p in perms) if perms else "ALL"
        print("  " + u.name + " — " + profile + " — companies: " + companies_str)

    # Workspace restrictions
    restricted = frappe.db.sql(
        """SELECT DISTINCT parent FROM `tabHas Role`
           WHERE parenttype='Workspace'""",
        as_dict=True
    )
    print("\nWORKSPACE RESTRICTIONS: " + str(len(restricted)) + " workspaces have role filters")

    # Employee count by company
    print("\nEMPLOYEES:")
    for c in companies:
        count = frappe.db.count("Employee", {"company": c.name, "status": "Active"})
        if count:
            print("  " + c.name + ": " + str(count) + " active")

    print("\n" + "=" * 60)
