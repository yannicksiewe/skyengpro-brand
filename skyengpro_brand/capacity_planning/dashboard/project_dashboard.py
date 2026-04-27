# Copyright (c) 2026, SkyEngPro and contributors
"""Extends ERPNext's Project Connections panel with a Capacity Planning section
that surfaces Project Allocation rows for the open project. Wired via
hooks.py:override_doctype_dashboards.

Frappe chains overrides: each registered handler receives the previous
handler's `data` dict and returns it. We accept the optional `data` arg so we
play nice with HRMS's override (which extends Project too).
"""
from frappe import _


def get_data(data=None):
    if data is None:
        # Direct invocation (smoke test, manual call) — fetch upstream first.
        try:
            from erpnext.projects.doctype.project.project_dashboard import get_data as upstream
            data = upstream()
        except Exception:
            data = {"fieldname": "project", "transactions": []}

    transactions = data.setdefault("transactions", [])
    label = _("Capacity Planning")
    if not any(s.get("label") == label for s in transactions):
        transactions.append({
            "label": label,
            "items": ["Project Allocation"],
        })
    return data
