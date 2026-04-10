app_name = "skyengpro_brand"
app_title = "SkyEngPro Brand"
app_publisher = "SkyEngPro"
app_description = "SkyEngPro branding — logos, favicon, colors, and system name"
app_email = "contact@skyengpro.com"
app_license = "MIT"
required_apps = ["frappe"]

# Inject brand CSS into every desk page (safe — pure CSS, no JS hooks)
app_include_css = "/assets/skyengpro_brand/css/skyengpro.css"

after_install = "skyengpro_brand.install.after_install"
after_migrate = "skyengpro_brand.install.after_install"
