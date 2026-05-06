"""User lifecycle — auto-attach default Module Profile + roles on
new-user creation, and reconcile the User → Employee permission that
plugs the Salary Slip cross-employee leak.

Background — the leak this closes
─────────────────────────────────
Frappe's "Employee Self Service" role gates Salary Slip / Leave
Application / Expense Claim with `if_owner=1`. That flag protects the
form view (`/app/salary-slip/<name>`) but NOT list views, REST
(`/api/resource/Salary Slip?filters=...`), or report builder — those
paths consult **User Permissions**. Without a User Permission row
linking each User to their Employee record, an ESS user can list
peer payslips by employee name and read net pay.

Fix: for every User that has a matching Employee (linked by
Employee.user_id), create a User Permission with allow=Employee,
for_value=<employee.name>, applicable_for=NULL ("apply to all
doctypes"). Frappe then forces every list/report/REST query of a
doctype that has an `employee` link to be filtered to that Employee.

Carve-out for HR-role users
───────────────────────────
The leak fix targets Employee Self Service users who must NOT see
peers. But users with HR Manager / HR User / System Manager roles
are explicitly authorised to see every employee — Payroll Entry,
bulk Salary Slip generation, Leave approvals, etc. all break when
their visibility is scoped to a single Employee. So we skip UP
creation (and proactively delete existing rows) for those roles.
Their self-service surfaces (own Leave Application / Expense Claim)
remain functional via Employee.user_id matching, which doesn't
depend on User Permission.

Idempotent — re-running on every migrate is safe and cheap.
"""
import frappe

from skyengpro_brand.config import DEFAULT_MODULE_PROFILE
from skyengpro_brand.setup_roles import (
    ensure_user_has_default_roles,
    sync_user_module_profile,
)


# Users with any of these roles bypass the User → Employee permission
# scoping — their job requires cross-employee visibility.
HR_BYPASS_ROLES = {"HR Manager", "HR User", "System Manager"}


def _user_sees_all_employees(user: str) -> bool:
    """Return True if the user has a role that grants legitimate
    cross-employee visibility. Such users must NOT receive a
    User Permission Employee→self row, since it would clamp every
    Employee-linked query to a single record and break HR/payroll
    workflows."""
    if user in ("Administrator",):
        return True
    roles = set(frappe.get_roles(user) or [])
    return bool(roles & HR_BYPASS_ROLES)


# ─────────────────────────────────────────────────────────────
# doc_event: User.after_insert
# ─────────────────────────────────────────────────────────────

def on_user_after_insert(doc, method=None):
    """User.after_insert — attach default profile + roles to a fresh
    System User. Skips bench-driven creations (Administrator, Guest)
    and Website Users (portal-only, no desk).

    Runs synchronously inside the User insert transaction — by the
    time the new user logs in for the first time, their workspace
    sidebar is already shaped.
    """
    if doc.name in ("Administrator", "Guest"):
        return
    if getattr(doc, "user_type", None) != "System User":
        return
    # If an admin assigned a profile during creation, respect it.
    if getattr(doc, "module_profile", None):
        return
    # Skip if the new user is being created with System Manager role
    # (probably another platform admin — they need full visibility).
    role_names = {r.role for r in (doc.roles or [])}
    if "System Manager" in role_names:
        return
    if not frappe.db.exists("Module Profile", DEFAULT_MODULE_PROFILE):
        return

    doc.db_set("module_profile", DEFAULT_MODULE_PROFILE, update_modified=False)
    ensure_user_has_default_roles(doc.name)
    sync_user_module_profile(doc.name)


# ─────────────────────────────────────────────────────────────
# Salary Slip leak fix
# ─────────────────────────────────────────────────────────────

def ensure_user_employee_permissions():
    """Create User Permission `User → Employee` (apply_to_all_doctypes)
    for every user that has a linked Employee record.

    This is the canonical Frappe answer to "ESS users can list peer
    payslips" — the if_owner flag doesn't cover list/report/REST, but
    User Permission does, applied site-wide.

    Idempotent: skip if a permission already exists for that
    (user, allow=Employee, for_value=<employee>) tuple.
    """
    rows = frappe.db.sql(
        """
        SELECT name, user_id
        FROM `tabEmployee`
        WHERE user_id IS NOT NULL AND user_id != ''
          AND user_id NOT IN ('Administrator', 'Guest')
        """,
        as_dict=True,
    )
    created = 0
    skipped_hr = 0
    for r in rows:
        # HR-role users bypass the scoping. The leak protection
        # exists to stop ESS users from listing peer payslips —
        # users who are explicitly authorised to see all employees
        # (HR Manager / HR User / System Manager) must keep that
        # visibility, otherwise their Employee list / Payroll Entry
        # / bulk Salary Slip flows return only themselves.
        if _user_sees_all_employees(r["user_id"]):
            skipped_hr += 1
            continue
        existing = frappe.db.exists(
            "User Permission",
            {
                "user":      r["user_id"],
                "allow":     "Employee",
                "for_value": r["name"],
            },
        )
        if existing:
            continue
        try:
            frappe.get_doc({
                "doctype":                "User Permission",
                "user":                   r["user_id"],
                "allow":                  "Employee",
                "for_value":              r["name"],
                "apply_to_all_doctypes":  1,
                "is_default":             1,
            }).insert(ignore_permissions=True)
            created += 1
        except Exception:
            frappe.logger("skyengpro").exception(
                "ensure_user_employee_permissions: failed for %s -> %s",
                r["user_id"], r["name"],
            )
    frappe.db.commit()
    frappe.logger("skyengpro").info(
        "ensure_user_employee_permissions: created %d row(s), skipped %d HR-role user(s)",
        created, skipped_hr,
    )


