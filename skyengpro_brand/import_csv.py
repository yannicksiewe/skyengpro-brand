"""
SkyEngPro Platform — CSV Import for Companies & Users

Reads CSV files and creates companies, users, employees, and permissions.
Idempotent: skips existing records, safe to run multiple times.

Usage:
    # From bench console or Python script:
    from skyengpro_brand.import_csv import import_companies, import_users

    # Import companies from CSV
    import_companies("/path/to/companies.csv")

    # Import users from CSV
    import_users("/path/to/users.csv")

    # Or import both at once
    from skyengpro_brand.import_csv import import_all
    import_all("/path/to/companies.csv", "/path/to/users.csv")

CSV Formats:
    See templates/ folder for example CSVs with all columns.
"""
import csv
import frappe
from skyengpro_brand.onboarding import (
    add_company,
    add_user,
    add_employee,
    setup_company_letterhead,
)
from skyengpro_brand.setup_roles import sync_user_module_profile


def import_companies(csv_path):
    """Import companies from a CSV file.

    CSV columns:
        company_name     (required) — display name
        abbreviation     (required) — 3-4 letter code
        country_template (required) — key from config.COMPANY_DEFAULTS
        parent_company   (optional) — parent company name for EoR partners
        letterhead_image (optional) — path to letterhead image
        company_logo     (optional) — path to company logo

    Example:
        company_name,abbreviation,country_template,parent_company,letterhead_image,company_logo
        ALI Capital,ALI,cameroon,,/files/ALI_Capital_Letterhead.png,/files/ALI_Capital_Logo.png
    """
    rows = _read_csv(csv_path)
    created = 0
    skipped = 0

    for row in rows:
        name = row.get("company_name", "").strip()
        if not name:
            continue

        abbr = row.get("abbreviation", "").strip()
        template = row.get("country_template", "cameroon").strip()
        parent = row.get("parent_company", "").strip() or None
        lh_image = row.get("letterhead_image", "").strip() or None
        logo = row.get("company_logo", "").strip() or None

        if frappe.db.exists("Company", name):
            print("  SKIP (exists): " + name)
            skipped += 1
        else:
            add_company(name, abbr, country_template=template, parent_company=parent)
            print("  CREATED: " + name)
            created += 1

        # Set letterhead if provided
        if lh_image:
            setup_company_letterhead(name, lh_image, company_logo=logo)

    frappe.db.commit()
    print("\nCompanies: " + str(created) + " created, " + str(skipped) + " skipped")
    return {"created": created, "skipped": skipped}


def import_users(csv_path):
    """Import users from a CSV file.

    CSV columns:
        email            (required) — login email
        first_name       (required) — first name
        last_name        (required) — last name
        profile          (required) — profile name from config.PROFILES
        company          (required) — company to restrict to
        password         (optional) — initial password
        designation      (optional) — job title
        gender           (optional) — Male/Female/Other (default: Male)
        date_of_birth    (optional) — YYYY-MM-DD (default: 1990-01-01)
        date_of_joining  (optional) — YYYY-MM-DD (default: today)

    Example:
        email,first_name,last_name,profile,company,password,designation
        john@acme.com,John,Doe,Company Admin,Acme Corp,Secure@2026,CEO
    """
    rows = _read_csv(csv_path)
    created_users = 0
    created_employees = 0
    skipped = 0

    for row in rows:
        email = row.get("email", "").strip()
        if not email:
            continue

        first = row.get("first_name", "").strip()
        last = row.get("last_name", "").strip()
        profile = row.get("profile", "").strip()
        company = row.get("company", "").strip()
        password = row.get("password", "").strip() or None
        designation = row.get("designation", "").strip() or None
        gender = row.get("gender", "Male").strip() or "Male"
        dob = row.get("date_of_birth", "1990-01-01").strip() or "1990-01-01"
        doj = row.get("date_of_joining", "").strip() or None

        # Create user
        if frappe.db.exists("User", email):
            print("  SKIP user (exists): " + email)
            skipped += 1
        else:
            add_user(
                email=email,
                first_name=first,
                last_name=last,
                profile=profile,
                company=company if company else None,
                password=password,
            )
            print("  CREATED user: " + email + " (" + profile + ")")
            created_users += 1

        # Create employee
        if not frappe.db.exists("Employee", {"user_id": email}):
            if company:
                add_employee(
                    email=email,
                    company=company,
                    designation=designation,
                    gender=gender,
                    date_of_birth=dob,
                    date_of_joining=doj,
                )
                print("  CREATED employee: " + email + " in " + company)
                created_employees += 1
        else:
            print("  SKIP employee (exists): " + email)

    frappe.db.commit()
    print("\nUsers: " + str(created_users) + " created, " + str(skipped) + " skipped")
    print("Employees: " + str(created_employees) + " created")
    return {
        "users_created": created_users,
        "employees_created": created_employees,
        "skipped": skipped,
    }


def import_all(companies_csv_path, users_csv_path):
    """Import companies first, then users.

    Args:
        companies_csv_path: path to companies CSV
        users_csv_path: path to users CSV
    """
    print("=" * 50)
    print("IMPORTING COMPANIES")
    print("=" * 50)
    co_result = import_companies(companies_csv_path)

    print()
    print("=" * 50)
    print("IMPORTING USERS")
    print("=" * 50)
    user_result = import_users(users_csv_path)

    print()
    print("=" * 50)
    print("IMPORT COMPLETE")
    print("=" * 50)
    print("Companies: " + str(co_result["created"]) + " created")
    print("Users: " + str(user_result["users_created"]) + " created")
    print("Employees: " + str(user_result["employees_created"]) + " created")


def export_users(csv_path=None):
    """Export current users to CSV format.

    If csv_path is provided, writes to file. Otherwise prints to stdout.
    Useful for backing up or migrating user setup.
    """
    users = frappe.get_all(
        "User",
        filters={"enabled": 1, "user_type": "System User"},
        fields=["name", "first_name", "last_name", "module_profile"],
        order_by="name"
    )

    rows = []
    for u in users:
        if u.name in ("Administrator", "Guest"):
            continue

        # Get company
        perm = frappe.get_all(
            "User Permission",
            filters={"user": u.name, "allow": "Company"},
            fields=["for_value"],
            limit=1
        )
        company = perm[0].for_value if perm else ""

        # Get employee info
        emp = frappe.db.get_value(
            "Employee",
            {"user_id": u.name},
            ["designation", "gender", "date_of_birth", "date_of_joining"],
            as_dict=True
        )

        rows.append({
            "email": u.name,
            "first_name": u.first_name or "",
            "last_name": u.last_name or "",
            "profile": u.module_profile or "Platform Admin",
            "company": company,
            "password": "",  # never export passwords
            "designation": emp.designation if emp else "",
            "gender": emp.gender if emp else "",
            "date_of_birth": str(emp.date_of_birth) if emp and emp.date_of_birth else "",
            "date_of_joining": str(emp.date_of_joining) if emp and emp.date_of_joining else "",
        })

    if csv_path:
        _write_csv(csv_path, rows)
        print("Exported " + str(len(rows)) + " users to " + csv_path)
    else:
        # Print as CSV to stdout
        if rows:
            print(",".join(rows[0].keys()))
            for row in rows:
                print(",".join(str(v) for v in row.values()))

    return rows


# ─────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────

def _read_csv(path):
    """Read a CSV file and return list of dicts."""
    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def _write_csv(path, rows):
    """Write list of dicts to CSV."""
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
