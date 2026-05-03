app_name = "skyengpro_brand"
app_title = "SkyEngPro Brand"
app_publisher = "SkyEngPro"
app_description = "SkyEngPro branding — logos, favicon, colors, and system name"
app_email = "contact@skyengpro.com"
app_license = "MIT"
required_apps = ["frappe"]

# Inject brand CSS on desk pages (logged-in users)
app_include_css = "/assets/skyengpro_brand/css/skyengpro.css"
# Same brand CSS on web pages (login, portal, signup) — without this the
# login page falls back to Frappe defaults and the SKYENGPRO mark becomes
# invisible (white-on-white).
web_include_css = "/assets/skyengpro_brand/css/skyengpro.css"

# Brand loader: reads frappe.boot.brand and applies per-tenant logo + colors
# at runtime. Loaded on both desk and web so login carries SkyEngPro brand
# even for guests (the loader gracefully falls back when frappe.boot.brand
# is absent).
app_include_js = "/assets/skyengpro_brand/js/brand_loader.js"
web_include_js = "/assets/skyengpro_brand/js/brand_loader.js"

# Resolve the user's tenant brand at boot and stuff it into bootinfo.brand
boot_session = "skyengpro_brand.theme.boot_session"

# Self Service app card on /desk apps grid. Frappe v16's apps grid is
# populated by frappe.apps.get_apps() which iterates every installed
# app's `add_to_apps_screen` hook entries. Adding this entry makes
# Self Service render as a top-level card alongside Framework /
# Organization / Accounting / Projects, with a one-click route into
# the dedicated workspace (Apply for Leave / My Salary Slips /
# Submit Expense). has_permission returns False for Website Users
# only — Self Service is meant for any desk-bound user.
add_to_apps_screen = [
    {
        "name":           "skyengpro_brand",
        "logo":           "/assets/skyengpro_brand/brand/skyengpro/icon_mark_512px.png",
        "title":          "Self Service",
        "route":          "/desk/self-service",
        "has_permission": "skyengpro_brand.dashboard_perm.self_service_app_has_permission",
    }
]

# DocType-scoped client scripts. Frappe loads these on the matching form.
doctype_js = {
    "Project": "public/js/project_form.js",
}

# Extend the Connections panels of Project and Employee with a Capacity
# Planning section listing related Project Allocation rows.
override_doctype_dashboards = {
    "Project": "skyengpro_brand.capacity_planning.dashboard.project_dashboard.get_data",
    "Employee": "skyengpro_brand.capacity_planning.dashboard.employee_dashboard.get_data",
}

# Intercept Script Report execution to inject company filter (prevents data leaks)
override_whitelisted_methods = {
    "frappe.desk.query_report.run": "skyengpro_brand.report_filter.run",
}

# Per-tenant scoping: User list filter + same scope applied to the four
# shared masters that ERPNext leaves globally visible by default
# (Customer, Supplier, Item, Letter Head). Resolver lives in
# tenant_scope.get_user_company; behaviour for NULL company is per-doctype
# (strict for Customer/Supplier/Item, allow-as-global for Letter Head).
has_permission = {
    "User":             "skyengpro_brand.user_permission.user_has_permission",
    "Company":          "skyengpro_brand.tenant_scope.company_has_perm",
    "Customer":         "skyengpro_brand.tenant_scope.customer_has_perm",
    "Supplier":         "skyengpro_brand.tenant_scope.supplier_has_perm",
    "Item":             "skyengpro_brand.tenant_scope.item_has_perm",
    "Letter Head":      "skyengpro_brand.tenant_scope.letter_head_has_perm",
    "Project":          "skyengpro_brand.tenant_scope.project_has_perm",
    "Project User":     "skyengpro_brand.tenant_scope.project_user_has_perm",
    "Task":             "skyengpro_brand.tenant_scope.task_has_perm",
    # Per-dashboard role gates. Hides the auto-injected workspace
    # sidebar entry for non-managers (the "Dashboard" item under
    # Projects). See dashboard_perm.DASHBOARD_ROLE_GATES.
    "Dashboard":        "skyengpro_brand.dashboard_perm.dashboard_has_perm",
}

