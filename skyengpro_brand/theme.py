"""Per-tenant brand resolution.

Wired via hooks.py:
    boot_session = "skyengpro_brand.theme.boot_session"

Logic:
    1. Resolve the user's default Company (Frappe defaults → User Permission).
    2. Map the company name to a brand slug (skyengpro / adorsys / ali_capital /
       mc_capital / clemios). Unknown companies fall back to skyengpro.
    3. For each brand asset, fall back to the SkyEngPro asset if the tenant's
       file is missing — so the mechanism works even before a tenant has
       provided its own logo.
    4. Load the tenant's colors from `<brand>/colors.yaml`; fall back to
       SkyEngPro colors on any error.
    5. Stuff the result into `bootinfo.brand`. The client (brand_loader.js)
       reads it on `app_ready` and applies CSS vars + logo + favicon.

The function is best-effort — any unexpected error logs and falls back to the
default SkyEngPro brand so a brand-system bug never breaks login.
"""
from __future__ import annotations

import os

import frappe


# Edit this map when a new tenant is added. The key is the EXACT ERPNext
# Company name as stored in `tabCompany.name`. The value is the brand slug —
# matches the folder name under skyengpro_brand/public/brand/<slug>/.
COMPANY_TO_BRAND = {
    # Real ERPNext Company names (match exactly)
    "Sky Engineering Professional": "skyengpro",
    "adorsys": "adorsys",
    "Clemios Sarl": "clemios",
    "ALI Capital": "ali_capital",
    "MC Capital": "mc_capital",
    # Aliases / earlier naming variants (kept so we don't break if a company
    # is renamed back or a new one matches a legacy form)
    "SkyEngPro Sarl": "skyengpro",
    "SkyEngPro": "skyengpro",
    "adorsys Ireland": "adorsys",
    "Clemios": "clemios",
}

DEFAULT_BRAND = "skyengpro"
ASSET_BASE = "/assets/skyengpro_brand/brand"

# Frappe ships these — used as the *generic* fallback for tenants that haven't
# uploaded their own logo. Better than falling back to the SkyEngPro brand for
# adorsys/MC/ALI/Clemios since that mis-brands every page.
FRAPPE_DEFAULT_LOGO = "/assets/frappe/images/frappe-framework-logo.svg"
FRAPPE_DEFAULT_FAVICON = "/assets/frappe/images/frappe-favicon.svg"


def boot_session(bootinfo):
    """Frappe boot hook. Mutates `bootinfo` in place to add `brand` and
    override `app_logo_url` per tenant.

    The desk navbar Vue component reads the logo URL from `bootinfo.app_logo_url`
    (set earlier in the boot pipeline from `Navbar Settings.app_logo`). Client-
    side DOM mutation is too late for that initial render, so we override the
    URL here. Brand_loader.js still runs on subsequent navigations and for the
    favicon swap.
    """
    try:
        brand_slug = _resolve_brand_slug()
        payload = _build_brand_payload(brand_slug)
        bootinfo.brand = payload

        # Prefer the white navbar variant if the tenant provided one (better
        # contrast on the dark desk navbar). Falls back to the color logo.
        navbar_logo = payload.get("logo_navbar_white") or payload.get("logo_navbar")
        if navbar_logo:
            bootinfo.app_logo_url = navbar_logo
            # navbar_settings is a dict-like; mutate in place so the navbar
            # Vue component reads the override too.
            try:
                if getattr(bootinfo, "navbar_settings", None):
                    bootinfo.navbar_settings.app_logo = navbar_logo
            except Exception:
                pass
    except Exception:
        frappe.logger("skyengpro").exception("brand boot_session failed; falling back to default")
        bootinfo.brand = _build_brand_payload(DEFAULT_BRAND, _safe_fallback=True)

    # /desk apps grid — drop apps that have no workspaces this user
    # can access. Frappe's stock boot adds an entry for every
    # installed app even when the user can't reach any of its
    # workspaces, so the "Frappe HR" / "Accounting" cards keep
    # showing for users who have HR / Accounts modules blocked.
    try:
        _filter_empty_app_data(bootinfo)
    except Exception:
        frappe.logger("skyengpro").exception("filter_empty_app_data failed")


def _filter_empty_app_data(bootinfo):
    """Drop bootinfo.app_data entries with no allowed workspaces.

    `bootinfo.app_data` is built by frappe.boot.get_bootinfo: for
    each installed app, it joins Workspace -> Module Def -> app and
    intersects with the user's allowed_pages. Apps whose workspaces
    are all blocked end up with an empty `workspaces` list, but the
    entry is still added to app_data — and rendered as an app card
    on /desk. We filter those out so the apps grid only shows
    cards the user can actually click into.

    Administrator is exempted so the platform admin sees every app.
    """
    if frappe.session.user == "Administrator":
        return
    app_data = getattr(bootinfo, "app_data", None)
    if not app_data:
        return
    bootinfo.app_data = [a for a in app_data if a.get("workspaces")]


