"""
Fix management user permissions for Branda + Beltine.
Scripted so it can be re-run on any instance.
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

# ─── 4. Verify ───
print("\n--- Verification ---")
for email in MANAGEMENT_USERS:
    frappe.set_user(email)
    can_create_supplier = frappe.has_permission("Supplier", ptype="create")
    can_create_customer = frappe.has_permission("Customer", ptype="create")
    emps = frappe.get_list("Employee", fields=["name"])
    print("  " + email + ":")
    print("    create Supplier: " + str(can_create_supplier))
    print("    create Customer: " + str(can_create_customer))
    print("    visible employees: " + str(len(emps)))

frappe.clear_cache()
print("\nDone")
frappe.destroy()