def cleanup_hr_user_employee_permissions():
    """Remove `User Permission Employee → self` rows that already
    exist for users who now have HR Manager / HR User / System
    Manager. These rows were created by an earlier pass (when the
    user only had ESS roles) and stayed behind when the user was
    promoted to HR — silently breaking their Employee list view.

    Idempotent: re-running on every migrate is safe and cheap.
    """
    rows = frappe.db.sql(
        """
        SELECT up.name, up.user, up.for_value
        FROM `tabUser Permission` up
        WHERE up.allow = 'Employee'
          AND up.apply_to_all_doctypes = 1
          AND up.user NOT IN ('Administrator', 'Guest')
        """,
        as_dict=True,
    )
    deleted = 0
    for r in rows:
        if not _user_sees_all_employees(r["user"]):
            continue
        try:
            frappe.delete_doc(
                "User Permission", r["name"],
                force=1, ignore_permissions=True,
            )
            deleted += 1
        except Exception:
            frappe.logger("skyengpro").exception(
                "cleanup_hr_user_employee_permissions: delete failed for %s",
                r["name"],
            )
    if deleted:
        frappe.db.commit()
    frappe.logger("skyengpro").info(
        "cleanup_hr_user_employee_permissions: removed %d row(s)", deleted
    )


# ─────────────────────────────────────────────────────────────
# doc_event: Employee.after_insert / .on_update
# ─────────────────────────────────────────────────────────────

def block_self_edit_for_non_admins(doc, method=None):
    """User.validate — refuse self-edit (or self-elevation) by users
    without System Manager role.

    Frappe core has a hardcoded self-permission rule on the User
    doctype: `User.has_permission` returns True when
    `doc.name == frappe.session.user`, regardless of DocPerm. That
    means every authenticated user can save changes to her own User
    record (first_name, last_name, username, time_zone, etc.) —
    including identity-affecting fields. We block that at the
    validate layer.

    Allowed paths (NOT blocked):
      - Administrator + any user with System Manager role: full edit.
      - Brand-new user (`doc.is_new()`) — needed because the
        after_insert lifecycle path saves the doc once before any
        field-level guards apply.
      - Password resets and user-driven self-service flows that go
        through dedicated whitelisted methods
        (`frappe.core.doctype.user.user.update_password`, etc.) —
        those don't fire this validate hook because they bypass the
        full Document.save path.

    Blocked path:
      - Logged-in non-admin user clicks Save on her own User form.
        Frappe shows a permission error and the doc is not persisted.
    """
    if doc.is_new():
        return
    if frappe.session.user in ("Administrator", "Guest"):
        return
    if "System Manager" in (frappe.get_roles() or []):
        return
    if doc.name != frappe.session.user:
        # Editing someone else — DocPerm gates that. The block here
        # is specifically for the self-edit hardcoded bypass.
        return
    frappe.throw(
        "You cannot edit your own User profile. "
        "Ask a platform admin (System Manager) to make changes on "
        "your behalf.",
        title="Self-edit not allowed",
    )


def on_employee_save(doc, method=None):
    """Employee.after_insert / on_update — keep the User → Employee
    permission in sync when HR links/unlinks a User from an Employee.

    If the Employee gains a user_id, ensure the matching UP exists.
    If user_id changed from A to B, the old A→<emp> UP becomes stale —
    we don't proactively delete it (HR may revert the change), but
    the lookups go through the current `tabEmployee.user_id` so a
    stale UP just becomes a no-op for that user."""
    user_id = getattr(doc, "user_id", None)
    if not user_id or user_id in ("Administrator", "Guest"):
        return
    # HR Manager / HR User / System Manager need cross-employee
    # visibility — never scope them to a single Employee record.
    if _user_sees_all_employees(user_id):
        return
    existing = frappe.db.exists(
        "User Permission",
        {"user": user_id, "allow": "Employee", "for_value": doc.name},
    )
    if existing:
        return
    try:
        frappe.get_doc({
            "doctype":               "User Permission",
            "user":                  user_id,
            "allow":                 "Employee",
            "for_value":             doc.name,
            "apply_to_all_doctypes": 1,
            "is_default":            1,
        }).insert(ignore_permissions=True)
        frappe.logger("skyengpro").info(
            "on_employee_save: created User Permission %s -> %s", user_id, doc.name
        )
    except Exception:
        frappe.logger("skyengpro").exception(
            "on_employee_save: failed creating UP for %s -> %s", user_id, doc.name
        )
