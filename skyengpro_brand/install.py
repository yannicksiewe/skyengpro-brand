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

    # 2. Module Profiles + custom roles + default-profile reconciliation.
    #    Order matters: custom roles must exist BEFORE any DocPerm or
    #    Workspace.roles row references them; default-profile attach
    #    must run AFTER setup_module_profiles creates the profile docs.
    from skyengpro_brand.setup_roles import (
        apply_default_profile_to_existing,
        ensure_custom_roles,
        setup_module_profiles,
        sync_all_users_profiles,
    )
    ensure_custom_roles()
    setup_module_profiles()
    apply_default_profile_to_existing()
    sync_all_users_profiles()

    # 3. Desk & Workspace Permissions
    from skyengpro_brand.setup_permissions import setup_all_permissions
    setup_all_permissions()

    # 3b. Salary Slip leak fix: User -> Employee User Permission for
    #     every user with a linked Employee. ESS's if_owner doesn't
    #     cover list/report/REST — User Permission does. Runs after
    #     module profiles so role-related setup is complete.
    from skyengpro_brand.user_lifecycle import ensure_user_employee_permissions
    ensure_user_employee_permissions()

    # 3c. Wave 2: field-level permlevel gates on Project + Company +
    #     Employee. Hides Costing/More Info tabs on Project, the
    #     Accounts/Buying-Selling/Stock subtabs on Company, and the
    #     Salary tab on Employee from regular users. Unlocked
    #     per-user via custom roles (Project Costing Viewer / Project
    #     More Info Viewer) or via existing core roles (Accounts User
    #     / Sales User / HR User).
    from skyengpro_brand.field_perms import apply_field_permlevels
    apply_field_permlevels()

    # 3d. Wave 2.5: Custom DocPerm write-strip. Permlevel hides salary
    #     fields from the form but doesn't block writes via REST API
    #     against permlevel-0 fields the role still has write on.
    #     Force write=0 on (Employee, ESS) and (Company, every
    #     non-finance role) so the only write surface left is what
    #     the platform admin explicitly grants.
    from skyengpro_brand.docperm_lockdown import apply_docperm_lockdowns
    apply_docperm_lockdowns()

    # 4. Performance indexes for capacity-planning aggregations
    ensure_capacity_indexes()

    # 5. Workspace shortcuts for the Employee Capacity Planning report
    ensure_capacity_workspace_shortcuts()

    # 6. Insights "SkyEngPro Overview" dashboard (create only if missing —
    #    user edits in the UI are preserved across migrations).
    ensure_overview_dashboard()

    # 7. Multi-tenant scope: ensure custom `company` field exists on the
    #    shared masters and backfill NULL rows so existing data is tagged
    #    to a tenant. Wired into permission_query_conditions via hooks.py.
    ensure_tenant_company_fields()

    # 8. Per-user Project scope: backfill existing projects so their
    #    creator is in the Users child table. Without this, projects
    #    that pre-date this release become invisible to their creators
    #    (project_query's owner clause covers them, but the canonical
    #    Users tab is empty — confusing UX).
    backfill_project_creator_membership()

    # 9. Capacity Planning report — restrict to managers only. The
    #    report ships with `Projects User` + `HR User` roles which
    #    would let any regular employee see capacity for the whole
    #    org (peer salaries are not in this report, but allocation
    #    + utilization is sensitive scheduling info).
    restrict_capacity_planning_report()

    # 10. Project Setup doctypes + cross-project reports — strip
    #     Projects User / Employee / ESS access. These reports
    #     aggregate across ALL projects (not scoped per-user) and the
    #     setup doctypes (Activity Type / Cost, Project Type, Project
    #     Update) are admin-managed master data that regular users
    #     shouldn't be editing.
    restrict_project_setup_and_reports()

    # 11. Project dashboard chart — gate the only chart on the
    #     `Project` Dashboard (Project Summary, sourced from the
    #     same-named report we just locked) so the dashboard
    #     renders empty for non-managers. Frappe's Dashboard
    #     doctype has no `roles` table, so chart-level gating is
    #     the only handle.
    restrict_project_dashboard_chart()

    # 12. Self Service workspace — dedicated ESS entry point with
    #     Leave Application, Salary Slip, Expense Claim shortcuts.
    #     Lives under module=Setup so it's visible to every user
    #     regardless of which Module Profile gates HR / Payroll.
    #     Also cleans up the same shortcuts from Home (where an
    #     earlier release placed them).
    ensure_self_service_workspace()

    # 13. Self Service desktop icon — adds a top-level card on
    #     /desk's apps grid. The grid renders from tabDesktop Icon
    #     (standard=1, hidden=0, no parent_icon), not from the
    #     add_to_apps_screen hook.
    ensure_self_service_desktop_icon()

    # 14. ESS workflow plumbing — all the bits that make Apply for
    #     Leave / Submit Expense / Employee Advance actually work
    #     for a regular employee:
    #       a. HR Settings: allow employees to file backdated leave
    #          (without this, only Administrator can submit a leave
    #          for any past date — useless for sick-leave workflows)
    #       b. ensure read=1 on Custom DocPerm for ESS on
    #          Account/Currency/Mode of Payment/Cost Center so the
    #          form autocomplete doesn't die with "Insufficient
    #          Permission for X"
    #       c. Backfill Employee Self Service role onto every user
    #          that already has Employee role — DEFAULT_USER_ROLES
    #          covers new users via on_user_after_insert, but
    #          existing users created before this release are
    #          missing it.
    ensure_hr_settings_allow_backdated_leave()
    ensure_ess_read_doctype_perms()
    backfill_employee_self_service_role()

    frappe.db.commit()
    frappe.logger("skyengpro").info("SkyEngPro setup: complete.")


