"""
SkyEngPro Platform — Post-install / Post-migrate Setup

Runs automatically on:
  - bench --site <site> install-app skyengpro_brand
  - bench --site <site> migrate

Idempotent: safe to run repeatedly.
"""
import frappe
import shutil
import os


BRAND_FILES = [
    "SkyEngPro_Logo_Primary_400px.png",
    "SkyEngPro_Icon_32px.png",
    "SkyEngPro_Icon_512px.png",
    "SkyEngPro_Logo_Tagline_800px.png",
    "SkyEngPro_Logo_White_800px.png",
    "SkyEngPro_Logo_Navbar.png",
    "SkyEngPro_Logo_White_Navbar.png",
]


def after_install():
    """Main entry point — called by hooks.py on install and migrate."""
    frappe.logger("skyengpro").info("SkyEngPro setup: starting...")

    # 1. Branding (logos, favicon, system name)
    copy_brand_assets()
    apply_website_settings()
    apply_navbar_settings()
    apply_system_settings()

    # 2. Module Profiles (from config.py)
    from skyengpro_brand.setup_roles import setup_module_profiles, sync_all_users_profiles
    setup_module_profiles()
    sync_all_users_profiles()

    # 3. Desk & Workspace Permissions
    from skyengpro_brand.setup_permissions import setup_all_permissions
    setup_all_permissions()

    # 4. Performance indexes for capacity-planning aggregations
    ensure_capacity_indexes()

    # 5. Workspace shortcuts for the Employee Capacity Planning report
    ensure_capacity_workspace_shortcuts()

    # 6. Insights "SkyEngPro Overview" dashboard (create only if missing —
    #    user edits in the UI are preserved across migrations).
    ensure_overview_dashboard()

    frappe.db.commit()
    frappe.logger("skyengpro").info("SkyEngPro setup: complete.")


def ensure_capacity_workspace_shortcuts():
    """Add a shortcut card for the Employee Capacity Planning report on the
    Home, People, and Projects workspaces so managers find it from the desk
    home.

    In Frappe v15+ a workspace card has two parts:
      1. A `Workspace Shortcut` child row referencing the report.
      2. An entry in the workspace's `content` JSON that renders the card.
    Both must be present. This function manages both, idempotently.
    """
    import json as _json

    # Each entry: (workspace, [(shortcut_type, link_to, label, color), ...])
    targets = [
        ("Home", [
            ("Report", "Employee Capacity Planning", "Capacity Planning", "Green"),
        ]),
        ("People", [
            ("Report", "Employee Capacity Planning", "Capacity Planning", "Green"),
            ("DocType", "Project Allocation", "Project Allocations", "Blue"),
        ]),
        ("Projects", [
            ("Report", "Employee Capacity Planning", "Capacity Planning", "Green"),
            ("DocType", "Project Allocation", "Project Allocations", "Blue"),
        ]),
    ]

    for ws_name, shortcuts in targets:
        if not frappe.db.exists("Workspace", ws_name):
            frappe.logger("skyengpro").info("Workspace %s not found, skipping shortcut", ws_name)
            continue
        ws = frappe.get_doc("Workspace", ws_name)
        try:
            blocks = _json.loads(ws.content or "[]")
        except ValueError:
            blocks = []
        changed = False

        for stype, link_to, label, color in shortcuts:
            # Skip DocType shortcuts whose target doesn't exist on this site yet
            # (e.g. Project Allocation before its DocType has been migrated).
            if stype == "DocType" and not frappe.db.exists("DocType", link_to):
                continue

            has_row = any(
                (s.type == stype and s.link_to == link_to)
                for s in (ws.shortcuts or [])
            )
            if not has_row:
                ws.append("shortcuts", {
                    "type": stype,
                    "link_to": link_to,
                    "label": label,
                    "color": color,
                })
                changed = True

            already_rendered = any(
                b.get("type") == "shortcut" and b.get("data", {}).get("shortcut_name") == label
                for b in blocks
            )
            if not already_rendered:
                new_block = {"type": "shortcut", "data": {"shortcut_name": label, "col": 3}}
                last_shortcut_idx = -1
                for i, b in enumerate(blocks):
                    if b.get("type") == "shortcut":
                        last_shortcut_idx = i
                if last_shortcut_idx >= 0:
                    blocks.insert(last_shortcut_idx + 1, new_block)
                else:
                    header = {
                        "type": "header",
                        "data": {"text": "<span class=\"h4\"><b>Your Shortcuts</b></span>", "col": 12},
                    }
                    blocks = [header, new_block] + blocks
                changed = True

        if changed:
            ws.content = _json.dumps(blocks)
            ws.save(ignore_permissions=True)
            frappe.logger("skyengpro").info("Updated shortcuts on workspace %s", ws_name)


