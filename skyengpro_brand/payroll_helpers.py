"""Bulletin de Paie helpers — Jinja-callable utilities for the payslip print format.

The print format calls these functions to:
  - Resolve a Salary Component name to its display label + numeric code (1000, 1040, ...).
  - Format Cameroon-style anciennete from date_of_joining ("01 an 07 mois").
  - Compute year-to-date totals (Salaire brut / Charges / Net à payer).
  - Resolve company-side custom fields with safe blank fallback.

Why a helper module instead of inline Jinja: the PDF needs *labels* that don't match the
DB component names exactly (PDF says "Indemnité de Transport" but the component is
"Prime de Transport"; PDF says "Pension vieillesse CNPS" but the component is
"CNPS Salariale", etc.). Maintaining the mapping in Python is cleaner than embedding
a giant Jinja `{% if ... %}` chain in the print format HTML.
"""
from __future__ import annotations

import base64
import os
import re
from datetime import date, datetime

import frappe


# Component code/label map. Key = canonical Salary Component name as stored in
# `tabSalary Detail.salary_component`. Value = (numeric code, French display label).
# Codes 1xxx = earnings, 8xxx = salarial deductions, 9xxx = pension contributions
# (matches the bareme codes shown on the original PDF). The print format reads
# this map at render time — adding a new component is a one-line edit here.
COMPONENT_DISPLAY = {
    # Earnings (codes 1xxx)
    "Salaire de Base":              ("1000", "Salaire de Base mensuel"),
    "Prime de Transport":           ("1040", "Indemnité de Transport"),
    "Prime de Logement":            ("1050", "Indemnité de Logement"),
    "Prime de Technicite":          ("1020", "Prime de technicité"),
    "Indemnité de représentation":  ("1030", "Indemnité de représentation"),
    "Prime d'Ancienneté":           ("1060", "Prime d'Ancienneté"),
    "Prime de Responsabilité":      ("1070", "Prime de Responsabilité"),
    # Employer charges (Retenues patronales) — no codes shown on PDF, label only
    "Fond National de L'emploi":    ("",     "FNE"),
    "Fond National de L'emploie":   ("",     "FNE"),  # legacy typo variant
    "CFC Patronal":                 ("",     "CFC/PAT"),
    "CNPS Patronale":               ("",     "CNPS"),
    # Salarial deductions (codes 8xxx + 9xxx)
    "IRPP":                         ("8010", "IRPP"),
    "IRPP_1":                       ("8010", "IRPP"),  # legacy duplicate variant
    "CAC":                          ("8020", "CAC/IRPP"),
    "CFC":                          ("8030", "Crédit Foncier Salarial"),
    "RAV":                          ("8040", "Redevance Audio Visuelle"),
    "TDL":                          ("8050", "TDL"),
    "CNPS Salariale":               ("9010", "Pension vieillesse CNPS"),
}

# Components classified as employer-side (Retenues patronales) so the print
# format renders them in the patronal block rather than the salarial block.
EMPLOYER_COMPONENTS = {
    "Fond National de L'emploi",
    "Fond National de L'emploie",
    "CFC Patronal",
    "CNPS Patronale",
}

# Components computed by progressive tax brackets (not a flat percentage).
# Renders as "Bareme" in the Taux column. IRPP is the income-tax progressive
# scale; RAV uses a slab table; TDL is a per-bracket fixed levy.
BAREME_COMPONENTS = {"IRPP", "IRPP_1", "RAV", "TDL"}

