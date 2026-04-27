# Copyright (c) 2026, SkyEngPro and contributors
# Per-employee weekly capacity planning report.
#
# Capacity formula:
#   Gross capacity (h)  = working_days_in_week × daily_hours
#                          (working_days = Mon-Fri minus Holiday List entries)
#                          (daily_hours from Employee.default_shift if set,
#                           else HR Settings.standard_working_hours)
#   Time off (h)        = approved Leave Application hours + Attendance
#                          (Absent / Half Day) hours, with precedence
#                          Holiday > Leave > Attendance to avoid double-count
#   Available (h)       = max(0, gross - time off)
#   Engaged (h)         = max(planned, actual) for past/current weeks
#                         planned only for future weeks
#   Remaining (h)       = available - engaged
#   Utilization %       = engaged / available × 100  (None if available == 0)
#
# Planned engagement (per project):
#   - If a non-cancelled `Project Allocation` covers the week for this employee,
#     it WINS for that project (allocation_pct × daily_hours × overlap_workdays).
#   - Otherwise, sum Task.expected_time × workday-overlap-ratio for tasks
#     assigned to the employee's user_id whose project lacks an allocation.
#   - Unassigned-project tasks always count.
#
# This avoids double-counting an Allocation budget against the individual Tasks
# that fulfil it.

from __future__ import annotations

from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import getdate


# ---- public entrypoint -------------------------------------------------------

def execute(filters=None):
    filters = frappe._dict(filters or {})
    week_start, week_end = _resolve_week(filters.get("week_start_date"))

    columns = _columns()
    employees = _get_employees(filters)
    today = getdate()
    is_future_week = week_start > today

    daily_hours_map = {e.name: _daily_hours(e) for e in employees}
    holidays_map = _holidays_in_week_batch(employees, week_start, week_end)

    leave_hours_by_emp, leave_dates_by_emp = _leave_reducer_batch(
        employees, week_start, week_end, daily_hours_map, holidays_map
    )
    attendance_hours_by_emp = _attendance_reducer_batch(
        employees, week_start, week_end, daily_hours_map, leave_dates_by_emp
    )

    rows = []
    for emp in employees:
        gross = _capacity_hours(emp, week_start, week_end, daily_hours_map, holidays_map)
        time_off = leave_hours_by_emp.get(emp.name, 0.0) + attendance_hours_by_emp.get(
            emp.name, 0.0
        )
        time_off = min(time_off, gross)
        available = max(0.0, gross - time_off)

        planned, planned_projects = _engagement_planned(
            emp.name,
            emp.user_id,
            week_start,
            week_end,
            daily_hours_map.get(emp.name, 8.0),
        )
        actual = _actual_hours(emp.name, week_start, week_end)
        actual_projects = _actual_projects(emp.name, week_start, week_end)
        engaged = planned if is_future_week else max(planned, actual)
        remaining = available - engaged
        utilization = (engaged / available * 100.0) if available else None
        projects = len(planned_projects | actual_projects)

        rows.append({
            "employee": emp.name,
            "employee_name": emp.employee_name,
            "department": emp.department,
            "capacity_hours": round(gross, 2),
            "time_off_hours": round(time_off, 2),
            "available_hours": round(available, 2),
            "planned_hours": round(planned, 2),
            "actual_hours": round(actual, 2),
            "engaged_hours": round(engaged, 2),
            "remaining_hours": round(remaining, 2),
            "project_count": projects,
            "utilization_pct": round(utilization, 1) if utilization is not None else None,
        })

    rows.sort(key=lambda r: (r["available_hours"] == 0, r["remaining_hours"]))
    chart = _chart(rows)
    summary = _summary(rows)
    return columns, rows, None, chart, summary


# ---- columns -----------------------------------------------------------------