def ensure_capacity_indexes():
    """Create indexes that speed up the Employee Capacity Planning report.

    The report aggregates Timesheet Detail by employee+date and Task by
    assignee+date range. Without these indexes the aggregation table-scans
    once Timesheet volume crosses ~100k rows.
    """
    indexes = [
        ("tabTimesheet Detail", "idx_skyeng_td_parent_fromtime", ["parent", "from_time"]),
        ("tabTask", "idx_skyeng_task_dates", ["exp_start_date", "exp_end_date"]),
        ("tabToDo", "idx_skyeng_todo_alloc_ref", ["allocated_to", "reference_type", "reference_name"]),
        ("tabLeave Application", "idx_skyeng_leave_emp_status_dates", ["employee", "status", "from_date", "to_date"]),
        ("tabAttendance", "idx_skyeng_attendance_emp_status_date", ["employee", "status", "attendance_date"]),
    ]
    for table, name, cols in indexes:
        if _index_exists(table, name):
            continue
        col_list = ", ".join(f"`{c}`" for c in cols)
        try:
            frappe.db.sql(f"CREATE INDEX `{name}` ON `{table}` ({col_list})")
            frappe.logger("skyengpro").info("Created index %s on %s", name, table)
        except Exception as e:
            frappe.logger("skyengpro").warning("Index %s on %s failed: %s", name, table, e)


def _index_exists(table, index_name):
    res = frappe.db.sql(
        """
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND index_name = %s
        LIMIT 1
        """,
        (table, index_name),
    )
    return bool(res)


# ─────────────────────────────────────────────────────────────
# Branding
# ─────────────────────────────────────────────────────────────

