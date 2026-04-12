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


def user_query_conditions(user=None):
    """SQL WHERE clause to filter User list by company.

    Non-admins only see users who share at least one company.
    Registered via hooks.py permission_query_conditions.
    """
    if not user:
        user = frappe.session.user

    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return ""

    # Get current user's companies
    companies = get_user_companies(user)
    if not companies:
        # No company restriction = sees all (shouldn't happen for non-admins)
        return ""

    # Find users who have at least one company in common
    company_list = ", ".join("'{}'".format(c.replace("'", "\\'")) for c in companies)

    return """
        `tabUser`.name IN (
            SELECT user FROM `tabUser Permission`
            WHERE allow = 'Company' AND for_value IN ({companies})
        )
        OR `tabUser`.name = '{user}'
    """.format(companies=company_list, user=user.replace("'", "\\'"))


def get_user_companies(email):
    """Get set of companies a user has access to."""
    perms = frappe.get_all(
        "User Permission",
        filters={"user": email, "allow": "Company"},
        fields=["for_value"],
        ignore_permissions=True,
    )
    return {p.for_value for p in perms}
