"""
SkyEngPro — Report Company Filter

Wraps frappe.desk.query_report.run to filter Script Report results
by the user's company. Prevents cross-company data leaks in Script
Reports that use raw SQL and don't respect User Permissions.

Two-phase approach:
1. Inject company into filters (for reports that support it)
2. Post-filter results by checking the ref_doctype's company field

Registered via hooks.py:
    override_whitelisted_methods = {
        "frappe.desk.query_report.run": "skyengpro_brand.report_filter.run"
    }
"""
import frappe
from frappe.desk.query_report import run as original_run


@frappe.whitelist()
def run(report_name, filters=None, user=None, ignore_prepared_report=False,
        custom_columns=None, is_custom_report=False):
    """Wrapper that filters report results by user's company."""

    if isinstance(filters, str):
        import json
        filters = json.loads(filters)

    if not filters:
        filters = {}

    # Admins see everything
    if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
        return original_run(
            report_name, filters=filters, user=user,
            ignore_prepared_report=ignore_prepared_report,
            custom_columns=custom_columns, is_custom_report=is_custom_report,
        )

    user_company = frappe.defaults.get_user_default("company")
    if not user_company:
        return original_run(
            report_name, filters=filters, user=user,
            ignore_prepared_report=ignore_prepared_report,
            custom_columns=custom_columns, is_custom_report=is_custom_report,
        )

    # Phase 1: inject company filter (works if report supports it)
    if "company" not in filters:
        filters["company"] = user_company

    # Run the report
    result = original_run(
        report_name, filters=filters, user=user,
        ignore_prepared_report=ignore_prepared_report,
        custom_columns=custom_columns, is_custom_report=is_custom_report,
    )

    # Phase 2: post-filter results for Script Reports
    report_doc = frappe.get_doc("Report", report_name)
    if report_doc.report_type == "Script Report" and result.get("result"):
        result["result"] = _filter_results(
            result["result"],
            report_doc.ref_doctype,
            user_company,
        )

    return result


def _filter_results(rows, ref_doctype, user_company):
    """Filter report result rows to only include the user's company data."""
    if not rows or not ref_doctype:
        return rows

    # Check if the ref doctype has a company field
    meta = frappe.get_meta(ref_doctype)
    has_company = any(f.fieldname == "company" for f in meta.fields)
    if not has_company:
        return rows

    # Get the names of all records belonging to the user's company
    allowed_names = set()
    all_records = frappe.get_all(
        ref_doctype,
        filters={"company": user_company},
        fields=["name"],
        limit_page_length=0,
        ignore_permissions=True,
    )
    allowed_names = {r.name for r in all_records}

    # Also allow records with empty company (shared/unassigned)
    empty_company = frappe.get_all(
        ref_doctype,
        filters={"company": ["in", ["", None]]},
        fields=["name"],
        limit_page_length=0,
        ignore_permissions=True,
    )
    allowed_names.update(r.name for r in empty_company)

    # Filter rows — check 'name' field in each row
    filtered = []
    for row in rows:
        if isinstance(row, dict):
            row_name = row.get("name", "")
            if row_name in allowed_names or not row_name:
                filtered.append(row)
        elif isinstance(row, (list, tuple)):
            # Some reports return lists instead of dicts
            # First column is usually the name/ID
            if rows and len(row) > 0 and row[0] in allowed_names:
                filtered.append(row)
            elif not row[0]:
                filtered.append(row)

    return filtered
