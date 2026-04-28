# Copyright (c) 2026, SkyEngPro and contributors
"""Tenant provisioning — read brand/<slug>/tenant.csv and create/update the
ERPNext Company along with its defaults, naming series, and Letterhead.

Idempotent. Safe to re-run. Designed to make adding a new tenant a one-step
operation:
  1. Create brand/<slug>/ folder (with assets + colors.yaml + tenant.csv)
  2. Add the company name to skyengpro_brand.theme.COMPANY_TO_BRAND
  3. Run: bench --site <site> execute skyengpro_brand.tenant_setup.provision \\
            --kwargs "{'slug': '<slug>'}"

Also exposes:
  - provision_all()  — provision every brand/<slug>/tenant.csv on disk
  - delete_company(name) — remove a manually-created Company before
    provisioning it via the script (asks for explicit confirmation_phrase)
"""
from __future__ import annotations

import csv
import os
from typing import Dict, Optional

import frappe
from frappe import _


# ──────────────────────────────────────────────────────────────────
# Public API (whitelisted so it can be called via bench / web)
# ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
def provision(slug: str, dry_run: int = 0) -> dict:
    """Read brand/<slug>/tenant.csv and create or update the Company.

    Args:
        slug: tenant folder name (e.g. "clemios", "ali_capital").
        dry_run: 1 to print what would change without committing.

    Returns:
        Summary dict with `created`, `updated`, `skipped`, and `errors`.
    """
    cfg = _read_tenant_csv(slug)
    summary = {
        "slug": slug,
        "company_name": cfg.get("company_name"),
        "actions": [],
        "errors": [],
        "dry_run": bool(dry_run),
    }

    try:
        action = _ensure_company(cfg, dry_run=dry_run)
        summary["actions"].append(action)

        action = _ensure_fiscal_year(cfg, dry_run=dry_run)
        if action:
            summary["actions"].append(action)

        action = _ensure_holiday_list(cfg, dry_run=dry_run)
        if action:
            summary["actions"].append(action)

        action = _ensure_employee_naming_series(cfg, dry_run=dry_run)
        if action:
            summary["actions"].append(action)

        action = _ensure_letterhead(cfg, dry_run=dry_run)
        if action:
            summary["actions"].append(action)

        if not dry_run:
            frappe.db.commit()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"tenant_setup.provision({slug})")
        summary["errors"].append(str(e))

    _print_summary(summary)
    return summary


@frappe.whitelist()
def provision_all(dry_run: int = 0) -> list:
    """Provision every tenant.csv found under brand/."""
    base = _brand_dir()
    out = []
    for entry in sorted(os.listdir(base)):
        full = os.path.join(base, entry)
        if not os.path.isdir(full):
            continue
        if not os.path.exists(os.path.join(full, "tenant.csv")):
            continue
        out.append(provision(entry, dry_run=dry_run))
    return out


@frappe.whitelist()
def delete_company(company_name: str, confirmation_phrase: str = "") -> dict:
    """Remove a manually-created Company so the script can recreate it cleanly.

    Destructive — deletes Company + its child records. Requires the caller to
    pass `confirmation_phrase=DELETE <CompanyName>` exactly.
    """
    expected = f"DELETE {company_name}"
    if confirmation_phrase != expected:
        return {
            "deleted": False,
            "reason": (
                "Confirmation phrase missing. Re-run with "
                f"confirmation_phrase='{expected}'."
            ),
        }

    if not frappe.db.exists("Company", company_name):
        return {"deleted": False, "reason": f"Company '{company_name}' not found"}

    # Frappe's delete_doc on Company cascades to its child records.
    frappe.delete_doc("Company", company_name, force=1, ignore_permissions=True)
    frappe.db.commit()
    return {"deleted": True, "company": company_name}


# ──────────────────────────────────────────────────────────────────
# Internals
# ──────────────────────────────────────────────────────────────────

def _brand_dir() -> str:
    return frappe.get_app_path("skyengpro_brand", "public", "brand")


def _read_tenant_csv(slug: str) -> Dict[str, str]:
    """Load brand/<slug>/tenant.csv into a flat dict.

    The file is a 2-column CSV `field,value` (third column `notes` is ignored).
    Lines starting with '#' are skipped. Empty values become None.
    """
    path = os.path.join(_brand_dir(), slug, "tenant.csv")
    if not os.path.exists(path):
        frappe.throw(_("tenant.csv not found at {0}").format(path))

    cfg: Dict[str, str] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            field = row[0].strip()
            if not field or field.startswith("#"):
                continue
            if field == "field":  # header
                continue
            value = row[1].strip() if len(row) > 1 else ""
            cfg[field] = value if value else None
    if not cfg.get("company_name"):
        frappe.throw(_("company_name missing in {0}").format(path))
    return cfg


def _ensure_company(cfg: Dict[str, str], dry_run: bool) -> dict:
    name = cfg["company_name"]
    if frappe.db.exists("Company", name):
        # Update editable fields
        doc = frappe.get_doc("Company", name)
        changed = []
        for field, target in (
            ("abbr", cfg.get("abbr")),
            ("country", cfg.get("country")),
            ("default_currency", cfg.get("default_currency")),
            ("parent_company", cfg.get("parent_company")),
            ("is_group", int(cfg.get("is_group") or 0)),
        ):
            if target is None:
                continue
            current = doc.get(field)
            # Cast for comparison
            if field == "is_group":
                if int(current or 0) != target:
                    changed.append((field, current, target))
                    doc.set(field, target)
            elif current != target:
                changed.append((field, current, target))
                doc.set(field, target)
        if changed and not dry_run:
            doc.save(ignore_permissions=True)
        return {"step": "company", "result": "updated" if changed else "unchanged",
                "name": name, "changed_fields": changed}
    else:
        if dry_run:
            return {"step": "company", "result": "would-create", "name": name}
        doc = frappe.new_doc("Company")
        doc.company_name = name
        doc.abbr = cfg.get("abbr") or _slug_to_abbr(cfg["slug"])
        doc.country = cfg.get("country") or "Cameroon"
        doc.default_currency = cfg.get("default_currency") or "XAF"
        doc.is_group = int(cfg.get("is_group") or 0)
        if cfg.get("parent_company"):
            doc.parent_company = cfg["parent_company"]
        if cfg.get("chart_of_accounts"):
            doc.chart_of_accounts = cfg["chart_of_accounts"]
        doc.insert(ignore_permissions=True)
        return {"step": "company", "result": "created", "name": name}


