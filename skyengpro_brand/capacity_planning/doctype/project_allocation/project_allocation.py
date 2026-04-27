# Copyright (c) 2026, SkyEngPro and contributors
"""Project Allocation — books an employee's % capacity to a project for a date range.

The Employee Capacity Planning report consumes these rows as the authoritative
"planned" engagement when present, falling back to Task.expected_time for any
project that lacks an active allocation. See
skyengpro_brand.capacity_planning.report.employee_capacity_planning.
"""
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class ProjectAllocation(Document):
    def validate(self):
        self._validate_dates()
        self._validate_pct()
        self._warn_on_overlap()

    def _validate_dates(self):
        if not self.from_date or not self.to_date:
            return
        if getdate(self.from_date) > getdate(self.to_date):
            frappe.throw(_("From Date cannot be after To Date"))

    def _validate_pct(self):
        if self.allocation_pct is None or self.allocation_pct <= 0:
            frappe.throw(_("Allocation % must be greater than 0"))
        if self.allocation_pct > 100:
            frappe.throw(
                _(
                    "Allocation % cannot exceed 100 on a single row. "
                    "Use multiple Project Allocation rows for split work."
                )
            )

    def _warn_on_overlap(self):
        """Soft warning if another active allocation for the same employee+project overlaps this one."""
        cond = {
            "employee": self.employee,
            "project": self.project,
            "status": ["!=", "Cancelled"],
            "from_date": ["<=", self.to_date],
            "to_date": [">=", self.from_date],
        }
        if not self.is_new() and self.name:
            cond["name"] = ["!=", self.name]
        existing = frappe.db.get_all(
            "Project Allocation", filters=cond, fields=["name"], limit=1
        )
        if existing:
            frappe.msgprint(
                _(
                    "An overlapping Project Allocation already exists for this "
                    "employee on this project: {0}"
                ).format(existing[0].name),
                indicator="orange",
                alert=True,
            )