# Override the Workspace Sidebar controller to route dashboard sidebar
# items through has_permission. Without this override Frappe shows
# every dashboard item to every user (hardcoded `return True`), which
# negates the Dashboard has_permission hook above.
override_doctype_class = {
    "Workspace Sidebar": "skyengpro_brand.workspace_sidebar_override.PatchedWorkspaceSidebar",
}
permission_query_conditions = {
    "User":             "skyengpro_brand.user_permission.user_query_conditions",
    "Company":          "skyengpro_brand.tenant_scope.company_query",
    "Customer":         "skyengpro_brand.tenant_scope.customer_query",
    "Supplier":         "skyengpro_brand.tenant_scope.supplier_query",
    "Item":             "skyengpro_brand.tenant_scope.item_query",
    "Letter Head":      "skyengpro_brand.tenant_scope.letter_head_query",
    "Project":          "skyengpro_brand.tenant_scope.project_query",
    "Project User":     "skyengpro_brand.tenant_scope.project_user_query",
    "Task":             "skyengpro_brand.tenant_scope.task_query",
    "Timesheet Detail": "skyengpro_brand.tenant_scope.timesheet_detail_query",
}

# Auto-tag the company on insert so new Customer/Supplier/Item records
# always carry the creator's tenant. Letter Head is intentionally not
# auto-tagged — leaving its company empty marks it as shared across
# tenants (matches the allow-NULL behaviour of letter_head_query).
doc_events = {
    "Customer":  {"before_insert": "skyengpro_brand.tenant_scope.auto_tag_company"},
    "Supplier":  {"before_insert": "skyengpro_brand.tenant_scope.auto_tag_company"},
    "Item":      {"before_insert": "skyengpro_brand.tenant_scope.auto_tag_company"},
    # Auto-add the creator to Project.users so the canonical team UI
    # is always seeded with at least one member (the creator).
    "Project":   {"before_insert": "skyengpro_brand.tenant_scope.auto_add_project_creator"},
    # Hard-block Timesheet save when any time_logs row references a
    # project the user isn't assigned to. Closes the validate_link
    # save-by-name bypass that permission_query_conditions cannot.
    "Timesheet": {"validate": "skyengpro_brand.tenant_scope.validate_timesheet_projects"},
    # Auto-attach default Module Profile + Employee/ESS roles on new
    # System User creation. Runs synchronously inside the User insert
    # so first-login already gets a shaped sidebar.
    "User":      {
        "after_insert": "skyengpro_brand.user_lifecycle.on_user_after_insert",
        # Frappe core has a hardcoded self-permission on User: every
        # authenticated user can save changes to their own User record
        # regardless of DocPerm. This validate hook closes that gap by
        # refusing self-edit for any user without System Manager.
        "validate":     "skyengpro_brand.user_lifecycle.block_self_edit_for_non_admins",
    },
    # Keep User -> Employee User Permission (Salary Slip leak guard)
    # in sync when HR links/unlinks a User from an Employee.
    "Employee":  {
        "after_insert": "skyengpro_brand.user_lifecycle.on_employee_save",
        "on_update":    "skyengpro_brand.user_lifecycle.on_employee_save",
    },
}

after_install = "skyengpro_brand.install.after_install"
after_migrate = "skyengpro_brand.install.after_install"

# Bulletin de Paie helpers — expose payroll_helpers functions inside the
# print-format Jinja sandbox. Each path's last segment becomes the callable
# name in the template (e.g. component_code(name)).
jinja = {
    "methods": [
        "skyengpro_brand.payroll_helpers.component_code",
        "skyengpro_brand.payroll_helpers.component_label",
        "skyengpro_brand.payroll_helpers.is_employer_component",
        "skyengpro_brand.payroll_helpers.split_deductions",
        "skyengpro_brand.payroll_helpers.anciennete",
        "skyengpro_brand.payroll_helpers.ytd_totals",
        "skyengpro_brand.payroll_helpers.employee_field",
        "skyengpro_brand.payroll_helpers.company_field",
        "skyengpro_brand.payroll_helpers.total_imposable",
        "skyengpro_brand.payroll_helpers.total_cotisation",
        "skyengpro_brand.payroll_helpers.format_taux",
        "skyengpro_brand.payroll_helpers.format_base",
        "skyengpro_brand.payroll_helpers.brand_image_data_uri",
    ],
}