def _ensure_fiscal_year(cfg: Dict[str, str], dry_run: bool) -> Optional[dict]:
    """Best-effort fiscal year setup. Frappe may already have a 2026 FY from
    site bootstrap; this function does NOT create new fiscal years to avoid
    conflicts. It only logs the desired range for visibility.
    """
    fy_start = cfg.get("fiscal_year_start")
    fy_end = cfg.get("fiscal_year_end")
    if not fy_start or not fy_end:
        return None
    return {"step": "fiscal_year", "result": "noted",
            "note": f"desired window {fy_start}..{fy_end} (FY records not auto-created — confirm in ERPNext)"}


def _ensure_holiday_list(cfg: Dict[str, str], dry_run: bool) -> Optional[dict]:
    name = cfg.get("holiday_list_name")
    if not name:
        return None
    if frappe.db.exists("Holiday List", name):
        return {"step": "holiday_list", "result": "exists", "name": name}
    if dry_run:
        return {"step": "holiday_list", "result": "would-create", "name": name}

    doc = frappe.new_doc("Holiday List")
    doc.holiday_list_name = name
    doc.from_date = "2026-01-01"
    doc.to_date = "2026-12-31"
    doc.insert(ignore_permissions=True)
    return {"step": "holiday_list", "result": "created", "name": name,
            "note": "empty — add country holidays manually or via 'Get Weekly Off Dates'"}


def _ensure_employee_naming_series(cfg: Dict[str, str], dry_run: bool) -> Optional[dict]:
    series = cfg.get("employee_naming")
    if not series:
        return None
    # Read current series options
    current = (frappe.db.get_value("DocType", "Employee", "autoname") or "")
    if dry_run:
        return {"step": "naming_series", "result": "would-set",
                "current": current, "target": series}
    # Frappe stores naming series options on the field, not autoname directly.
    # Easier: use Property Setter for the naming_series field.
    series_field = frappe.get_meta("Employee").get_field("naming_series")
    if not series_field:
        return {"step": "naming_series", "result": "skipped",
                "reason": "Employee.naming_series field not present"}
    options = (series_field.options or "").split("\n")
    if series in options:
        return {"step": "naming_series", "result": "exists", "series": series}
    options.append(series)
    new_options = "\n".join(o for o in options if o)
    # Use Property Setter so it survives migrations
    ps_name = "Employee-naming_series-options"
    if frappe.db.exists("Property Setter", ps_name):
        ps = frappe.get_doc("Property Setter", ps_name)
        ps.value = new_options
        ps.save(ignore_permissions=True)
    else:
        frappe.get_doc({
            "doctype": "Property Setter",
            "doctype_or_field": "DocField",
            "doc_type": "Employee",
            "field_name": "naming_series",
            "property": "options",
            "property_type": "Text",
            "value": new_options,
        }).insert(ignore_permissions=True)
    return {"step": "naming_series", "result": "added", "series": series}


def _ensure_letterhead(cfg: Dict[str, str], dry_run: bool) -> Optional[dict]:
    """Create a Letter Head record using the per-tenant letterhead PNG."""
    slug = cfg["slug"]
    company_name = cfg["company_name"]
    name = cfg.get("default_letterhead") or f"{company_name} Letterhead"

    letterhead_path = os.path.join(_brand_dir(), slug, "letterhead_400px.png")
    if not os.path.exists(letterhead_path):
        return {"step": "letterhead", "result": "skipped",
                "reason": f"no letterhead at brand/{slug}/letterhead_400px.png"}
    asset_url = f"/assets/skyengpro_brand/brand/{slug}/letterhead_400px.png"

    if frappe.db.exists("Letter Head", name):
        if dry_run:
            return {"step": "letterhead", "result": "would-update", "name": name}
        doc = frappe.get_doc("Letter Head", name)
        doc.image = asset_url
        doc.source = "Image"
        doc.save(ignore_permissions=True)
        return {"step": "letterhead", "result": "updated", "name": name}

    if dry_run:
        return {"step": "letterhead", "result": "would-create", "name": name}
    doc = frappe.new_doc("Letter Head")
    doc.letter_head_name = name
    doc.image = asset_url
    doc.source = "Image"
    doc.is_default = 0
    doc.insert(ignore_permissions=True)
    # Set as default for the Company
    if frappe.db.exists("Company", company_name):
        frappe.db.set_value("Company", company_name, "default_letter_head", name)
    return {"step": "letterhead", "result": "created", "name": name}


def _slug_to_abbr(slug: str) -> str:
    """Fallback abbreviation if not provided in CSV."""
    return "".join(part[0].upper() for part in slug.split("_"))[:5] or "TNT"


def _print_summary(summary: dict) -> None:
    print(f"\n=== tenant_setup.provision({summary['slug']}) ===")
    print(f"company: {summary['company_name']}  dry_run: {summary['dry_run']}")
    for action in summary["actions"]:
        print(f"  • {action}")
    if summary["errors"]:
        print("  ERRORS:")
        for err in summary["errors"]:
            print(f"    {err}")