def copy_brand_assets():
    """Copy logo files from the app's public/files into the site's public/files."""
    app_files_dir = os.path.join(
        frappe.get_app_path("skyengpro_brand"), "public", "files"
    )
    site_files_dir = os.path.join(
        frappe.get_site_path(), "public", "files"
    )
    os.makedirs(site_files_dir, exist_ok=True)

    for fname in BRAND_FILES:
        src = os.path.join(app_files_dir, fname)
        dst = os.path.join(site_files_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            frappe.logger("skyengpro").info("Copied brand asset: %s", fname)


def apply_website_settings():
    """Set SkyEngPro defaults for Website Settings.

    Note: the URLs below point at the new `brand/skyengpro/` folder layout.
    Per-tenant logo swap on the desk happens client-side via brand_loader.js;
    Website Settings is the *fallback* for guest pages (login, portal).

    The display app name is sourced from `apply_branding.APP_NAME` so there's
    one place to change it; previously this function hardcoded "SEP ERP" and
    overwrote any change made there on every `bench migrate`.
    """
    from skyengpro_brand.apply_branding import APP_NAME

    ws = frappe.get_single("Website Settings")
    ws.app_name = APP_NAME
    ws.brand_image = "/assets/skyengpro_brand/brand/skyengpro/logo_horizontal_color_400px.png"
    ws.favicon     = "/assets/skyengpro_brand/brand/skyengpro/icon_mark_32px.png"
    ws.splash_image = "/assets/skyengpro_brand/brand/skyengpro/logo_tagline_color_800px.png"
    ws.save(ignore_permissions=True)


def apply_navbar_settings():
    """Set the navbar logo to the COLOR variant.

    The login page reads `Navbar Settings.app_logo` and renders it on a
    light background — the white variant was invisible there. The color
    logo works on both the dark desk navbar and the light login card.
    For users who want a true white logo on dark navbar, brand_loader.js
    can be extended to swap based on theme.
    """
    ns = frappe.get_single("Navbar Settings")
    ns.app_logo = "/assets/skyengpro_brand/brand/skyengpro/logo_horizontal_color_400px.png"
    ns.save(ignore_permissions=True)


def apply_system_settings():
    """Set System Settings.app_name from apply_branding.APP_NAME (single
    source of truth). System Settings.app_name controls the browser tab
    title and a few other places."""
    from skyengpro_brand.apply_branding import APP_NAME

    ss = frappe.get_single("System Settings")
    ss.app_name = APP_NAME
    ss.save(ignore_permissions=True)


# ─────────────────────────────────────────────────────────────
# Insights "SkyEngPro Overview" dashboard
# ─────────────────────────────────────────────────────────────

OVERVIEW_DASHBOARD_TITLE = "SkyEngPro Overview"
OVERVIEW_DATA_SOURCE = "Site DB"

# item_type uses Insights v2 widget keys (Bar / Number / Pie / Line / ...).
# options must include {"query": "QRY-..."} plus the column bindings the widget
# needs. The 20-column grid layout matches frontend/src/dashboard/VueGridLayout.
OVERVIEW_QUERIES = [
    {
        "title": "Headcount by Department",
        "sql": (
            "SELECT COALESCE(department, '(Unassigned)') AS department, "
            "COUNT(*) AS employees "
            "FROM `tabEmployee` WHERE status='Active' "
            "GROUP BY department ORDER BY employees DESC"
        ),
        "item_type": "Bar",
        "x_col": "department",
        "y_col": "employees",
        "layout": {"x": 0, "y": 0, "w": 20, "h": 10},
    },
    {
        "title": "Top 10 Designations",
        "sql": (
            "SELECT COALESCE(designation, '(Unspecified)') AS designation, "
            "COUNT(*) AS employees "
            "FROM `tabEmployee` WHERE status='Active' "
            "GROUP BY designation ORDER BY employees DESC LIMIT 10"
        ),
        "item_type": "Bar",
        "x_col": "designation",
        "y_col": "employees",
        "layout": {"x": 0, "y": 10, "w": 20, "h": 10},
    },
    {
        "title": "Active Employees",
        "sql": (
            "SELECT COUNT(*) AS active_employees "
            "FROM `tabEmployee` WHERE status='Active'"
        ),
        "item_type": "Number",
        "value_col": "active_employees",
        "layout": {"x": 0, "y": 20, "w": 4, "h": 4},
    },
    {
        "title": "Headcount by Gender",
        "sql": (
            "SELECT COALESCE(gender, '(Unspecified)') AS gender, "
            "COUNT(*) AS employees "
            "FROM `tabEmployee` WHERE status='Active' "
            "GROUP BY gender ORDER BY employees DESC"
        ),
        "item_type": "Pie",
        "x_col": "gender",
        "y_col": "employees",
        "layout": {"x": 4, "y": 20, "w": 8, "h": 8},
    },
    {
        "title": "Sales Invoiced (last 12 months)",
        "sql": (
            "SELECT DATE_FORMAT(posting_date, '%Y-%m') AS month, "
            "SUM(grand_total) AS invoiced "
            "FROM `tabSales Invoice` WHERE docstatus=1 "
            "AND posting_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH) "
            "GROUP BY month ORDER BY month"
        ),
        "item_type": "Line",
        "x_col": "month",
        "y_col": "invoiced",
        "layout": {"x": 12, "y": 20, "w": 8, "h": 8},
    },
]


def ensure_overview_dashboard():
    """Create the SkyEngPro Overview dashboard if it doesn't exist.

    Idempotent: a no-op when the dashboard already exists, so manual edits
    in the UI survive `bench migrate`. Use `force_rebuild_overview_dashboard`
    to regenerate from scratch (will discard any UI edits).
    """
    if not frappe.db.exists("DocType", "Insights Dashboard"):
        frappe.logger("skyengpro").info("Insights not installed — skipping overview dashboard.")
        return
    if not frappe.db.exists("Insights Data Source", OVERVIEW_DATA_SOURCE):
        frappe.logger("skyengpro").info(
            "Insights data source %s not found — skipping overview dashboard.",
            OVERVIEW_DATA_SOURCE,
        )
        return
    if frappe.db.exists("Insights Dashboard", {"title": OVERVIEW_DASHBOARD_TITLE}):
        return  # already there — leave it (and any user edits) alone
    _build_overview_dashboard()


@frappe.whitelist()
def force_rebuild_overview_dashboard():
    """Wipe and recreate the SkyEngPro Overview dashboard. Discards user edits.

    Whitelisted so it can be triggered from a desk action or via:
      bench --site <site> execute skyengpro_brand.install.force_rebuild_overview_dashboard
    """
    if not frappe.db.exists("DocType", "Insights Dashboard"):
        frappe.throw("Insights app is not installed on this site.")
    if not frappe.db.exists("Insights Data Source", OVERVIEW_DATA_SOURCE):
        frappe.throw("Insights data source '%s' is missing." % OVERVIEW_DATA_SOURCE)

    existing = frappe.db.get_value(
        "Insights Dashboard", {"title": OVERVIEW_DASHBOARD_TITLE}, "name"
    )
    if existing:
        frappe.delete_doc(
            "Insights Dashboard", existing, force=1, ignore_permissions=True
        )
    for spec in OVERVIEW_QUERIES:
        for qname in frappe.db.get_all(
            "Insights Query", filters={"title": spec["title"]}, pluck="name"
        ):
            for cname in frappe.db.get_all(
                "Insights Chart", filters={"query": qname}, pluck="name"
            ):
                frappe.delete_doc(
                    "Insights Chart", cname, force=1, ignore_permissions=True
                )
            frappe.delete_doc(
                "Insights Query", qname, force=1, ignore_permissions=True
            )
    frappe.db.commit()
    return _build_overview_dashboard()


def _build_overview_dashboard():
    import json
    import random

    dash = frappe.new_doc("Insights Dashboard")
    dash.title = OVERVIEW_DASHBOARD_TITLE
    dash.is_public = 1
    dash.insert(ignore_permissions=True)

    for spec in OVERVIEW_QUERIES:
        q = frappe.new_doc("Insights Query")
        q.title = spec["title"]
        q.data_source = OVERVIEW_DATA_SOURCE
        q.is_native_query = 1
        q.sql = spec["sql"]
        q.status = "Pending Execution"
        q.insert(ignore_permissions=True)

        opts = {"query": q.name, "title": spec["title"]}
        t = spec["item_type"]
        if t in ("Bar", "Line", "Scatter", "Mixed Axis", "Row"):
            opts["xAxis"] = [{"column": spec["x_col"]}]
            opts["yAxis"] = [{"column": spec["y_col"]}]
        elif t == "Pie":
            opts["xAxis"] = spec["x_col"]
            opts["yAxis"] = spec["y_col"]
        elif t == "Number":
            opts["column"] = spec["value_col"]

        dash.append("items", {
            "item_id": int(random.random() * 1000000),
            "item_type": t,
            "options": json.dumps(opts),
            "layout": json.dumps(spec["layout"]),
        })

    dash.save(ignore_permissions=True)

    # Pre-warm: run each query once so the dashboard renders data immediately.
    for spec in OVERVIEW_QUERIES:
        qname = frappe.db.get_value(
            "Insights Query", {"title": spec["title"]}, "name"
        )
        if not qname:
            continue
        try:
            frappe.get_doc("Insights Query", qname).fetch_results()
        except Exception as exc:
            frappe.logger("skyengpro").warning(
                "Failed to pre-warm Insights Query %s: %s", qname, exc
            )

    frappe.db.commit()
    frappe.logger("skyengpro").info("Built Insights Overview dashboard %s", dash.name)
    return {"name": dash.name, "title": dash.title}
