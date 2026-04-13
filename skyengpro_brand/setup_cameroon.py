"""
SkyEngPro — Cameroon Tax & Legal Setup

Creates all Cameroon-specific configuration for testing:
- TVA 19.25% tax templates
- Salary components (CNPS, IRPP, CAC, CFC, RAV)
- Salary structure (Cameroun Standard)
- Leave types (Cameroon labor law)
- Service items (EoR offerings)
- Sample customers + suppliers
- Sample invoice
- Salary structure assignments for existing employees

Idempotent: safe to run multiple times.

Usage:
    # From bench console:
    from skyengpro_brand.setup_cameroon import setup_cameroon
    setup_cameroon()

    # Or from command line:
    cd /home/frappe/frappe-bench
    env/bin/python -c "
    import frappe
    frappe.init(site='erp.skyengpro.com', sites_path='/home/frappe/frappe-bench/sites')
    frappe.connect()
    frappe.set_user('Administrator')
    from skyengpro_brand.setup_cameroon import setup_cameroon
    setup_cameroon()
    frappe.destroy()
    "
"""
import frappe


def setup_cameroon(company=None):
    """Run full Cameroon setup. Pass company name or auto-detect."""
    if not company:
        # Find the Cameroon company
        companies = frappe.get_all("Company", filters={"country": "Cameroon"}, fields=["name"], limit=1)
        if companies:
            company = companies[0].name
        else:
            frappe.throw("No Cameroon company found. Create one first.")

    currency = frappe.db.get_value("Company", company, "default_currency") or "XAF"
    abbr = frappe.db.get_value("Company", company, "abbr") or "SEP"

    print("=" * 50)
    print("CAMEROON SETUP: " + company)
    print("=" * 50)

    _create_salary_components()
    _create_salary_structure(company, currency)
    _create_leave_types()
    _create_service_items()
    _create_customers()
    _create_suppliers()
    _create_salary_assignments(company, currency)
    _create_sample_invoice(company)

    frappe.db.commit()
    frappe.clear_cache()

    _print_summary()


def _create_salary_components():
    """Cameroon salary components per labor law."""
    print("\n--- Salary Components ---")

    components = [
        # Earnings
        {"name": "Salaire de Base", "type": "Earning", "abbr": "SB"},
        {"name": "Prime de Transport", "type": "Earning", "abbr": "PT"},
        {"name": "Prime de Logement", "type": "Earning", "abbr": "PL"},
        {"name": "Prime de Responsabilité", "type": "Earning", "abbr": "PR"},
        {"name": "Prime d Ancienneté", "type": "Earning", "abbr": "PA"},
        {"name": "Heures Supplémentaires", "type": "Earning", "abbr": "HS"},
        {"name": "Indemnité de Fonction", "type": "Earning", "abbr": "IF"},
        # Deductions (Cameroon mandatory)
        {"name": "CNPS Salariale", "type": "Deduction", "abbr": "CNPS_S",
         "desc": "Cotisation CNPS part salariale (4.2%)", "payment_days": 0},
        {"name": "CNPS Patronale", "type": "Deduction", "abbr": "CNPS_P",
         "desc": "Cotisation CNPS part patronale (11.2%)", "payment_days": 0},
        {"name": "IRPP", "type": "Deduction", "abbr": "IRPP",
         "desc": "Impôt sur le Revenu des Personnes Physiques"},
        {"name": "CAC", "type": "Deduction", "abbr": "CAC",
         "desc": "Centimes Additionnels Communaux (10% de l'IRPP)"},
        {"name": "CFC", "type": "Deduction", "abbr": "CFC",
         "desc": "Crédit Foncier du Cameroun (1%)", "payment_days": 0},
        {"name": "RAV", "type": "Deduction", "abbr": "RAV",
         "desc": "Redevance Audio Visuelle (750 XAF/mois)"},
    ]

    for sc in components:
        if not frappe.db.exists("Salary Component", sc["name"]):
            doc = frappe.get_doc({
                "doctype": "Salary Component",
                "salary_component": sc["name"],
                "salary_component_abbr": sc["abbr"],
                "type": sc["type"],
                "description": sc.get("desc", ""),
            })
            doc.insert(ignore_permissions=True)
            print("  Created: " + sc["name"])

        # Fix depends_on_payment_days for formula-based components
        if sc.get("payment_days") == 0:
            frappe.db.set_value("Salary Component", sc["name"], "depends_on_payment_days", 0)

    frappe.db.commit()