# Standard Cameroonian payroll rates per legal text (Loi des Finances /
# Code Général des Impôts / Code de Sécurité Sociale). Used as the Taux
# column fallback when the salary slip rows don't carry a formula.
# Update here when a rate is revised by law — single source of truth.
TAUX_DEFAULTS = {
    # Employer charges (Retenues patronales)
    "CNPS Patronale":               "12.95%",   # 4.20 vieillesse + 7 PF + 1.75 AT
    "Fond National de L'emploi":    "1%",
    "Fond National de L'emploie":   "1%",       # legacy typo variant
    "CFC Patronal":                 "1.5%",
    # Salarial deductions
    "CNPS Salariale":               "4.20%",    # pension vieillesse
    "CFC":                          "1%",       # Crédit Foncier salarial
    "CAC":                          "10%",      # Centimes additionnels (10% of IRPP)
}

# Match a simple "base * X / 100" rate inside a formula. Captures X.
_PERCENT_RE = re.compile(r"\*\s*([\d.]+)\s*/\s*100")


def component_code(name: str) -> str:
    """Return the numeric code (e.g. '1000') for a salary component, or empty."""
    return COMPONENT_DISPLAY.get(name, ("", name))[0]


def component_label(name: str) -> str:
    """Return the French display label, falling back to the raw name."""
    return COMPONENT_DISPLAY.get(name, ("", name))[1]


def is_employer_component(name: str) -> bool:
    """True if this deduction is an employer charge (retenue patronale)."""
    return name in EMPLOYER_COMPONENTS


def format_taux(row) -> str:
    """Return the Taux column string for a deduction row.

    Resolution order:
      1. If the component is bracket-based (IRPP/RAV/TDL) → 'Bareme'.
      2. If the slip row has a `base * X / 100` formula → 'X%'.
      3. If the component has a known statutory rate → the stored rate
         (TAUX_DEFAULTS — covers components paid as a static amount on
         the slip but where the underlying rate is well-known).
      4. Otherwise empty.
    """
    if not row:
        return ""
    name = row.salary_component
    if name in BAREME_COMPONENTS:
        return "Bareme"
    formula = (row.formula or "") if getattr(row, "amount_based_on_formula", 0) else ""
    if formula:
        m = _PERCENT_RE.search(formula)
        if m:
            rate = m.group(1).rstrip("0").rstrip(".") or "0"
            return f"{rate}%"
        return "Bareme"
    return TAUX_DEFAULTS.get(name, "")


def format_base(row, slip) -> float:
    """Return the Base value for a deduction row's Base column.

    Different deductions use different bases in Cameroon payroll:
      - IRPP / CAC / CFC / RAV / TDL — Total imposable (gross minus
        IRPP-exempt allowances)
      - CNPS Salariale / CNPS Patronale — Total cotisation (capped gross)
      - FNE / CFC Patronal — Total brut (full gross)
    Returns 0 when no recognised base applies (template renders empty).
    """
    if not row:
        return 0.0
    name = row.salary_component
    if name in {"IRPP", "IRPP_1", "CAC", "CFC", "RAV", "TDL"}:
        return total_imposable(slip)
    if name in {"CNPS Salariale", "CNPS Patronale"}:
        return total_cotisation(slip)
    if name in {"Fond National de L'emploi", "Fond National de L'emploie", "CFC Patronal"}:
        return float(slip.gross_pay or 0)
    return 0.0


def split_deductions(deductions):
    """Split a Salary Slip's deductions list into (employer, salarial) tuples.

    Returns ([retenues_patronales], [retenues_salariales]) — each preserving
    the original child-doc rows so the template can read amount, formula, etc.
    """
    employer, salarial = [], []
    for row in deductions or []:
        (employer if is_employer_component(row.salary_component) else salarial).append(row)
    return employer, salarial


def anciennete(doj) -> str:
    """Format seniority as Cameroon-style 'NN an MM mois' from date_of_joining.

    Returns empty string if date_of_joining is missing.
    """
    if not doj:
        return ""
    if isinstance(doj, str):
        try:
            doj = datetime.strptime(doj, "%Y-%m-%d").date()
        except ValueError:
            return ""
    today = date.today()
    months = (today.year - doj.year) * 12 + (today.month - doj.month)
    if today.day < doj.day:
        months -= 1
    if months < 0:
        return ""
    years, mm = divmod(months, 12)
    return f"{years:02d} an {mm:02d} mois"


