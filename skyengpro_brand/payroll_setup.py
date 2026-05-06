"""Payroll wiring — make sure every Company has its
default_payroll_payable_account set, and that every existing
Salary Structure Assignment carries the same value.

Why this module exists
──────────────────────
Payroll Entry → Get Employees joins
  Salary Structure Assignment.payroll_payable_account
against
  Payroll Entry.payroll_payable_account
A silent NULL on either side drops the employee from the dialog —
HR can't add them to the bulk slip run, and there's no error to
diagnose from. Symptom: "I have 9 active employees but Get
Employees only returns 2."

The ERPNext SSA controller does NOT auto-default this field from
Company. So an SSA created via the form before HR populates
Company.default_payroll_payable_account ends up with PPA=NULL and
silently breaks until somebody notices the missing employees.

This module adds three layers of defense:

  1. set_company_payroll_payable_defaults() — populates
     Company.default_payroll_payable_account from the static map
     in config.COMPANY_PAYROLL_PAYABLE_ACCOUNTS. Idempotent;
     never overwrites a value that's already set in the UI.

  2. backfill_ssa_payroll_payable_account() — for every submitted
     SSA with PPA=NULL, sets it from
     Company.default_payroll_payable_account. Uses
     frappe.db.set_value (the standard ERPNext pattern for
     backfilling missing-field values on submitted docs); adds an
     audit Comment on each touched row so the change is
     discoverable from the form's activity log.

  3. validate_ssa_set_default_ppa() — doc_event on Salary
     Structure Assignment.validate that fills PPA from the
     Company default if blank. Closes the on-create gap so we
     don't drift into the same hole again.

All three are idempotent and safe to run on every migrate.
"""
import frappe

from skyengpro_brand.config import COMPANY_PAYROLL_PAYABLE_ACCOUNTS


# ─────────────────────────────────────────────────────────────
# Layer 1: Company.default_payroll_payable_account
# ─────────────────────────────────────────────────────────────

def set_company_payroll_payable_defaults():
    """For each Company in COMPANY_PAYROLL_PAYABLE_ACCOUNTS, set
    its default_payroll_payable_account if blank. Skip if the
    target Account doesn't exist on this site (fresh install
    case) — the validate hook will pick it up next time."""
    for company, account in COMPANY_PAYROLL_PAYABLE_ACCOUNTS.items():
        if not frappe.db.exists("Company", company):
            continue
        if not frappe.db.exists("Account", {"name": account, "company": company}):
            frappe.logger("skyengpro").warning(
                "set_company_payroll_payable_defaults: account %s not found for company %s — skipping",
                account, company,
            )
            continue
        current = frappe.db.get_value(
            "Company", company, "default_payroll_payable_account"
        )
        if current:
            continue
        frappe.db.set_value(
            "Company", company,
            "default_payroll_payable_account", account,
            update_modified=False,
        )
        frappe.logger("skyengpro").info(
            "set_company_payroll_payable_defaults: %s -> %s", company, account,
        )


# ─────────────────────────────────────────────────────────────
# Layer 2: backfill SSA.payroll_payable_account
# ─────────────────────────────────────────────────────────────

def backfill_ssa_payroll_payable_account():
    """For every submitted SSA with payroll_payable_account=NULL,
    set it from Company.default_payroll_payable_account.

    Uses db.set_value (no cancel/amend) because:
      * payroll_payable_account is routing metadata, not a
        financial amount, so amending the doc to capture the
        change in the version chain would be ceremony with no
        analytical value.
      * Cancel/amend renames the SSA (HR-SSA-26-04-00009 →
        HR-SSA-26-04-00009-1), and any external reference to
        the old name (custom reports, exports) goes stale.
      * The ERPNext core pattern for backfilling missing
        field values added in a later release is direct SQL.

    Audit trail: each touched SSA gets a `Comment` row tagging
    the change to skyengpro_brand + the resolved account, so
    the activity log on the form makes the change visible.

    Idempotent: skips SSAs where PPA is already populated.
    """
    rows = frappe.db.sql(
        """
        SELECT ssa.name, ssa.employee, ssa.company
        FROM `tabSalary Structure Assignment` ssa
        WHERE ssa.docstatus = 1
          AND (ssa.payroll_payable_account IS NULL
               OR ssa.payroll_payable_account = '')
        """,
        as_dict=True,
    )
    if not rows:
        return

    # Cache Company → default PPA so we don't read the same row N times.
    company_default = {}
    touched = 0
    skipped_no_default = 0

    for r in rows:
        if r.company not in company_default:
            company_default[r.company] = frappe.db.get_value(
                "Company", r.company, "default_payroll_payable_account"
            )
        ppa = company_default[r.company]
        if not ppa:
            skipped_no_default += 1
            continue
        try:
            frappe.db.set_value(
                "Salary Structure Assignment", r.name,
                "payroll_payable_account", ppa,
                update_modified=True,
            )
            _add_backfill_comment(r.name, ppa)
            touched += 1
        except Exception:
            frappe.logger("skyengpro").exception(
                "backfill_ssa_payroll_payable_account: set_value failed for %s",
                r.name,
            )

    if touched:
        frappe.db.commit()
    frappe.logger("skyengpro").info(
        "backfill_ssa_payroll_payable_account: backfilled %d SSA(s), %d skipped (no Company default)",
        touched, skipped_no_default,
    )


def _add_backfill_comment(ssa_name: str, account: str):
    """Drop an Info Comment on the SSA so the change shows up in
    the form's activity log. Failure to write the comment is
    non-fatal — the data fix has already landed at this point."""
    try:
        frappe.get_doc({
            "doctype":         "Comment",
            "comment_type":    "Info",
            "reference_doctype": "Salary Structure Assignment",
            "reference_name":  ssa_name,
            "content": (
                f"skyengpro_brand: backfilled payroll_payable_account → "
                f"<b>{frappe.utils.escape_html(account)}</b> "
                f"(SSA was missing the field — Payroll Entry filtered the employee out)."
            ),
        }).insert(ignore_permissions=True)
    except Exception:
        frappe.logger("skyengpro").warning(
            "_add_backfill_comment: failed for %s", ssa_name,
        )


# ─────────────────────────────────────────────────────────────
# Layer 3: SSA validate hook — close the on-create gap
# ─────────────────────────────────────────────────────────────

def validate_ssa_set_default_ppa(doc, method=None):
    """Salary Structure Assignment.validate — if the user didn't
    set payroll_payable_account, fall back to
    Company.default_payroll_payable_account.

    Runs before the docstatus transition, so a freshly-submitted
    SSA picks the company default automatically and never lands
    in the NULL state that breaks Payroll Entry."""
    if doc.payroll_payable_account:
        return
    if not doc.company:
        return
    default = frappe.db.get_value(
        "Company", doc.company, "default_payroll_payable_account"
    )
    if not default:
        return
    doc.payroll_payable_account = default