def _columns():
    return [
        {"fieldname": "employee", "label": _("Employee"), "fieldtype": "Link", "options": "Employee", "width": 130},
        {"fieldname": "employee_name", "label": _("Name"), "fieldtype": "Data", "width": 180},
        {"fieldname": "department", "label": _("Department"), "fieldtype": "Link", "options": "Department", "width": 150},
        {"fieldname": "capacity_hours", "label": _("Capacity (h)"), "fieldtype": "Float", "width": 100, "precision": 2},
        {"fieldname": "time_off_hours", "label": _("Time off (h)"), "fieldtype": "Float", "width": 100, "precision": 2},
        {"fieldname": "available_hours", "label": _("Available (h)"), "fieldtype": "Float", "width": 110, "precision": 2},
        {"fieldname": "planned_hours", "label": _("Planned (h)"), "fieldtype": "Float", "width": 100, "precision": 2},
        {"fieldname": "actual_hours", "label": _("Actual (h)"), "fieldtype": "Float", "width": 100, "precision": 2},
        {"fieldname": "engaged_hours", "label": _("Engaged (h)"), "fieldtype": "Float", "width": 100, "precision": 2},
        {"fieldname": "remaining_hours", "label": _("Remaining (h)"), "fieldtype": "Float", "width": 110, "precision": 2},
        {"fieldname": "project_count", "label": _("# Projects"), "fieldtype": "Int", "width": 90},
        {"fieldname": "utilization_pct", "label": _("Utilization %"), "fieldtype": "Percent", "width": 110},
    ]


# ---- filters helpers ---------------------------------------------------------

def _resolve_week(week_start_date):
    d = getdate(week_start_date) if week_start_date else getdate()
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _get_employees(filters):
    cond = {"status": "Active"}
    if filters.get("employee"):
        cond["name"] = filters["employee"]
    if filters.get("department"):
        cond["department"] = filters["department"]
    if filters.get("company"):
        cond["company"] = filters["company"]
    return frappe.db.get_all(
        "Employee",
        filters=cond,
        fields=["name", "employee_name", "department", "user_id", "default_shift", "holiday_list", "company"],
        order_by="employee_name asc",
    )


# ---- capacity (gross) -------------------------------------------------------

def _capacity_hours(emp, week_start, week_end, daily_hours_map, holidays_map):
    daily = daily_hours_map.get(emp.name, 8.0)
    holidays = holidays_map.get(emp.name, set())
    working_days = 0
    d = week_start
    while d <= week_end:
        if d.weekday() < 5 and d not in holidays:
            working_days += 1
        d += timedelta(days=1)
    return daily * working_days


def _daily_hours(emp):
    fallback = float(frappe.db.get_single_value("HR Settings", "standard_working_hours") or 8.0)
    if not emp.default_shift:
        return fallback
    shift = frappe.db.get_value(
        "Shift Type",
        emp.default_shift,
        ["start_time", "end_time"],
        as_dict=True,
    )
    if not shift or not shift.start_time or not shift.end_time:
        return fallback
    start_h = _seconds_to_hours(shift.start_time)
    end_h = _seconds_to_hours(shift.end_time)
    span = end_h - start_h
    if span <= 0:
        return fallback
    # Subtract a 1h lunch if span > 6h (best-effort heuristic; HRMS does not
    # store break duration on Shift Type).
    return span - 1.0 if span > 6.0 else span


def _seconds_to_hours(t):
    if isinstance(t, timedelta):
        return t.total_seconds() / 3600.0
    if isinstance(t, datetime) or hasattr(t, "hour"):
        return t.hour + t.minute / 60.0 + t.second / 3600.0
    return 0.0


def _holidays_in_week_batch(employees, week_start, week_end):
    holiday_lists = {e.holiday_list for e in employees if e.holiday_list}
    if not holiday_lists:
        return {e.name: set() for e in employees}
    rows = frappe.db.sql(
        """
        SELECT parent, holiday_date
        FROM `tabHoliday`
        WHERE parent IN %(lists)s
          AND holiday_date BETWEEN %(start)s AND %(end)s
        """,
        {"lists": tuple(holiday_lists), "start": week_start, "end": week_end},
        as_dict=True,
    )
    by_list = {}
    for r in rows:
        by_list.setdefault(r["parent"], set()).add(getdate(r["holiday_date"]))
    return {e.name: by_list.get(e.holiday_list, set()) for e in employees}


# ---- time off: approved leaves -----------------------------------------------

