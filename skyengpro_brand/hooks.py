app_name = "skyengpro_brand"
app_title = "SkyEngPro Brand"
app_publisher = "SkyEngPro"
app_description = "SkyEngPro branding — logos, favicon, colors, and system name"
app_email = "contact@skyengpro.com"
app_license = "MIT"
required_apps = ["frappe"]

# Inject brand CSS into every desk page (safe — pure CSS, no JS hooks)
app_include_css = "/assets/skyengpro_brand/css/skyengpro.css"

# Intercept Script Report execution to inject company filter (prevents data leaks)
override_whitelisted_methods = {
    "frappe.desk.query_report.run": "skyengpro_brand.report_filter.run",
}

# Restrict User list + single doc to same-company users only
has_permission = {
    "User": "skyengpro_brand.user_permission.user_has_permission"
}
permission_query_conditions = {
    "User": "skyengpro_brand.user_permission.user_query_conditions"
}

after_install = "skyengpro_brand.install.after_install"
after_migrate = "skyengpro_brand.install.after_install"
