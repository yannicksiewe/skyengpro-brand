"""
SkyEngPro — Report Company Filter

Wraps frappe.desk.query_report.run to inject the user's company
into Script Report filters. This prevents cross-company data leaks
in Script Reports that use raw SQL.

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
    """Wrapper around frappe.desk.query_report.run that injects company filter."""

    # Parse filters
    if isinstance(filters, str):
        import json
        filters = json.loads(filters)

    if not filters:
        filters = {}

    # If user has a company restriction and the filter doesn't already have company,
    # inject their default company
    if not frappe.session.user == "Administrator" and "System Manager" not in frappe.get_roles():
        user_company = frappe.defaults.get_user_default("company")
        if user_company and "company" not in filters:
            filters["company"] = user_company

    return original_run(
        report_name,
        filters=filters,
        user=user,
        ignore_prepared_report=ignore_prepared_report,
        custom_columns=custom_columns,
        is_custom_report=is_custom_report,
    )