def _leave_reducer_batch(employees, week_start, week_end, daily_hours_map, holidays_map):
    """Returns (hours_by_employee, dates_by_employee) for approved leaves."""
    hours_by_emp = {}
    dates_by_emp = {}
    if not employees:
        return hours_by_emp, dates_by_emp

    rows = frappe.db.sql(
        """
        SELECT
            la.employee,
            la.from_date,
            la.to_date,
            la.half_day,
            la.half_day_date,
            COALESCE(lt.include_holiday, 0) AS include_holiday
        FROM `tabLeave Application` la
        LEFT JOIN `tabLeave Type` lt ON lt.name = la.leave_type
        WHERE la.employee IN %(emps)s
          AND la.docstatus = 1
          AND la.status = 'Approved'
          AND la.from_date <= %(week_end)s
          AND la.to_date >= %(week_start)s
        """,
        {
            "emps": tuple(e.name for e in employees),
            "week_start": week_start,
            "week_end": week_end,
        },
        as_dict=True,
    )

    for r in rows:
        emp = r["employee"]
        daily = daily_hours_map.get(emp, 8.0)
        holidays = holidays_map.get(emp, set())
        for day, frac in _leave_day_fractions(r, week_start, week_end, holidays):
            hours_by_emp[emp] = hours_by_emp.get(emp, 0.0) + frac * daily
            dates_by_emp.setdefault(emp, set()).add(day)
    return hours_by_emp, dates_by_emp


def _leave_day_fractions(la_row, week_start, week_end, holidays):
    """Yield (date, fraction) for each in-week, working day this leave consumes."""
    start = max(getdate(la_row["from_date"]), week_start)
    end = min(getdate(la_row["to_date"]), week_end)
    half_day = bool(la_row.get("half_day"))
    half_day_date = getdate(la_row["half_day_date"]) if la_row.get("half_day_date") else None
    include_holiday = bool(la_row.get("include_holiday"))

    d = start
    while d <= end:
        if d.weekday() >= 5:
            d += timedelta(days=1)
            continue
        if d in holidays and not include_holiday:
            d += timedelta(days=1)
            continue
        frac = 0.5 if (half_day and half_day_date == d) else 1.0
        yield d, frac
        d += timedelta(days=1)


# ---- time off: attendance absences (with anti-join vs leaves) ---------------

def _attendance_reducer_batch(employees, week_start, week_end, daily_hours_map, leave_dates_by_emp):
    hours_by_emp = {}
    if not employees:
        return hours_by_emp
    rows = frappe.db.sql(
        """
        SELECT employee, attendance_date, status
        FROM `tabAttendance`
        WHERE employee IN %(emps)s
          AND docstatus = 1
          AND attendance_date BETWEEN %(start)s AND %(end)s
          AND status IN ('Absent', 'Half Day')
        """,
        {
            "emps": tuple(e.name for e in employees),
            "start": week_start,
            "end": week_end,
        },
        as_dict=True,
    )
    for r in rows:
        emp = r["employee"]
        d = getdate(r["attendance_date"])
        if d in leave_dates_by_emp.get(emp, set()):
            continue
        daily = daily_hours_map.get(emp, 8.0)
        frac = 0.5 if r["status"] == "Half Day" else 1.0
        hours_by_emp[emp] = hours_by_emp.get(emp, 0.0) + frac * daily
    return hours_by_emp


# ---- engagement: planned (allocations + tasks) ------------------------------

def _engagement_planned(employee, user_id, week_start, week_end, daily_hours, exclude_allocation=None):
    """Return (total_planned_hours, set_of_projects_engaged) for this week.

    Allocation hours win per-project; Task expected_time fills in for any
    project not covered by an active allocation. Tasks without a project are
    always counted (they don't conflict with any allocation).
    """
    # Active allocations — per project
    alloc_filters = {
        "employee": employee,
        "from_date": ["<=", week_end],
        "to_date": [">=", week_start],
        "status": ["!=", "Cancelled"],
    }
    if exclude_allocation:
        alloc_filters["name"] = ["!=", exclude_allocation]
    alloc_rows = []
    if frappe.db.exists("DocType", "Project Allocation"):
        alloc_rows = frappe.db.get_all(
            "Project Allocation",
            filters=alloc_filters,
            fields=["name", "project", "from_date", "to_date", "allocation_pct"],
        )

    alloc_hours_by_proj = {}
    for r in alloc_rows:
        overlap_start = max(getdate(r.from_date), week_start)
        overlap_end = min(getdate(r.to_date), week_end)
        wd = _count_weekdays(overlap_start, overlap_end)
        if wd <= 0:
            continue
        h = wd * daily_hours * (float(r.allocation_pct or 0) / 100.0)
        alloc_hours_by_proj[r.project] = alloc_hours_by_proj.get(r.project, 0.0) + h

    # Task hours — per project, but skip projects already covered by allocation
    task_hours_by_proj = {}
    if user_id:
        rows = frappe.db.sql(
            """
            SELECT t.name, t.project, t.expected_time, t.exp_start_date, t.exp_end_date
            FROM `tabTask` t
            INNER JOIN `tabToDo` td
                    ON td.reference_type = 'Task' AND td.reference_name = t.name
            WHERE td.allocated_to = %(user)s
              AND td.status = 'Open'
              AND IFNULL(t.expected_time, 0) > 0
              AND t.exp_start_date IS NOT NULL
              AND t.exp_end_date IS NOT NULL
              AND t.exp_start_date <= %(week_end)s
              AND t.exp_end_date >= %(week_start)s
              AND t.status NOT IN ('Cancelled', 'Completed')
            """,
            {"user": user_id, "week_start": week_start, "week_end": week_end},
            as_dict=True,
        )
        for r in rows:
            project_key = r.project or "_unassigned"
            if r.project and r.project in alloc_hours_by_proj:
                continue  # allocation already accounts for this project
            task_wd = _count_weekdays(getdate(r.exp_start_date), getdate(r.exp_end_date))
            if task_wd <= 0:
                continue
            overlap_start = max(getdate(r.exp_start_date), week_start)
            overlap_end = min(getdate(r.exp_end_date), week_end)
            overlap_wd = _count_weekdays(overlap_start, overlap_end)
            h = float(r.expected_time) * (overlap_wd / task_wd)
            task_hours_by_proj[project_key] = task_hours_by_proj.get(project_key, 0.0) + h

    total = sum(alloc_hours_by_proj.values()) + sum(task_hours_by_proj.values())
    projects = set(alloc_hours_by_proj.keys()) | {
        p for p in task_hours_by_proj if p != "_unassigned"
    }
    return total, projects


