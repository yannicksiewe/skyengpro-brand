# Copyright (c) 2026, SkyEngPro and contributors
"""Extends HRMS's Employee Connections panel with a Capacity Planning section
that surfaces Project Allocation rows for the open employee.

Frappe chains overrides: each registered handler receives the previous
handler's `data` dict and returns it.
"""
from frappe import _


def get_data(data=None):
    if data is None:
        try:
            from hrms.hr.doctype.employee.employee_dashboard import get_data as upstream
            data = upstream()
        except Exception:
            data = {"fieldname": "employee", "transactions": []}

    transactions = data.setdefault("transactions", [])
    label = _("Capacity Planning")
    if not any(s.get("label") == label for s in transactions):
        transactions.append({
            "label": label,
            "items": ["Project Allocation"],
        })
    return data