def _resolve_brand_slug() -> str:
    """Best-guess of which brand to show this user.

    Priority (most specific → least specific):
      1. Employee.company linked to this user (Frappe HR primary linkage)
      2. User Permission "allow=Company" for this user
      3. Frappe per-user default for "company"
      4. The site's default Company (Global Defaults)
      5. DEFAULT_BRAND

    NOTE: Employee comes first because `frappe.defaults.get_user_default("company")`
    falls back to the *global* default when no per-user value is set, which would
    incorrectly resolve every adorsys/clemios user to the SkyEngPro brand.
    """
    # Skip lookup for guest / login page — not authenticated
    if frappe.session.user == "Guest":
        return DEFAULT_BRAND

    company = None

    # 1) Employee → Company. Most specific signal for HR-managed users.
    try:
        emp_company = frappe.db.get_value(
            "Employee",
            {"user_id": frappe.session.user, "status": "Active"},
            "company",
        )
        if emp_company:
            company = emp_company
    except Exception:
        pass

    # 2) User Permission table
    if not company:
        try:
            rows = frappe.db.get_all(
                "User Permission",
                filters={"user": frappe.session.user, "allow": "Company"},
                fields=["for_value"],
                limit=1,
                ignore_permissions=True,
            )
            if rows:
                company = rows[0].for_value
        except Exception:
            pass

    # 3) Per-user / global default. Note: this falls back to Global Defaults
    #    silently so it must come AFTER more specific lookups.
    if not company:
        company = frappe.defaults.get_user_default("company")

    if not company:
        company = frappe.db.get_single_value("Global Defaults", "default_company")

    if not company:
        return DEFAULT_BRAND

    return COMPANY_TO_BRAND.get(company, DEFAULT_BRAND)


def _build_brand_payload(brand_slug: str, _safe_fallback: bool = False) -> dict:
    """Resolve a brand slug to the URLs + colors the client needs.

    Per-tenant assets win. When a tenant doesn't have a specific variant we
    fall back within the same tenant first (e.g. white → color of same brand)
    and only as a last resort to the Frappe default logo. We deliberately do
    NOT fall back to the SkyEngPro asset, because every tenant except the
    actual SkyEngPro tenant would then visually mis-brand as SkyEngPro.
    """
    colors = _load_colors(brand_slug)
    is_skyengpro = (brand_slug == DEFAULT_BRAND)

    # Build the per-tenant fallback chains. Each entry is a relative path
    # under public/brand/. The first one that exists on disk wins.
    color_chain = [
        f"{brand_slug}/logo_horizontal_color_400px.png",
        f"{brand_slug}/logo_horizontal_color_150px.png",
        f"{brand_slug}/logo_horizontal_color_800px.png",
    ]
    # White variant: prefer real white, then color of same tenant (better
    # than mis-branding with skyengpro white on a dark navbar).
    white_chain = [
        f"{brand_slug}/logo_horizontal_white_400px.png",
        f"{brand_slug}/logo_horizontal_white_800px.png",
    ] + color_chain

    favicon_chain = [f"{brand_slug}/icon_mark_32px.png"]
    icon512_chain = [f"{brand_slug}/icon_mark_512px.png"]

    # The ACTUAL skyengpro tenant *should* fall back to its own assets — they
    # are the canonical ones — but never to the Frappe default. Other tenants
    # fall back to Frappe default if they have no logo at all.
    logo_default = (
        f"{ASSET_BASE}/{DEFAULT_BRAND}/logo_horizontal_color_400px.png"
        if is_skyengpro
        else FRAPPE_DEFAULT_LOGO
    )
    favicon_default = (
        f"{ASSET_BASE}/{DEFAULT_BRAND}/icon_mark_32px.png"
        if is_skyengpro
        else FRAPPE_DEFAULT_FAVICON
    )

    return {
        "slug": brand_slug,
        "logo_navbar": _first_existing(color_chain, default_url=logo_default),
        "logo_navbar_white": _first_existing(white_chain, default_url=logo_default),
        "favicon": _first_existing(favicon_chain, default_url=favicon_default),
        "icon_512": _first_existing(icon512_chain, default_url=favicon_default),
        "primary": colors.get("primary", "#CC7A1A"),
        "primary_hover": colors.get("primary_hover", "#B56A12"),
        "primary_light": colors.get("primary_light", "#F5E6D0"),
        "navbar_bg": colors.get("navbar_bg", "#2C2C2C"),
        "navbar_fg": colors.get("navbar_fg", "#FFFFFF"),
    }


def _first_existing(candidates: list, default_url: str) -> str:
    """Return ASSET_BASE-prefixed URL of the first candidate that exists on
    disk, or `default_url` if none exist."""
    app_path = frappe.get_app_path("skyengpro_brand", "public", "brand")
    for rel in candidates:
        if os.path.exists(os.path.join(app_path, rel)):
            return f"{ASSET_BASE}/{rel}"
    return default_url


def _resolve_asset(brand_slug: str, filename: str, fallbacks: list) -> str:
    """Backwards-compat wrapper kept in case anything else imports it."""
    candidates = [f"{brand_slug}/{filename}"] + list(fallbacks)
    return _first_existing(candidates, default_url=FRAPPE_DEFAULT_LOGO)


def _load_colors(brand_slug: str) -> dict:
    """Load <brand>/colors.yaml into a dict. Falls back to SkyEngPro on error."""
    try:
        import yaml  # frappe ships PyYAML
    except ImportError:
        return {}

    paths = [
        os.path.join(frappe.get_app_path("skyengpro_brand", "public", "brand"),
                     brand_slug, "colors.yaml"),
        os.path.join(frappe.get_app_path("skyengpro_brand", "public", "brand"),
                     DEFAULT_BRAND, "colors.yaml"),
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p) as f:
                    data = yaml.safe_load(f) or {}
                if isinstance(data, dict):
                    return data
            except Exception:
                continue
    return {}
