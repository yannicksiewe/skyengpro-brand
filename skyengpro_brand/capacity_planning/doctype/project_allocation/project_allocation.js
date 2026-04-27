// Copyright (c) 2026, SkyEngPro and contributors
//
// Live capacity banner: when employee + dates are filled, query the backend
// for the next 4 weeks of availability and show a per-week summary at the top
// of the form, factoring in the % being entered now.

frappe.ui.form.on("Project Allocation", {
    refresh(frm) { _refresh_banner(frm); },
    employee(frm) { _refresh_banner(frm); },
    from_date(frm) { _refresh_banner(frm); },
    to_date(frm) { _refresh_banner(frm); },
    allocation_pct(frm) { _refresh_banner(frm); },
});

function _refresh_banner(frm) {
    if (!frm.doc.employee || !frm.doc.from_date) {
        frm.dashboard.clear_headline();
        return;
    }
    frappe.call({
        method: "skyengpro_brand.capacity_planning.api.get_employee_availability",
        args: {
            employee: frm.doc.employee,
            from_date: frm.doc.from_date,
            weeks: 4,
            exclude_allocation: frm.doc.name || "",
        },
        callback(r) {
            if (!r || !r.message || !Array.isArray(r.message.weeks)) return;
            const pct_this = parseFloat(frm.doc.allocation_pct) || 0;
            const parts = r.message.weeks.map(w => {
                const new_engaged = w.engaged + (pct_this / 100.0) * w.gross_capacity;
                const new_remaining = w.available - new_engaged;
                const color = new_remaining < 0 ? "#b91c1c"
                            : new_remaining < 4 ? "#b45309"
                            : "#15803d";
                const label = w.week_start.slice(5);  // MM-DD
                return `<span style="color:${color};font-weight:500">`
                     + `wk ${label}: ${new_remaining.toFixed(1)}h left`
                     + `</span>`;
            });
            frm.dashboard.clear_headline();
            frm.dashboard.set_headline(
                "<strong>Projected remaining capacity after this allocation:</strong> "
                + parts.join(" &nbsp;|&nbsp; ")
            );
        },
    });
}
