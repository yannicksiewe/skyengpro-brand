"""
SkyEngPro — User DocType Permission Override

Restricts User list visibility for non-admin users.
Non-admins can only see:
  - Their own User record
  - Users in their company (via Employee → User mapping)

Registered via hooks.py:
    has_permission = {
        "User": "skyengpro_brand.user_permission.user_has_permission"
    }
"""
import frappe


def user_has_permission(doc, ptype=None, user=None):
    """Permission check for User DocType."""
    if not user:
        user = frappe.session.user

    # Admin/System Manager sees all
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return True

    # Users can always read their own record
    if doc.name == user:
        return True

    # For list view: block reading other users' records
    if ptype == "read":
        # Allow if the other user is in the same company
        user_companies = get_user_companies(user)
        other_companies = get_user_companies(doc.name)

        if user_companies and other_companies:
            # Allow if they share at least one company
            if user_companies & other_companies:
                return True

        return False

    return True


def get_user_companies(email):
    """Get set of companies a user has access to."""
    perms = frappe.get_all(
        "User Permission",
        filters={"user": email, "allow": "Company"},
        fields=["for_value"],
        ignore_permissions=True,
    )
    return {p.for_value for p in perms}
