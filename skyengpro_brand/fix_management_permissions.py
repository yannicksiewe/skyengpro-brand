"""
Fix management user permissions for Branda + Beltine + Willie.
Scripted so it can be re-run on any instance.

Fixes applied:
  1. Add missing roles for full management access
  2. Remove Employee-level User Permission restriction
  3. Update the "Finance + HR + Management" Role Profile
  4. Remove spurious all-zero "Employee Self Service" Custom DocPerms
     on Payroll doctypes (Salary Structure, Salary Component, Payroll Entry)
     — these block the permission resolver and prevent create/modify in the UI
  5. Clear permission caches
"""
import frappe

frappe.init(site="erp.skyengpro.com", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

MANAGEMENT_USERS = [
    "ewang.branda@skyengpro.com",
    "beltine.fuh@plooh.com",
    "willie.chieukam@skyengpro.com",
]

# ─── 1. Add missing roles for full management access ───
print("--- Adding missing roles ---")
EXTRA_ROLES = [
    "Purchase Master Manager",   # create Suppliers
    "Sales Master Manager",      # create Customers
    "Stock Manager",             # manage stock/warehouse
    "Insights User",             # Frappe Insights
    "Insights Admin",            # Frappe Insights admin
]

for email in MANAGEMENT_USERS:
    if not frappe.db.exists("User", email):
        print("  SKIP (not found): " + email)
        continue

    user = frappe.get_doc("User", email)
    existing_roles = [r.role for r in user.roles]
    added = []
    for role in EXTRA_ROLES:
        if role not in existing_roles and frappe.db.exists("Role", role):
            user.append("roles", {"role": role})
            added.append(role)
    if added:
        user.save(ignore_permissions=True)
        print("  " + email + ": added " + ", ".join(added))
    else:
        print("  " + email + ": already has all roles")

frappe.db.commit()

# ─── 2. Remove Employee User Permission for management users ───
# Management users need to see ALL employees, not just themselves
print("\n--- Removing Employee restriction ---")
ALL_NON_EMPLOYEE_USERS = MANAGEMENT_USERS + [
    "francis.pouatcha@gmail.com",
    "chrispain.yonga@skyengpro.com",
]

for email in ALL_NON_EMPLOYEE_USERS:
    perms = frappe.get_all("User Permission", filters={"user": email, "allow": "Employee"}, fields=["name"])
    for p in perms:
        frappe.delete_doc("User Permission", p.name, force=True, ignore_permissions=True)
    if perms:
        print("  Removed Employee restriction: " + email)

frappe.db.commit()

# ─── 3. Update the "Finance + HR + Management" Role Profile ───
print("\n--- Updating Role Profile ---")
profile_name = "Finance + HR + Management"
if frappe.db.exists("Role Profile", profile_name):
    rp = frappe.get_doc("Role Profile", profile_name)
    existing = [r.role for r in rp.roles]
    for role in EXTRA_ROLES:
        if role not in existing and frappe.db.exists("Role", role):
            rp.append("roles", {"role": role})
    rp.save(ignore_permissions=True)
    print("  Updated: " + profile_name + " (" + str(len(rp.roles)) + " roles)")

frappe.db.commit()

# ─── 4. Remove spurious "Employee Self Service" Custom DocPerms ───
# When a Custom DocPerm entry exists with ALL permissions = 0, Frappe's
# permission resolver still evaluates it.  On Payroll doctypes this caused
# Branda & Beltine to be unable to create/modify Salary Structures even
# though their HR Manager / System Manager roles grant full access.
print("\n--- Removing all-zero Employee Self Service Custom DocPerms ---")
PAYROLL_DOCTYPES = [
    "Salary Structure",
    "Salary Structure Assignment",
    "Salary Slip",
    "Salary Component",
    "Payroll Entry",
    "Income Tax Slab",
]

for dt in PAYROLL_DOCTYPES:
    ess_perms = frappe.get_all(
        "Custom DocPerm",
        filters={"parent": dt, "role": "Employee Self Service"},
        fields=["name", "read", "write", "create", "submit", "amend", "delete"],
    )
    for p in ess_perms:
        all_zero = (
            not p.read and not p["write"] and not p.create
            and not p.submit and not p.amend and not p["delete"]
        )
        if all_zero:
            frappe.delete_doc("Custom DocPerm", p.name, force=True, ignore_permissions=True)
            print("  Removed all-zero ESS perm from: " + dt)

frappe.db.commit()

# ─── 5. Clear permission caches ───
print("\n--- Clearing caches ---")
for email in MANAGEMENT_USERS:
    frappe.cache.delete_value("user_permissions:" + email)
    frappe.cache.delete_value("has_role:" + email)
    frappe.cache.delete_value("roles:" + email)
    print("  Cleared permission cache: " + email)

frappe.clear_cache()
print("  Full cache cleared")

# ─── 6. Verify ───
print("\n--- Verification ---")
for email in MANAGEMENT_USERS:
    if not frappe.db.exists("User", email):
        continue
    frappe.set_user(email)
    can_create_supplier = frappe.has_permission("Supplier", ptype="create")
    can_create_customer = frappe.has_permission("Customer", ptype="create")
    emps = frappe.get_list("Employee", fields=["name"])

    ss_create = frappe.has_permission("Salary Structure", ptype="create")
    ss_write = frappe.has_permission("Salary Structure", ptype="write")
    ss_submit = frappe.has_permission("Salary Structure", ptype="submit")
    ss_amend = frappe.has_permission("Salary Structure", ptype="amend")

    print("  " + email + ":")
    print("    create Supplier: " + str(can_create_supplier))
    print("    create Customer: " + str(can_create_customer))
    print("    visible employees: " + str(len(emps)))
    print("    Salary Structure: create=" + str(ss_create) + " write=" + str(ss_write)
          + " submit=" + str(ss_submit) + " amend=" + str(ss_amend))
    frappe.set_user("Administrator")

print("\nDone")
frappe.destroy()