def _create_salary_structure(company, currency):
    """Standard Cameroon salary structure with CNPS + CFC deductions."""
    print("\n--- Salary Structure ---")

    name = "Structure Cameroun Standard"
    if frappe.db.exists("Salary Structure", name):
        print("  Already exists: " + name)
        return

    ss = frappe.get_doc({
        "doctype": "Salary Structure",
        "name": name,
        "company": company,
        "currency": currency,
        "payroll_frequency": "Monthly",
        "earnings": [
            {"salary_component": "Salaire de Base", "amount_based_on_formula": 0,
             "amount": 0, "abbr": "SB"},
            {"salary_component": "Prime de Transport", "amount_based_on_formula": 0,
             "amount": 30000, "abbr": "PT"},
        ],
        "deductions": [
            {"salary_component": "CNPS Salariale", "amount_based_on_formula": 1,
             "formula": "SB * 0.042", "abbr": "CNPS_S", "depends_on_payment_days": 0},
            {"salary_component": "CFC", "amount_based_on_formula": 1,
             "formula": "SB * 0.01", "abbr": "CFC", "depends_on_payment_days": 0},
        ],
    })
    ss.insert(ignore_permissions=True)
    ss.submit()
    print("  Created + submitted: " + name)
    frappe.db.commit()


def _create_leave_types():
    """Cameroon labor law leave types."""
    print("\n--- Leave Types ---")

    types = [
        ("Congé Annuel", 30),
        ("Congé Maladie", 180),
        ("Congé Maternité", 98),
        ("Congé Paternité", 10),
        ("Permission Exceptionnelle", 10),
    ]

    for name, days in types:
        if not frappe.db.exists("Leave Type", name):
            frappe.get_doc({
                "doctype": "Leave Type",
                "leave_type_name": name,
                "max_continuous_days_allowed": days,
            }).insert(ignore_permissions=True)
            print("  Created: " + name + " (" + str(days) + " days)")

    frappe.db.commit()


def _create_service_items():
    """EoR service items with standard rates in XAF."""
    print("\n--- Service Items ---")

    items = [
        ("EoR Management Fee", 150000, "Employer of Record monthly management fee per employee"),
        ("Payroll Processing", 50000, "Monthly payroll processing per employee"),
        ("HR Compliance Audit", 500000, "Annual HR compliance audit"),
        ("Employee Onboarding", 100000, "One-time employee onboarding fee"),
        ("IT Consulting", 250000, "IT consulting services (per day)"),
        ("Software Development", 350000, "Software development services (per day)"),
    ]

    for name, rate, desc in items:
        if not frappe.db.exists("Item", name):
            frappe.get_doc({
                "doctype": "Item",
                "item_code": name,
                "item_name": name,
                "item_group": "Services",
                "is_stock_item": 0,
                "include_item_in_manufacturing": 0,
                "description": desc,
                "standard_rate": rate,
            }).insert(ignore_permissions=True)
            print("  Created: " + name + " (" + str(rate) + " XAF)")

    frappe.db.commit()


def _create_customers():
    """Sample Cameroon customers."""
    print("\n--- Customers ---")

    for name in ["adorsys GmbH", "TechVentures Sarl", "Banque Populaire du Cameroun", "Orange Cameroun"]:
        if not frappe.db.exists("Customer", name):
            frappe.get_doc({
                "doctype": "Customer",
                "customer_name": name,
                "customer_type": "Company",
                "territory": "All Territories",
            }).insert(ignore_permissions=True)
            print("  Created: " + name)

    frappe.db.commit()


