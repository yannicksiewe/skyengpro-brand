// Copyright (c) 2026, SkyEngPro and contributors

frappe.query_reports["Employee Capacity Planning"] = {
    filters: [
        {
            fieldname: "week_start_date",
            label: __("Week (any date in week)"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1,
        },
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            default: frappe.defaults.get_user_default("Company"),
        },
        {
            fieldname: "department",
            label: __("Department"),
            fieldtype: "Link",
            options: "Department",
        },
        {
            fieldname: "employee",
            label: __("Employee"),
            fieldtype: "Link",
            options: "Employee",
        },
    ],

    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        const fully_off = (data.available_hours === 0);

        // Dim every cell on a fully-off row (gray, no red anywhere)
        if (fully_off) {
            return `<span style="color: #94a3b8;">${value}</span>`;
        }

        if (column.fieldname === "time_off_hours" && data.time_off_hours > 0) {
            return `<span style="color: #b45309;">${value}</span>`;
        }

        if (column.fieldname === "remaining_hours") {
            if (data.remaining_hours < 0) {
                return `<span style="color: #b91c1c; font-weight: 600;">${value}</span>`;
            }
            if (data.remaining_hours < 4) {
                return `<span style="color: #b45309; font-weight: 600;">${value}</span>`;
            }
            return `<span style="color: #15803d;">${value}</span>`;
        }

        if (column.fieldname === "utilization_pct") {
            if (data.utilization_pct == null) {
                return `<span style="color: #94a3b8;">—</span>`;
            }
            if (data.utilization_pct > 100) {
                return `<span style="color: #b91c1c; font-weight: 600;">${value}</span>`;
            }
            if (data.utilization_pct > 85) {
                return `<span style="color: #b45309;">${value}</span>`;
            }
        }

        return value;
    },
};
