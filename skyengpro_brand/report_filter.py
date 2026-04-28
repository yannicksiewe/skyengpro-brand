"""
Per-tenant filter for Frappe Script Reports.

Wraps `frappe.desk.query_report.run` so a non-admin user cannot run a
report for a Company they don't belong to. Without this wrapper, anyone
with access to a financial report (Cash Flow, P&L, Balance Sheet, GL,
Trial Balance, etc.) could pass `?company=<other-tenant>` in the URL
and read another tenant's books — Frappe doesn't enforce per-user
company access on report execution.

Two-layer defence:
  1. Hard-override the `company` filter to the user's resolved tenant
     before the report runs. Even if the URL says
     `?company=Sky+Engineering+Professional`, a Clemios user gets
     `Clemios Sarl` substituted in.
  2. Post-filter rows for Script Reports whose ref_doctype carries a
     company column — defends against reports that ignore the filter.

Bypass is limited to `Administrator` (matches tenant_scope's policy —
System Manager users are still scoped to their tenant).

Wired via hooks.py:
    override_whitelisted_methods = {
        "frappe.desk.query_report.run": "skyengpro_brand.report_filter.run"
    }
"""
import json

import frappe
from frappe.desk.query_report import run as original_run

from skyengpro_brand.tenant_scope import get_user_company


@frappe.whitelist()
def run(report_name, filters=None, user=None, ignore_prepared_report=False,
        custom_columns=None, is_custom_report=False):
    if isinstance(filters, str):
        filters = json.loads(filters)
    filters = filters or {}

    # Bypass for Administrator + System Manager — same policy as
    # tenant_scope.get_user_company. Platform admins need cross-tenant
    # report access to manage the site.
    if frappe.session.user == "Administrator" or "System Manager" in (frappe.get_roles() or []):
        return original_run(
            report_name, filters=filters, user=user,
            ignore_prepared_report=ignore_prepared_report,
            custom_columns=custom_columns, is_custom_report=is_custom_report,
        )

    user_company = get_user_company()

    # If the user can't be tied to a tenant we don't know what to scope to.
    # Falling through to original_run would leak; safer to refuse.
    if not user_company:
        frappe.throw(
            "Cannot determine your Company — link your User to an Employee "
            "or set a Company User Permission, then try again.",
            title="Tenant scope: no company resolved",
        )

    # Layer 1: hard-override the company filter. We do this BEFORE running
    # the report so the SQL that the report builds sees only this user's
    # tenant. Even if the URL passed a different company name, we replace
    # it — there's no legitimate reason for a Clemios user to query a
    # SkyEngPro report.
    if filters.get("company") and filters["company"] != user_company:
        frappe.logger("skyengpro").warning(
            "report_filter: rewrote company filter for user %s on report %s "
            "(requested=%s, forced=%s)",
            frappe.session.user, report_name,
            filters["company"], user_company,
        )
    filters["company"] = user_company

    result = original_run(
        report_name, filters=filters, user=user,
        ignore_prepared_report=ignore_prepared_report,
        custom_columns=custom_columns, is_custom_report=is_custom_report,
    )

    # Layer 2: post-filter rows for Script Reports whose ref doctype has
    # a `company` column. This catches reports that don't pipe the company
    # filter into their SQL.
    try:
        report_doc = frappe.get_doc("Report", report_name)
    except Exception:
        return result

    if report_doc.report_type == "Script Report" and result and result.get("result"):
        result["result"] = _filter_rows_by_company(
            result["result"], report_doc.ref_doctype, user_company
        )

    return result


def _filter_rows_by_company(rows, ref_doctype, user_company):
    """Drop rows whose ref-doctype record belongs to a different company.

    Only applies when the ref doctype has a `company` field. For reports
    that don't reference a single doctype (or whose ref doctype has no
    company), rows pass through unchanged — those reports must be
    audited individually.
    """
    if not rows or not ref_doctype:
        return rows

    try:
        meta = frappe.get_meta(ref_doctype)
    except Exception:
        return rows
    if not any(f.fieldname == "company" for f in meta.fields):
        return rows

    allowed = set()
    for r in frappe.get_all(
        ref_doctype, filters={"company": user_company},
        fields=["name"], limit_page_length=0, ignore_permissions=True,
    ):
        allowed.add(r.name)

    # Untagged ref-records are treated as global and pass through. This
    # matches tenant_scope's allow-NULL-as-global behaviour for shared
    # masters; locking them out here would over-filter common reports.
    for r in frappe.get_all(
        ref_doctype, filters={"company": ["in", ["", None]]},
        fields=["name"], limit_page_length=0, ignore_permissions=True,
    ):
        allowed.add(r.name)

    out = []
    for row in rows:
        if isinstance(row, dict):
            n = row.get("name", "")
            if not n or n in allowed:
                out.append(row)
        elif isinstance(row, (list, tuple)) and row:
            n = row[0]
            if not n or n in allowed:
                out.append(row)
        else:
            # Unknown row shape — pass through rather than drop.
            out.append(row)
    return out
