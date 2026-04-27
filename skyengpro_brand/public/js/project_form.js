// Copyright (c) 2026, SkyEngPro and contributors
//
// Adds a "Capacity Check" button to the Project form. Opens a dialog showing
// per-week remaining hours for each Project User over the next 4 weeks.

frappe.ui.form.on("Project", {
    refresh(frm) {
        if (frm.is_new()) return;
        frm.add_custom_button(__("Capacity Check"), () => _open_dialog(frm), __("View"));
    },
});

function _open_dialog(frm) {
    const users = (frm.doc.users || [])
        .map(row => row.user)
        .filter(Boolean);
    if (users.length === 0) {
        frappe.msgprint({
            title: __("No project users"),
            message: __("Add users on the <b>Users</b> tab first, then run Capacity Check."),
            indicator: "orange",
        });
        return;
    }

    const dlg = new frappe.ui.Dialog({
        title: __("Capacity Check — next 4 weeks"),
        size: "extra-large",
        fields: [{ fieldtype: "HTML", fieldname: "html" }],
    });
    dlg.show();
    dlg.fields_dict.html.$wrapper.html(
        '<div style="text-align:center;padding:2rem;color:#64748b">Loading…</div>'
    );

    frappe.call({
        method: "skyengpro_brand.capacity_planning.api.get_users_availability",
        args: {
            users: JSON.stringify(users),
            weeks: 4,
        },
        callback(r) {
            if (!r || !r.message) {
                dlg.fields_dict.html.$wrapper.html(
                    '<div style="padding:1rem;color:#b91c1c">Failed to load capacity data.</div>'
                );
                return;
            }
            dlg.fields_dict.html.$wrapper.html(_render(r.message));
        },
    });
}

function _render(data) {
    if (!data.employees || data.employees.length === 0) {
        return (
            '<div style="padding:1rem;color:#64748b">' +
            __("None of the project users are mapped to active Employees with capacity data.") +
            "</div>"
        );
    }

    const headers = data.week_headers || [];
    let html = '<div style="overflow-x:auto"><table class="table table-bordered" ';
    html += 'style="font-size:13px;margin-bottom:0">';
    html += "<thead><tr>";
    html += '<th style="background:#f8fafc">' + __("Employee") + "</th>";
    for (const wk of headers) {
        const label = wk.slice(5);  // MM-DD
        html += `<th style="background:#f8fafc;text-align:right">wk ${label}</th>`;
    }
    html += "</tr></thead><tbody>";

    for (const emp of data.employees) {
        html += `<tr><td><strong>${frappe.utils.escape_html(emp.employee_name || emp.employee)}</strong>`;
        html += `<div style="color:#64748b;font-size:11px">${frappe.utils.escape_html(emp.user_id || "")}</div></td>`;
        for (const w of emp.weeks) {
            const remaining = w.remaining;
            const color = remaining < 0 ? "#b91c1c" : (remaining < 4 ? "#b45309" : "#15803d");
            const sub = `<div style="color:#64748b;font-size:11px">avail ${w.available.toFixed(1)}h, engaged ${w.engaged.toFixed(1)}h</div>`;
            html += `<td style="text-align:right">`;
            html += `<span style="color:${color};font-weight:600">${remaining.toFixed(1)}h left</span>`;
            html += sub;
            html += `</td>`;
        }
        html += "</tr>";
    }
    html += "</tbody></table></div>";
    html += '<div style="margin-top:0.75rem;font-size:12px;color:#64748b">';
    html += __("Red = overbooked, amber = &lt; 4h slack, green = comfortable. Click an Employee to drill into the Capacity Planning report.");
    html += "</div>";
    return html;
}
