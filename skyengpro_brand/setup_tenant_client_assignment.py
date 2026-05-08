"""Tenant-scoping via `client_assignment` — EoR-aware visibility.

Why this exists
───────────────
Sky Engineering Professional (SEP) acts as Employer-of-Record (EoR) for
adorsys: the 24 adorsys-team developers are EMPLOYED BY SEP (so SEP
handles Cameroon CNPS / IRPP / contracts) but BILLED TO adorsys (their
work and salary cost is recharged through a monthly EoR invoice).

In ERPNext terms:
  - Employee.company             = "Sky Engineering Professional"  (legal employer)
  - Employee.client_assignment   = "adorsys"                       (billed-to tenant)

That breaks the standard User Permission filter for an HR Manager on
the adorsys side (e.g. Lauson). She has UP `Company=adorsys`; ERPNext
filters Employee by `company IN [adorsys]`; the 24 employees now have
`company=SEP`, so she sees zero rows.

Fix — three pieces, all in this module
──────────────────────────────────────
  1. Add a Custom Field `client_assignment` (Link → Company) to:
       Salary Slip, Salary Structure Assignment,
       Leave Application, Attendance.
     Each fetches `client_assignment` from the linked Employee
     (`fetch_from = "employee.client_assignment"`), so a slip generated
     from HR-EMP-00006 picks up `client_assignment=adorsys` automatically.

     Employee already has `client_assignment` from `tenant_setup.py`'s
     EoR setup — we don't recreate it here.

  2. Property Setter `ignore_user_permissions=1` on the `company` field
     of all five doctypes (Employee + the four above).

     With strict UP enabled (System Settings.apply_strict_user_permissions),
     Frappe filters EVERY Company-Link field against the user's Company
     UPs and AND-merges the conditions. Marking `company` as
     ignore_user_permissions=1 removes it from that filter; the only
     remaining Company-link field that gets filtered is
     `client_assignment`. Effective behavior:

         user UP: Company=adorsys
         filter:  client_assignment IN [adorsys]
         matches: HR-EMP-00006 (client_assignment=adorsys, company=SEP) ✓

  3. Backfill `client_assignment` on existing Salary Slip / SSA /
     Leave Application / Attendance rows by joining to Employee.
     New rows are tagged automatically via `fetch_from`.

The combined effect:
  - adorsys-side users see ONLY their 24 client-assigned employees
  - SEP-internal users see their 9 SEP-tagged employees
  - Multi-tenant operators (e.g. Branda with UP for adorsys + SEP)
    see all 33

No subqueries, no permission_query_conditions hooks needed — native
ERPNext UP filtering does the work once `company` is masked and
`client_assignment` is the visible Company-link field.

Idempotent. Safe to re-run on every migrate.
"""
import frappe


# Doctypes whose `company` field gets masked from UP filtering, and
# (except Employee) where we add a `client_assignment` Custom Field.
# Employee already has `client_assignment` via tenant_setup.ensure_eor_setup().
_DERIVED_DOCTYPES = [
    "Salary Slip",
    "Salary Structure Assignment",
    "Leave Application",
    "Attendance",
]
_ALL_DOCTYPES = ["Employee"] + _DERIVED_DOCTYPES


def setup_tenant_client_assignment():
    """Main entry — wired into install.after_install. Idempotent."""
    _ensure_client_assignment_field()
    _ensure_company_ignore_user_permissions()
    _backfill_client_assignment()
    frappe.db.commit()


def _ensure_client_assignment_field():
    """Add `client_assignment` Custom Field on the four derivative
    doctypes. Each field fetches from the linked Employee on insert."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field

    for dt in _DERIVED_DOCTYPES:
        if not frappe.db.exists("DocType", dt):
            continue
        if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": "client_assignment"}):
            continue

        meta = frappe.get_meta(dt)
        # Place the field after `company` (preferred) or after `employee`
        # (every derived doctype has at least one of those).
        insert_after = "company" if meta.get_field("company") else "employee"
        try:
            create_custom_field(dt, {
                "fieldname":     "client_assignment",
                "label":         "Client Assignment",
                "fieldtype":     "Link",
                "options":       "Company",
                "insert_after":  insert_after,
                "in_standard_filter": 1,
                # Auto-fill from Employee — keeps the field truthful
                # without a doc_event hook. ERPNext's standard
                # field-fetcher applies on insert and on employee
                # change.
                "fetch_from":    "employee.client_assignment",
                "read_only":     1,
                "description":   (
                    "Client tenant this row is billed to. Auto-fetched "
                    "from Employee.client_assignment. Drives tenant "
                    "scoping when the Employee's legal employer "
                    "(company) differs from the client they work for."
                ),
            })
            frappe.logger("skyengpro").info(
                "client_assignment Custom Field created on %s", dt
            )
        except Exception:
            frappe.logger("skyengpro").exception(
                "client_assignment Custom Field failed on %s", dt
            )


def _ensure_company_ignore_user_permissions():
    """Property Setter: mark `company` as ignore_user_permissions=1 on
    Employee + the four derivative doctypes. This is what lets a
    user with `Company=adorsys` UP see an Employee whose company=SEP
    but client_assignment=adorsys."""
    for dt in _ALL_DOCTYPES:
        if not frappe.db.exists("DocType", dt):
            continue
        if not frappe.get_meta(dt).get_field("company"):
            continue

        existing = frappe.db.exists("Property Setter", {
            "doc_type":   dt,
            "field_name": "company",
            "property":   "ignore_user_permissions",
        })
        if existing:
            # Re-affirm the value if someone toggled it off in the UI.
            frappe.db.set_value(
                "Property Setter", existing, "value", "1",
                update_modified=False,
            )
            continue
        try:
            ps = frappe.new_doc("Property Setter")
            ps.doctype_or_field = "DocField"
            ps.doc_type         = dt
            ps.field_name       = "company"
            ps.property         = "ignore_user_permissions"
            ps.property_type    = "Check"
            ps.value            = "1"
            ps.insert(ignore_permissions=True)
            frappe.logger("skyengpro").info(
                "ignore_user_permissions=1 set on %s.company", dt
            )
        except Exception:
            frappe.logger("skyengpro").exception(
                "ignore_user_permissions Property Setter failed on %s.company",
                dt,
            )


def _backfill_client_assignment():
    """Tag existing rows on the four derivative doctypes by joining
    to Employee. New rows are filled via `fetch_from`."""
    for dt in _DERIVED_DOCTYPES:
        if not frappe.db.exists("DocType", dt):
            continue
        if not frappe.get_meta(dt).get_field("client_assignment"):
            continue
        try:
            frappe.db.sql(f"""
                UPDATE `tab{dt}` t
                JOIN `tabEmployee` e ON e.name = t.employee
                SET t.client_assignment = e.client_assignment
                WHERE (t.client_assignment IS NULL OR t.client_assignment = '')
                  AND e.client_assignment IS NOT NULL
            """)
        except Exception:
            frappe.logger("skyengpro").exception(
                "client_assignment backfill failed on %s", dt
            )