def _count_weekdays(start, end):
    if start > end:
        return 0
    days = 0
    d = start
    while d <= end:
        if d.weekday() < 5:
            days += 1
        d += timedelta(days=1)
    return days


# ---- engagement: actual -----------------------------------------------------

def _actual_hours(employee, week_start, week_end):
    res = frappe.db.sql(
        """
        SELECT COALESCE(SUM(td.hours), 0)
        FROM `tabTimesheet Detail` td
        INNER JOIN `tabTimesheet` t ON td.parent = t.name
        WHERE t.employee = %(emp)s
          AND t.docstatus < 2
          AND DATE(td.from_time) BETWEEN %(start)s AND %(end)s
        """,
        {"emp": employee, "start": week_start, "end": week_end},
    )
    return float(res[0][0]) if res else 0.0


def _actual_projects(employee, week_start, week_end):
    res = frappe.db.sql_list(
        """
        SELECT DISTINCT td.project
        FROM `tabTimesheet Detail` td
        INNER JOIN `tabTimesheet` t ON td.parent = t.name
        WHERE t.employee = %(emp)s
          AND td.project IS NOT NULL
          AND DATE(td.from_time) BETWEEN %(start)s AND %(end)s
        """,
        {"emp": employee, "start": week_start, "end": week_end},
    )
    return {p for p in res if p}


# ---- chart + summary --------------------------------------------------------

def _chart(rows):
    plottable = [r for r in rows if r["available_hours"] > 0][:15]
    return {
        "data": {
            "labels": [r["employee_name"] or r["employee"] for r in plottable],
            "datasets": [
                {"name": _("Engaged"), "values": [r["engaged_hours"] for r in plottable]},
                {"name": _("Remaining"), "values": [r["remaining_hours"] for r in plottable]},
            ],
        },
        "type": "bar",
        "barOptions": {"stacked": True},
        "colors": ["#ef4444", "#22c55e"],
    }


def _summary(rows):
    if not rows:
        return []
    n = len(rows)
    overbooked = sum(1 for r in rows if r["available_hours"] > 0 and r["remaining_hours"] < 0)
    free = sum(1 for r in rows if r["available_hours"] > 0 and r["remaining_hours"] >= 4)
    off = sum(1 for r in rows if r["available_hours"] == 0)
    util_rows = [r for r in rows if r["utilization_pct"] is not None]
    avg_util = (sum(r["utilization_pct"] for r in util_rows) / len(util_rows)) if util_rows else 0.0
    return [
        {"label": _("Employees"), "value": n, "datatype": "Int"},
        {"label": _("Overbooked"), "value": overbooked, "datatype": "Int", "indicator": "Red" if overbooked else "Green"},
        {"label": _("Free ≥ 4h"), "value": free, "datatype": "Int"},
        {"label": _("On leave / off"), "value": off, "datatype": "Int", "indicator": "Grey"},
        {"label": _("Avg utilization"), "value": round(avg_util, 1), "datatype": "Percent"},
    ]