# ─────────────────────────────────────────────────────────────
# Multi-tenant scope: company custom field + backfill
# ─────────────────────────────────────────────────────────────

# Maps a Company name to a regex of letterhead names that belong to it.
# Used during the one-shot Letter Head backfill — letterheads created
# AFTER this install are tagged through the UI / before_insert hook.
_LETTERHEAD_NAME_TO_COMPANY = {
    "MC Capital":                  r"^MC Capital",
    "ALI Capital":                 r"^ALI Capital",
    "adorsys":                     r"^adorsys",
    "Clemios Sarl":                r"^Clemios",
    # Anything else stays NULL (treated as "shared/global" — the
    # Letter Head scope intentionally allows that).
}

# Default tenant for legacy rows that have no other clue. Matches the
# COMPANY_TO_BRAND default from theme.py.
_BACKFILL_DEFAULT_COMPANY = "Sky Engineering Professional"


def ensure_tenant_company_fields():
    """Create the Custom Field `company` on Customer / Supplier / Item /
    Letter Head, and backfill existing rows where the field is NULL.

    Idempotent — re-running this on every migrate is safe and cheap.
    """
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field

    targets = ["Customer", "Supplier", "Item", "Letter Head"]
    for dt in targets:
        df = {
            "fieldname": "company",
            "label": "Company",
            "fieldtype": "Link",
            "options": "Company",
            # Place near the top so it's visible at-a-glance on the form.
            "insert_after": "naming_series" if dt != "Letter Head" else None,
            "in_list_view": 1,
            "in_standard_filter": 1,
            "description": "Tenant-scoping field — controls who can see and edit this record across multiple Companies on the same site.",
        }
        # `insert_after` for Letter Head: it doesn't have naming_series,
        # so let Frappe place it at the bottom of the form by leaving it None.
        if df.get("insert_after") is None:
            df.pop("insert_after")

        try:
            create_custom_field(dt, df)
            frappe.logger("skyengpro").info("Custom Field 'company' ensured on %s", dt)
        except Exception:
            frappe.logger("skyengpro").exception("Failed to add 'company' Custom Field on %s", dt)

    # Backfill NULL company values so existing data shows up under the
    # right tenant after the permission filter is wired up.
    _backfill_letter_head_company()
    _backfill_default_company(["Customer", "Supplier", "Item"])

    # Make sure the company column is indexed — list views filter by it
    # on every query, so a missing index turns into a table scan.
    for dt in targets:
        _ensure_index(dt, "company")


def _backfill_letter_head_company():
    """Tag existing Letter Heads by name pattern. Anything not matching a
    pattern stays NULL = shared across all tenants."""
    import re
    rows = frappe.db.get_all(
        "Letter Head",
        filters={"company": ["in", ["", None]]},
        fields=["name"],
    )
    for r in rows:
        for company, pattern in _LETTERHEAD_NAME_TO_COMPANY.items():
            if re.match(pattern, r.name, flags=re.IGNORECASE):
                frappe.db.set_value("Letter Head", r.name, "company", company,
                                    update_modified=False)
                break


