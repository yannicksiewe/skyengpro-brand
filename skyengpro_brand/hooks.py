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
    "User":        "skyengpro_brand.user_permission.user_has_permission",
    "Customer":    "skyengpro_brand.tenant_scope.customer_has_perm",
    "Supplier":    "skyengpro_brand.tenant_scope.supplier_has_perm",
    "Item":        "skyengpro_brand.tenant_scope.item_has_perm",
    "Letter Head": "skyengpro_brand.tenant_scope.letter_head_has_perm",
}
permission_query_conditions = {
    "User":        "skyengpro_brand.user_permission.user_query_conditions",
    "Customer":    "skyengpro_brand.tenant_scope.customer_query",
    "Supplier":    "skyengpro_brand.tenant_scope.supplier_query",
    "Item":        "skyengpro_brand.tenant_scope.item_query",
    "Letter Head": "skyengpro_brand.tenant_scope.letter_head_query",
}

# Auto-tag the company on insert so new Customer/Supplier/Item records
# always carry the creator's tenant. Letter Head is intentionally not
# auto-tagged — leaving its company empty marks it as shared across
# tenants (matches the allow-NULL behaviour of letter_head_query).
doc_events = {
    "Customer": {"before_insert": "skyengpro_brand.tenant_scope.auto_tag_company"},
    "Supplier": {"before_insert": "skyengpro_brand.tenant_scope.auto_tag_company"},
    "Item":     {"before_insert": "skyengpro_brand.tenant_scope.auto_tag_company"},
}

after_install = "skyengpro_brand.install.after_install"
after_migrate = "skyengpro_brand.install.after_install"