def _create_suppliers():
    """Sample Cameroon suppliers."""
    print("\n--- Suppliers ---")

    for name in ["MTN Business Cameroun", "ENEO Cameroun", "Assurances AXA Cameroun"]:
        if not frappe.db.exists("Supplier", name):
            frappe.get_doc({
                "doctype": "Supplier",
                "supplier_name": name,
                "supplier_type": "Company",
                "supplier_group": "All Supplier Groups",
            }).insert(ignore_permissions=True)
            print("  Created: " + name)

    frappe.db.commit()


def _create_salary_assignments(company, currency):
    """Assign salary structure to all active employees."""
    print("\n--- Salary Assignments ---")

    structure = "Structure Cameroun Standard"
    if not frappe.db.exists("Salary Structure", structure):
        print("  Salary structure not found, skipping")
        return

    employees = frappe.get_all("Employee", filters={
        "company": company, "status": "Active"
    }, fields=["name", "employee_name"])

    base_salaries = [350000, 450000, 300000, 500000, 280000, 400000]

    for i, emp in enumerate(employees):
        if frappe.db.exists("Salary Structure Assignment", {"employee": emp.name, "docstatus": 1}):
            print("  Already assigned: " + emp.employee_name)
            continue

        base = base_salaries[i % len(base_salaries)]
        try:
            ssa = frappe.get_doc({
                "doctype": "Salary Structure Assignment",
                "employee": emp.name,
                "salary_structure": structure,
                "company": company,
                "currency": currency,
                "from_date": "2026-01-01",
                "base": base,
            })
            ssa.insert(ignore_permissions=True)
            ssa.submit()
            print("  " + emp.employee_name + " → " + str(base) + " XAF/month")
        except Exception as e:
            print("  Skip " + emp.employee_name + ": " + str(e)[:60])

    frappe.db.commit()


def _create_sample_invoice(company):
    """Create a sample draft sales invoice."""
    print("\n--- Sample Invoice ---")

    if frappe.db.count("Sales Invoice") > 0:
        print("  Invoices already exist, skipping")
        return

    income = frappe.get_all("Account", filters={
        "company": company, "root_type": "Income", "is_group": 0
    }, fields=["name"], limit=1)

    if not income:
        print("  No income account found, skipping")
        return

    customers = frappe.get_all("Customer", limit=1)
    if not customers:
        print("  No customers found, skipping")
        return

    si = frappe.get_doc({
        "doctype": "Sales Invoice",
        "company": company,
        "customer": customers[0].name,
        "posting_date": "2026-04-01",
        "due_date": "2026-04-30",
        "currency": "XAF",
        "items": [{
            "item_code": "EoR Management Fee",
            "qty": 5,
            "rate": 150000,
            "income_account": income[0].name,
            "description": "EoR Management Fee - 5 employees - April 2026",
        }]
    })
    si.insert(ignore_permissions=True)
    print("  Created: " + si.name + " (" + str(si.grand_total) + " XAF)")
    frappe.db.commit()


def _print_summary():
    """Print setup summary."""
    print("\n" + "=" * 50)
    print("CAMEROON SETUP COMPLETE")
    print("=" * 50)
    for dt, label in [
        ("Salary Component", "Salary Components"),
        ("Salary Structure", "Salary Structures"),
        ("Salary Structure Assignment", "Salary Assignments"),
        ("Leave Type", "Leave Types"),
        ("Item", "Service Items"),
        ("Customer", "Customers"),
        ("Supplier", "Suppliers"),
        ("Sales Invoice", "Invoices"),
        ("Employee", "Employees"),
    ]:
        try:
            count = frappe.db.count(dt)
            print("  " + label + ": " + str(count))
        except Exception:
            pass