def _backfill_default_company(doctypes: list):
    """For Customer / Supplier / Item: any row with NULL company gets
    tagged to the default tenant. Without this, the strict scope filter
    would hide every legacy row immediately after rollout.

    Skip if the default Company doesn't exist on this site (fresh install
    case — there's nothing to backfill yet either way).
    """
    if not frappe.db.exists("Company", _BACKFILL_DEFAULT_COMPANY):
        return
    for dt in doctypes:
        try:
            frappe.db.sql(
                f"UPDATE `tab{dt}` SET company=%s "
                f"WHERE company IS NULL OR company=''",
                (_BACKFILL_DEFAULT_COMPANY,),
            )
        except Exception:
            frappe.logger("skyengpro").exception("Backfill failed for %s", dt)


def _ensure_index(doctype: str, fieldname: str):
    """Best-effort: add a non-unique index on (fieldname). Frappe stores
    this in the database, not in DocType meta — running it idempotently
    is fine because MySQL/MariaDB ignores CREATE INDEX IF NOT EXISTS
    via the existence check below."""
    try:
        frappe.db.add_index(doctype, [fieldname])
    except Exception:
        # Index already exists, or we don't have ALTER privilege.
        pass


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


SELF_SERVICE_WORKSPACE = "Self Service"
SELF_SERVICE_SHORTCUTS = [
    # (link_to, label, doc_view, color)
    ("Leave Application", "Apply for Leave",      "New",  "Green"),
    ("Salary Slip",       "My Salary Slips",      "List", "Blue"),
    ("Expense Claim",     "Submit Expense",       "New",  "Orange"),
]
SELF_SERVICE_DESKTOP_ICON = {
    "name":       SELF_SERVICE_WORKSPACE,
    "label":      SELF_SERVICE_WORKSPACE,
    "app":        "skyengpro_brand",
    "icon_type":  "App",
    "link_type":  "External",
    "link":       "/desk/self-service",
    "logo_url":   "/assets/skyengpro_brand/brand/skyengpro/icon_mark_512px.png",
    "standard":   1,
    "hidden":     0,
    "idx":        50,
}


def ensure_self_service_desktop_icon():
    """Add a top-level 'Self Service' card to /desk.

    The dashboard apps grid is built from `bootinfo.desktop_icons`
    (tabDesktop Icon, standard=1, hidden=0, no parent_icon). Apps
    like Framework / Frappe HR / Organization each ship one of
    these. Adding our own gives Self Service a one-click entry from
    the desktop, matching the visual treatment of every other
    top-level app card.

    Idempotent: existing Desktop Icon row is patched to match
    SELF_SERVICE_DESKTOP_ICON; otherwise inserted fresh.
    """
    spec = SELF_SERVICE_DESKTOP_ICON
    if frappe.db.exists("Desktop Icon", spec["name"]):
        for k, v in spec.items():
            if k == "name":
                continue
            frappe.db.set_value(
                "Desktop Icon", spec["name"], k, v, update_modified=False
            )
        return
    try:
        doc = frappe.get_doc({"doctype": "Desktop Icon", **spec})
        doc.insert(ignore_permissions=True)
    except Exception:
        frappe.logger("skyengpro").exception(
            "ensure_self_service_desktop_icon: insert failed"
        )


def ensure_hr_settings_allow_backdated_leave():
    """Set HR Settings.restrict_backdated_leave_application = 0.

    Out of the box HRMS restricts backdated leave to Administrator.
    For us employees self-file leave (sick days, emergency leave
    applied retroactively), so we relax the gate. Idempotent.
    """
    try:
        hr = frappe.get_single("HR Settings")
        if hr.get("restrict_backdated_leave_application"):
            hr.restrict_backdated_leave_application = 0
            hr.save(ignore_permissions=True)
            frappe.logger("skyengpro").info(
                "HR Settings: restrict_backdated_leave_application -> 0"
            )
    except Exception:
        frappe.logger("skyengpro").exception(
            "ensure_hr_settings_allow_backdated_leave failed"
        )


