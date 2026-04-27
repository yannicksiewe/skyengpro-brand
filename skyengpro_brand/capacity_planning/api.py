# Copyright (c) 2026, SkyEngPro and contributors
"""Whitelisted endpoints feeding the Project Allocation form banner and the
Project form's "Capacity Check" dialog. Both endpoints reuse the helpers from
the Employee Capacity Planning report so capacity logic stays in one place.
"""
from __future__ import annotations

import json
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import getdate

from skyengpro_brand.capacity_planning.report.employee_capacity_planning.employee_capacity_planning import (
    _actual_hours,
    _capacity_hours,
    _daily_hours,
    _engagement_planned,
    _get_employees,
    _holidays_in_week_batch,
    _leave_reducer_batch,
    _attendance_reducer_batch,
    _resolve_week,
)


def _employee_week(emp, week_start, week_end, daily_map, exclude_allocation=None):
    holidays = _holidays_in_week_batch([emp], week_start, week_end)
    leave_h, leave_dates = _leave_reducer_batch(
        [emp], week_start, week_end, daily_map, holidays
    )
    att_h = _attendance_reducer_batch([emp], week_start, week_end, daily_map, leave_dates)
    gross = _capacity_hours(emp, week_start, week_end, daily_map, holidays)
    time_off = min(leave_h.get(emp.name, 0.0) + att_h.get(emp.name, 0.0), gross)
    available = max(0.0, gross - time_off)
    planned, _projects = _engagement_planned(
        emp.name,
        emp.user_id,
        week_start,
        week_end,
        daily_map.get(emp.name, 8.0),
        exclude_allocation=exclude_allocation,
    )
    actual = _actual_hours(emp.name, week_start, week_end)
    today = getdate()
    engaged = planned if week_start > today else max(planned, actual)
    return {
        "week_start": week_start.strftime("%Y-%m-%d"),
        "week_end": week_end.strftime("%Y-%m-%d"),
        "gross_capacity": round(gross, 2),
        "time_off": round(time_off, 2),
        "available": round(available, 2),
        "engaged": round(engaged, 2),
        "remaining": round(available - engaged, 2),
    }


@frappe.whitelist()
def get_employee_availability(employee, from_date, weeks=4, exclude_allocation=None):
    """Return per-week availability for one employee.

    `exclude_allocation` lets the Project Allocation form ask "what would my
    capacity look like *without* this row?", so editing an existing allocation
    doesn't make the projected impact double-count itself.
    """
    weeks = int(weeks or 4)
    start = getdate(from_date)
    emps = _get_employees(frappe._dict({"employee": employee}))
    if not emps:
        return {"weeks": [], "error": _("Employee not found or inactive")}
    emp = emps[0]
    daily_map = {emp.name: _daily_hours(emp)}
    out = []
    for i in range(weeks):
        ws, we = _resolve_week(start + timedelta(days=7 * i))
        out.append(_employee_week(emp, ws, we, daily_map, exclude_allocation=exclude_allocation))
    return {"employee": employee, "employee_name": emp.employee_name, "weeks": out}


@frappe.whitelist()
def get_users_availability(users, weeks=4, from_date=None):
    """Return per-week availability for the Employees mapped to the given Frappe users.

    Used by the Capacity Check button on the Project form, which receives the
    users from `Project.users[*].user`. Users without an Employee record (or
    inactive ones) are silently skipped.
    """
    if isinstance(users, str):
        try:
            users = json.loads(users)
        except ValueError:
            users = [u.strip() for u in users.split(",") if u.strip()]
    weeks = int(weeks or 4)
    start = getdate(from_date) if from_date else getdate()

    emps = frappe.db.get_all(
        "Employee",
        filters={"status": "Active", "user_id": ["in", users]},
        fields=[
            "name",
            "employee_name",
            "department",
            "user_id",
            "default_shift",
            "holiday_list",
            "company",
        ],
        order_by="employee_name asc",
    )
    if not emps:
        return {"employees": [], "week_headers": []}

    daily_map = {e.name: _daily_hours(e) for e in emps}

    week_headers = []
    out = []
    for emp in emps:
        weeks_data = []
        for i in range(weeks):
            ws, we = _resolve_week(start + timedelta(days=7 * i))
            if len(week_headers) < weeks:
                week_headers.append(ws.strftime("%Y-%m-%d"))
            weeks_data.append(_employee_week(emp, ws, we, daily_map))
        out.append(
            {
                "employee": emp.name,
                "employee_name": emp.employee_name,
                "user_id": emp.user_id,
                "weeks": weeks_data,
            }
        )
    return {"employees": out, "week_headers": week_headers}
