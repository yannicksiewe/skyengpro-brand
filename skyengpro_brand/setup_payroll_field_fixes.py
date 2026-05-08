"""Property Setter overrides on Salary Structure Assignment + similar.

Why this exists
───────────────
Some field-level mandatories on `Salary Structure Assignment` block the
HRMS Bulk Assign UI from creating SSAs in batch. The blocking fields
exist for ERPNext-India workflows or rarely-used payroll features that
don't apply in our Cameroon EoR setup:

  - `income_tax_slab` — India progressive tax bracket reference. We use
    Cameroon IRPP (computed in Salary Structure formulas), not slabs.
  - `taxable_earnings_till_date` / `tax_deducted_till_date` — used by
    HRMS's investment-declaration / TDS feature. Not relevant in Cameroon.
  - `payroll_cost_centers` — child table HRMS expects when payroll
    cost-allocation is enabled. We allocate at JE level instead.

If these stay `reqd=1`, every Bulk Salary Structure Assignment fails
with `MandatoryError`. Concretely, Beltine hit this 2026-05-08 trying
to bulk-assign May 2026 SSAs for all 30 active employees.

Fix: idempotent Property Setter overrides making these fields optional.
Same pattern as setup_strict_up_exemptions.py.
"""
import frappe


_OPTIONAL_SSA_FIELDS = [
    "income_tax_slab",
    "taxable_earnings_till_date",
    "tax_deducted_till_date",
    "payroll_cost_centers",
    # `department` is also marked reqd=1 by a stray Property Setter on
    # this site, but legacy employees may lack a department assignment.
    # Making it optional lets Bulk Salary Structure Assignment succeed
    # for employees without a dept; ERPNext falls back to no-dept on
    # the SSA in that case (acceptable for our reporting).
    "department",
]


# Reports shipped by HRMS that target India-payroll-only concepts. They
# either error against our (non-IN) schema or return useless data; we
# disable them so they don't surface on the desk for our users.
#
# Concretely: as of HRMS v16.6.1, Professional Tax Deductions queries
# `tabSalary Component.component_type` which doesn't exist in this
# schema, leading to a 500 OperationalError when run.
_DISABLED_HRMS_REPORTS = [
    "Professional Tax Deductions",
    "Income Tax Deductions",
    "Provident Fund Deductions",
]


def ensure_india_reports_disabled():
    """Disable India-only HRMS reports that error or return nothing
    useful in our Cameroon site, AND scrub them from sidebars + role
    grants so they don't appear in the desk at all.

    `Report.disabled=1` blocks the report from running but doesn't hide
    it from the desk's report list / workspace sidebar — which is why
    users still see them and click through to the "Report X is
    disabled" message. To make them truly invisible, also:

      - Delete `tabHas Role` rows for the report (no role -> not in
        anyone's role-filtered listing).
      - Delete `tabWorkspace Link` and `tabWorkspace Shortcut` rows
        that reference the report (no workspace cards / sidebar entries).

    HRMS recreates the standard reports' Has Role + Workspace Link
    rows on every `bench migrate`, so this function MUST run on every
    after_install. Idempotent.
    """
    for r in _DISABLED_HRMS_REPORTS:
        if not frappe.db.exists("Report", r):
            continue
        cur = frappe.db.get_value("Report", r, "disabled")
        if not cur:
            frappe.db.set_value("Report", r, "disabled", 1, update_modified=False)
        # Strip role grants so the report disappears from role-filtered
        # listings (everywhere except for users with bypass).
        frappe.db.sql(
            "DELETE FROM `tabHas Role` WHERE parenttype='Report' AND parent=%s",
            (r,),
        )
        # Strip workspace links + shortcuts so the report doesn't show
        # up in any workspace's sidebar or shortcut card.
        frappe.db.sql(
            "DELETE FROM `tabWorkspace Link` "
            "WHERE link_type='Report' AND link_to=%s",
            (r,),
        )
        frappe.db.sql(
            "DELETE FROM `tabWorkspace Shortcut` "
            "WHERE type='Report' AND link_to=%s",
            (r,),
        )
        frappe.logger("skyengpro").info(
            "ensure_india_reports_disabled: disabled+scrubbed %s", r,
        )
    frappe.db.commit()


def ensure_ssa_optional_fields():
    """Set reqd=0 on the four SSA fields above. Idempotent."""
    DOCTYPE = "Salary Structure Assignment"
    for fname in _OPTIONAL_SSA_FIELDS:
        ps_name = f"{DOCTYPE}-{fname}-reqd"
        if frappe.db.exists("Property Setter", ps_name):
            cur = frappe.db.get_value("Property Setter", ps_name, "value")
            if cur != "0":
                frappe.db.set_value("Property Setter", ps_name, "value", "0", update_modified=False)
                frappe.logger("skyengpro").info(
                    "ensure_ssa_optional_fields: %s.reqd 1->0", fname,
                )
            continue
        try:
            ps = frappe.new_doc("Property Setter")
            ps.doctype_or_field = "DocField"
            ps.doc_type         = DOCTYPE
            ps.field_name       = fname
            ps.property         = "reqd"
            ps.property_type    = "Check"
            ps.value            = "0"
            ps.insert(ignore_permissions=True)
            frappe.logger("skyengpro").info(
                "ensure_ssa_optional_fields: created PS for %s.reqd=0", fname,
            )
        except Exception:
            frappe.logger("skyengpro").exception(
                "ensure_ssa_optional_fields: failed for %s", fname,
            )
    frappe.db.commit()