def ensure_ess_read_doctype_perms():
    """Force read=1 on Custom DocPerm rows for Employee Self Service
    on Account / Currency / Mode of Payment / Cost Center.

    These doctypes back the autocomplete fields on Expense Claim and
    Employee Advance. If a Custom DocPerm exists with read=0 (which
    is what we observe in this site post-rollouts) the form raises
    `Insufficient Permission for X`. Force read=1 idempotently — if
    no Custom DocPerm exists at permlevel 0 yet, insert a minimal
    read-only row so the gate is explicit.
    """
    from skyengpro_brand.config import ESS_READ_DOCTYPES

    role = "Employee Self Service"
    if not frappe.db.exists("Role", role):
        return
    for dt in ESS_READ_DOCTYPES:
        if not frappe.db.exists("DocType", dt):
            continue
        existing = frappe.db.get_value(
            "Custom DocPerm",
            {"parent": dt, "role": role, "permlevel": 0},
            "name",
        )
        if existing:
            frappe.db.set_value(
                "Custom DocPerm", existing, "read", 1, update_modified=False
            )
            continue
        try:
            frappe.get_doc({
                "doctype":     "Custom DocPerm",
                "parent":      dt,
                "parenttype":  "DocType",
                "parentfield": "permissions",
                "role":        role,
                "permlevel":   0,
                "read":        1,
                "write":       0,
                "create":      0,
                "delete":      0,
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.logger("skyengpro").exception(
                "ensure_ess_read_doctype_perms: insert failed for %s/%s",
                dt, role,
            )


def backfill_employee_self_service_role():
    """Make sure every user with the Employee role also has the
    Employee Self Service role.

    DEFAULT_USER_ROLES adds Employee Self Service to brand-new users
    via the on_user_after_insert hook, but pre-existing users
    (created before this app was installed or before that hook was
    wired) are stuck with just Employee — and Employee on its own
    has no read on Account/Currency, so the Expense Claim form
    bombs. This backfill plugs that gap. Idempotent.
    """
    rows = frappe.db.sql(
        """
        SELECT DISTINCT hr.parent AS user
        FROM `tabHas Role` hr
        WHERE hr.parenttype = 'User'
          AND hr.role = 'Employee'
          AND hr.parent NOT IN ('Administrator', 'Guest')
          AND NOT EXISTS (
            SELECT 1 FROM `tabHas Role` hr2
            WHERE hr2.parent = hr.parent
              AND hr2.parenttype = 'User'
              AND hr2.role = 'Employee Self Service'
          )
        """,
        as_dict=True,
    )
    if not rows:
        return
    for r in rows:
        try:
            frappe.db.sql(
                """
                INSERT INTO `tabHas Role`
                  (name, creation, modified, modified_by, owner,
                   docstatus, idx, role, parent, parenttype, parentfield)
                VALUES
                  (UUID(), NOW(), NOW(), 'Administrator', 'Administrator',
                   0, 1, 'Employee Self Service', %s, 'User', 'roles')
                """,
                (r["user"],),
            )
        except Exception:
            frappe.logger("skyengpro").exception(
                "backfill_employee_self_service_role: failed for %s", r["user"]
            )
    frappe.logger("skyengpro").info(
        "backfill_employee_self_service_role: added ESS role to %d user(s)",
        len(rows),
    )


def ensure_self_service_workspace():
    """Create a public 'Self Service' workspace with three ESS
    shortcuts: Apply for Leave / My Salary Slips / Submit Expense.

    Why a dedicated workspace and not just shortcuts on Home: HR +
    Payroll modules are blocked at the Module Profile level so the
    HR / Payroll workspace sidebars are hidden, but the Employee
    role still grants if_owner DocPerm on Leave Application /
    Salary Slip / Expense Claim. A dedicated 'Self Service'
    workspace under the (unblocked) `Setup` module gives users a
    clear, isolated entry point without surfacing any of the rest
    of the HR app's surface area.

    `doc_view=New` opens the create form directly; `List` opens a
    filtered list (User Permission scopes Salary Slip to the user's
    own Employee record).

    Idempotent: workspace is created on first run; subsequent runs
    upsert any missing shortcut rows + content blocks. If the
    workspace was created earlier and an admin edited it in the UI,
    we only ADD missing pieces — we don't blow away their layout.

    Side-effect: removes the same shortcuts from the Home workspace
    if they were added there by an earlier release.
    """
    import json as _json

    # 1) Cleanup: remove the ESS shortcuts from Home (placed there
    #    by an earlier release before we settled on a dedicated
    #    workspace). Idempotent — does nothing if Home is already
    #    clean.
    _purge_home_ess_shortcuts()

    # 2) Make sure the workspace exists.
    if not frappe.db.exists("Workspace", SELF_SERVICE_WORKSPACE):
        ws = frappe.new_doc("Workspace")
        ws.name = SELF_SERVICE_WORKSPACE
        ws.label = SELF_SERVICE_WORKSPACE
        ws.title = SELF_SERVICE_WORKSPACE
        # Setup is in the always-on module set (BASE_MODULES) so
        # every Module Profile keeps it unblocked. The workspace is
        # therefore visible in every user's sidebar regardless of
        # which other modules are gated.
        ws.module = "Setup"
        ws.public = 1
        ws.icon = "users"
        ws.content = "[]"
        ws.insert(ignore_permissions=True)

    ws = frappe.get_doc("Workspace", SELF_SERVICE_WORKSPACE)
    try:
        blocks = _json.loads(ws.content or "[]")
    except ValueError:
        blocks = []
    changed = False

    # 3) Header block for the page (only inserted once).
    has_header = any(b.get("type") == "header" for b in blocks)
    if not has_header:
        blocks.insert(0, {
            "type": "header",
            "data": {
                "text": "<span class=\"h4\"><b>Self Service</b></span>",
                "col": 12,
            },
        })
        changed = True

    # 4) Add each shortcut child row + content block.
    for link_to, label, doc_view, color in SELF_SERVICE_SHORTCUTS:
        if not frappe.db.exists("DocType", link_to):
            continue

        has_row = any(
            (s.type == "DocType" and s.link_to == link_to)
            for s in (ws.shortcuts or [])
        )
        if not has_row:
            ws.append("shortcuts", {
                "type":     "DocType",
                "link_to":  link_to,
                "label":    label,
                "doc_view": doc_view,
                "color":    color,
            })
            changed = True

        already_rendered = any(
            b.get("type") == "shortcut" and b.get("data", {}).get("shortcut_name") == label
            for b in blocks
        )
        if not already_rendered:
            blocks.append({
                "type": "shortcut",
                "data": {"shortcut_name": label, "col": 4},
            })
            changed = True

    if changed:
        ws.content = _json.dumps(blocks)
        ws.save(ignore_permissions=True)
        frappe.logger("skyengpro").info(
            "ensure_self_service_workspace: synced Self Service workspace",
        )


def _purge_home_ess_shortcuts():
    """Remove the ESS shortcut rows + content blocks from the Home
    workspace. They were placed there by an earlier release before
    we settled on a dedicated 'Self Service' workspace. Idempotent.
    """
    import json as _json

    if not frappe.db.exists("Workspace", "Home"):
        return
    ws = frappe.get_doc("Workspace", "Home")
    ess_labels = {label for _link, label, _dv, _c in SELF_SERVICE_SHORTCUTS}
    # Also catch the older "Submit Expense Claim" label.
    ess_labels.add("Submit Expense Claim")

    # Drop matching shortcut child rows
    keep_shortcuts = [
        s for s in (ws.shortcuts or []) if s.label not in ess_labels
    ]
    removed_rows = len(ws.shortcuts or []) - len(keep_shortcuts)
    if removed_rows:
        ws.shortcuts = keep_shortcuts

    # Drop matching content blocks
    try:
        blocks = _json.loads(ws.content or "[]")
    except ValueError:
        blocks = []
    new_blocks = [
        b for b in blocks
        if not (
            b.get("type") == "shortcut"
            and b.get("data", {}).get("shortcut_name") in ess_labels
        )
    ]
    blocks_changed = len(blocks) != len(new_blocks)

    if removed_rows or blocks_changed:
        ws.content = _json.dumps(new_blocks)
        ws.save(ignore_permissions=True)
        frappe.logger("skyengpro").info(
            "_purge_home_ess_shortcuts: removed %d ESS shortcut row(s) + %d block(s) from Home",
            removed_rows, len(blocks) - len(new_blocks),
        )


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
        # tenant_scope.project_query joins to `tabProject User` on every
        # Project list view + Link autocomplete keystroke. Frappe doesn't
        # ship a parent+user index, so without this the EXISTS subquery
        # table-scans once project teams grow past a few hundred rows.
        ("tabProject User", "idx_skyeng_project_user_parent_user", ["parent", "user"]),
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


def restrict_capacity_planning_report():
    """Lock the Employee Capacity Planning report to manager roles.

    The report ships with `System Manager`, `Projects Manager`,
    `HR Manager`, **and** `Projects User` + `HR User` in its allowed
    roles. The two `User` roles cover every regular employee — any
    Projects User can run capacity-planning across the whole org.

    Idempotent: re-runnable on every migrate. Removes only the two
    over-permissive User roles; leaves any admin-added custom role
    (e.g. a future "Capacity Planner" role) intact.
    """
    REPORT = "Employee Capacity Planning"
    OVERREACHING_ROLES = ("Projects User", "HR User")

    if not frappe.db.exists("Report", REPORT):
        return

    removed = frappe.db.sql(
        """DELETE FROM `tabHas Role`
           WHERE parent = %s
             AND parenttype = 'Report'
             AND role IN %s""",
        (REPORT, OVERREACHING_ROLES),
    )
    if removed:
        frappe.logger("skyengpro").info(
            "restrict_capacity_planning_report: stripped Projects User + HR User"
        )


def restrict_project_setup_and_reports():
    """Lock down Project setup masters + cross-project Reports.

    Cross-project Reports (Project Summary, Daily/Timesheet Billing
    Summary, Project wise Stock Tracking, Delayed Tasks Summary)
    aggregate across the whole org — they don't honor our per-user
    Project scope. Force their `tabHas Role` to exactly the canonical
    manager set {Projects Manager, System Manager}.

    Why "force the canonical set" instead of "just DELETE the bad
    roles": Frappe's Report.is_permitted falls back to ref_doctype
    permissions when `tabHas Role` is empty. Two of these reports
    (Daily Timesheet Summary, Timesheet Billing Summary) ship with
    only over-permissive roles — DELETE-only would empty the table
    and the report would revert to "anyone with Timesheet read"
    (i.e. every Projects User and Employee). Setting the canonical
    set guarantees the gate stays in place.

    Setup doctypes (Activity Type, Activity Cost, Project Type,
    Project Update) are admin-managed master data — Projects User
    shouldn't be able to add new activity types from the form.
    Strip read/write/create/delete via Custom DocPerm override.

    Idempotent: DELETE-then-INSERT for reports; Custom DocPerm
    upsert for setup doctypes.
    """
    OVERREACHING_REPORTS = (
        "Daily Timesheet Summary",
        "Delayed Tasks Summary",
        "Project Summary",
        "Project wise Stock Tracking",
        "Timesheet Billing Summary",
    )
    REPORT_CANONICAL_ROLES = ("Projects Manager", "System Manager")
    SETUP_DOCTYPES = ("Activity Type", "Activity Cost", "Project Type", "Project Update")
    SETUP_ROLES_TO_LOCK = ("Projects User", "Employee", "Employee Self Service")

    # 1) Force each cross-project Report's role list to exactly the
    #    canonical manager set. Wipe first, then ensure each role row
    #    exists. This closes the empty-roles fallback hole.
    #
    #    Direct SQL INSERT instead of `frappe.get_doc().insert()`:
    #    Frappe's Has Role validate dedupes on (parent, role) ignoring
    #    parenttype. We add a Dashboard Chart Has Role row with
    #    parent='Project Summary' elsewhere — the matching Report
    #    row collides at validate time and the insert silently fails.
    #    SQL bypasses that check; the parent+parenttype+parentfield
    #    uniquely identifies the row in the database.
    for report in OVERREACHING_REPORTS:
        if not frappe.db.exists("Report", report):
            continue
        frappe.db.sql(
            """DELETE FROM `tabHas Role`
               WHERE parenttype = 'Report' AND parent = %s""",
            (report,),
        )
        for role in REPORT_CANONICAL_ROLES:
            if not frappe.db.exists("Role", role):
                continue
            try:
                frappe.db.sql(
                    """INSERT INTO `tabHas Role`
                         (name, creation, modified, modified_by, owner,
                          docstatus, idx, role, parent, parenttype,
                          parentfield)
                       VALUES
                         (UUID(), NOW(), NOW(), 'Administrator',
                          'Administrator', 0, 1, %s, %s, 'Report',
                          'roles')""",
                    (role, report),
                )
            except Exception:
                frappe.logger("skyengpro").exception(
                    "restrict_project_setup_and_reports: Has Role insert failed for %s/%s",
                    report, role,
                )

    # 2) Lock setup doctypes via Custom DocPerm override (read=0, all
    #    operations 0). Mirrors docperm_lockdown's force-no-write
    #    pattern but also strips read.
    for dt in SETUP_DOCTYPES:
        if not frappe.db.exists("DocType", dt):
            continue
        for role in SETUP_ROLES_TO_LOCK:
            if not frappe.db.exists("Role", role):
                continue
            existing = frappe.db.get_value(
                "Custom DocPerm",
                {"parent": dt, "role": role, "permlevel": 0},
                "name",
            )
            if existing:
                for flag in ("read", "write", "create", "delete"):
                    frappe.db.set_value(
                        "Custom DocPerm", existing, flag, 0,
                        update_modified=False,
                    )
            else:
                try:
                    frappe.get_doc({
                        "doctype":     "Custom DocPerm",
                        "parent":      dt,
                        "parenttype":  "DocType",
                        "parentfield": "permissions",
                        "role":        role,
                        "permlevel":   0,
                        "read":        0,
                        "write":       0,
                        "create":      0,
                        "delete":      0,
                        "if_owner":    0,
                    }).insert(ignore_permissions=True)
                except Exception:
                    frappe.logger("skyengpro").exception(
                        "restrict_project_setup_and_reports: failed for %s/%s",
                        dt, role,
                    )
    frappe.db.commit()


def restrict_project_dashboard_chart():
    """Gate the `Project Summary` Dashboard Chart to Projects Manager.

    The `Project` Dashboard (module=Projects) contains a single
    chart, `Project Summary`, sourced from the like-named Report.
    Frappe's Dashboard doctype has no `roles` child table — so
    even though the report is locked, the dashboard URL itself
    is reachable from the module sidebar. Adding roles to the
    chart makes it disappear for users without those roles, so
    the dashboard renders empty.

    Idempotent: skipped if the role row already exists.
    """
    CHART = "Project Summary"
    ROLES = ("Projects Manager",)

    if not frappe.db.exists("Dashboard Chart", CHART):
        return

    for role in ROLES:
        if not frappe.db.exists("Role", role):
            continue
        existing = frappe.db.exists(
            "Has Role",
            {"parent": CHART, "parenttype": "Dashboard Chart", "role": role},
        )
        if existing:
            continue
        try:
            frappe.get_doc({
                "doctype":     "Has Role",
                "parent":      CHART,
                "parenttype":  "Dashboard Chart",
                "parentfield": "roles",
                "role":        role,
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.logger("skyengpro").exception(
                "restrict_project_dashboard_chart: failed for role %s", role,
            )


def backfill_project_creator_membership():
    """Ensure every existing Project has its `owner` listed in the
    `users` child table. Idempotent — safe to re-run on every migrate.

    The before_insert hook (auto_add_project_creator) handles new
    projects going forward; this function covers the pre-existing
    rows so the Project visibility flip doesn't strand them.

    Skipped for projects whose owner is Administrator/Guest — those
    are bench-driven and don't need a UX-facing membership row.
    """
    rows = frappe.db.sql(
        """
        SELECT p.name, p.owner
        FROM `tabProject` p
        WHERE p.owner IS NOT NULL
          AND p.owner NOT IN ('Administrator', 'Guest')
          AND NOT EXISTS (
            SELECT 1 FROM `tabProject User` pu
            WHERE pu.parent = p.name AND pu.user = p.owner
          )
        """,
        as_dict=True,
    )
    added = 0
    for r in rows:
        try:
            proj = frappe.get_doc("Project", r["name"])
            proj.append("users", {"user": r["owner"], "welcome_email_sent": 1})
            proj.save(ignore_permissions=True)
            added += 1
        except Exception:
            frappe.logger("skyengpro").exception(
                "backfill_project_creator_membership: failed for %s", r["name"]
            )
    frappe.logger("skyengpro").info(
        "backfill_project_creator_membership: added owner to users on %d project(s)", added
    )


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