def ytd_totals(slip) -> dict:
    """Sum gross_pay / total_deduction / net_pay across all submitted Salary
    Slips for this employee with end_date in the same calendar year as the
    current slip — including the current one if submitted.

    Returns {"gross": x, "deductions": y, "net": z}. All zero on errors.
    """
    try:
        year = (
            slip.end_date.year
            if hasattr(slip.end_date, "year")
            else datetime.strptime(str(slip.end_date), "%Y-%m-%d").year
        )
        rows = frappe.db.sql(
            """SELECT COALESCE(SUM(gross_pay),0)         AS gross,
                      COALESCE(SUM(total_deduction),0)  AS deductions,
                      COALESCE(SUM(net_pay),0)          AS net
                 FROM `tabSalary Slip`
                WHERE employee = %s
                  AND docstatus = 1
                  AND YEAR(end_date) = %s""",
            (slip.employee, year),
            as_dict=True,
        )
        return {
            "gross":      float(rows[0]["gross"] or 0),
            "deductions": float(rows[0]["deductions"] or 0),
            "net":        float(rows[0]["net"] or 0),
        }
    except Exception:
        frappe.logger("skyengpro").exception("ytd_totals failed for %s", slip.name)
        return {"gross": 0.0, "deductions": 0.0, "net": 0.0}


def employee_field(employee_name: str, fieldname: str, default: str = "") -> str:
    """Read a (possibly-custom) field from an Employee, with safe fallback."""
    try:
        v = frappe.db.get_value("Employee", employee_name, fieldname)
        return str(v) if v else default
    except Exception:
        return default


def company_field(company_name: str, fieldname: str, default: str = "") -> str:
    """Read a (possibly-custom) field from a Company, with safe fallback."""
    try:
        v = frappe.db.get_value("Company", company_name, fieldname)
        return str(v) if v else default
    except Exception:
        return default


def brand_image_data_uri(filename: str) -> str:
    """Read a brand asset under skyengpro_brand/public/brand/skyengpro/
    and return a base64 `data:image/png;base64,...` URI.

    Why a data URI: wkhtmltopdf's PDF generator routinely fails to fetch
    `/assets/...` URLs at render time (the request is made over loopback
    against gunicorn, which may 403/404 depending on auth state). Inline
    base64 sidesteps the network entirely and renders reliably.
    """
    try:
        path = os.path.join(
            frappe.get_app_path("skyengpro_brand", "public", "brand", "skyengpro"),
            filename,
        )
        if not os.path.exists(path):
            return ""
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        ext = filename.rsplit(".", 1)[-1].lower()
        mime = "image/png" if ext == "png" else f"image/{ext}"
        return f"data:{mime};base64,{data}"
    except Exception:
        frappe.logger("skyengpro").exception("brand_image_data_uri(%s) failed", filename)
        return ""


def total_imposable(slip) -> float:
    """Bareme imposable for IRPP: gross minus the IRPP-exempt allowances.

    Cameroon CGI: transport + logement allowances are IRPP-exempt up to legal
    caps. We approximate by subtracting the full transport + housing component
    amounts from gross pay — matches the PDF's `Total imposable` cell.
    """
    exempt_components = {"Prime de Transport", "Prime de Logement"}
    exempt_total = sum(
        float(row.amount or 0)
        for row in (slip.earnings or [])
        if row.salary_component in exempt_components
    )
    return float(slip.gross_pay or 0) - exempt_total


def total_cotisation(slip) -> float:
    """Base for CNPS contribution: capped at 750,000 XAF/month per Cameroon law,
    and excludes non-cotisable allowances. Approximates by taking gross_pay and
    capping at the legal ceiling.
    """
    CNPS_CEILING = 750_000.0
    return min(float(slip.gross_pay or 0), CNPS_CEILING)
