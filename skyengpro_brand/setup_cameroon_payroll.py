"""Canonical Cameroon payroll setup — Salary Components + the
`Cameroon Standard 2026` Salary Structure.

Designed for the 100k–500k XAF net salary range under Cameroon labour
+ tax law, but the structure is not range-specific: per-employee
differences live on the Salary Structure Assignment (`base` =
Salaire de Base, plus Additional Salary entries for variable primes),
not on the structure itself. One structure, every employee.

Tax / cotisation rates baked in (verify with current Code Général des
Impôts before each fiscal year):

  Employee side
  ─────────────
  CNPS Salariale (PVID)   4.2 % of min(SBI, 750 000)
  CFC Salarial            1   % of SBI
  IRPP (progressive)      11 / 16.5 / 27.5 / 38.5 % on SNI mensuel
                          brackets: 166 667 / 250 000 / 416 667
                          (= 2M / 3M / 5M annual / 12)
  CAC                     10 % of IRPP
  TDL                     bracket schedule on SBI
  RAV                     bracket schedule on SBI

  Employer side (statistical — printed but doesn't reduce net)
  ─────────────
  CNPS Patronale          12.95 % of min(SBI, 750 000)   ← combined
                          (PVID 4.2 + Prestations Familiales 7 +
                           Risques Professionnels 1.75 — assumes
                           low-risk class for IT / engineering /
                           services. If your CNPS RP class is 2.5%
                           or 5%, edit CNPS_P_RATE below.)
  CFC Patronal            1.5 % of SBI
  FNE Patronal            1   % of SBI

Where:
  SBI (Salaire Brut Imposable) =
      SB + max(0, PT − 30 000)
         + max(0, PL − min(PL, SB×0.15, 500 000))
         + PA

  SNI (Salaire Net Imposable mensuel) =
      max(0, SBI × 0.70 − CNPS_S − 41 667)
        # 0.70  = abattement 30 % frais professionnels
        # 41 667 = abattement annuel 500 000 / 12

Idempotent:
  * Components are upserted (formula updated if it changed).
  * The `Cameroon Standard 2026` structure is created only if missing —
    a re-run preserves any draft / submitted edits made via the UI.
  * To roll out a 2027 update, change `STRUCTURE_NAME` and re-run; the
    new structure is created alongside, employees migrate via SSA.
"""
import frappe


# Where the CNPS Risques Professionnels rate lives — one place to edit.
# 1.75 % = low-risk class (IT / services / engineering).
# 2.5  % = medium.
# 5    % = high (construction / industry).
CNPS_P_RP_RATE = 0.0175

# Combined CNPS Patronale = PVID + Prestations Familiales + Risques Pro
# (employer side). Capped on the same 750 000 base as the employee side.
CNPS_P_TOTAL_RATE = 0.042 + 0.07 + CNPS_P_RP_RATE   # 12.95 % default

STRUCTURE_NAME = "Cameroon Standard 2026"

# Per-company Salary Component → GL Account mapping. Applied to each
# Salary Component's `accounts` child table on every migrate. Without
# this mapping, Salary Slip submission fails with
# "Salary Component X is not linked to an account".
#
# Statistical components (CNPS Patronale / CFC Patronal / FNE Patronal /
# SNI / Salaire Net Imposable) are intentionally NOT mapped — they
# don't post GL entries. Employer-side charges are booked via a
# separate monthly Journal Entry (Option A in the docs).
#
# Salaire Brut Imposable is also unmapped — its
# `do_not_include_in_total=1` flag excludes it from
# `get_salary_components_for_gl_entries()` so no GL post happens.
COMPONENT_ACCOUNT_MAP = {
    "Sky Engineering Professional": [
        # ── Earnings (debit to expense) ──
        ("Salaire de Base",       "6611-Appointements salaires et commissions - SEP"),
        ("Prime de Transport",    "6634-Indemnités de transport - SEP"),
        ("Prime de Logement",     "6631-Indemnités de logement - SEP"),
        ("Prime d'Ancienneté",    "6612-Primes et gratifications - SEP"),
        ("Prime de Restauration", "6612-Primes et gratifications - SEP"),
        ("Prime d'Assurance",     "6618-Autres rémunérations directes - SEP"),
        # ── Employee deductions (credit to liability) ──
        ("CNPS Salariale",        "4318-Autres cotisations sociales - SEP"),
        ("CFC",                   "4318-Autres cotisations sociales - SEP"),
        ("IRPP",                  "4422-Impôts et taxes pour les collectivités publiques - SEP"),
        ("CAC",                   "4422-Impôts et taxes pour les collectivités publiques - SEP"),
        ("TDL",                   "4422-Impôts et taxes pour les collectivités publiques - SEP"),
        ("RAV",                   "4422-Impôts et taxes pour les collectivités publiques - SEP"),
    ],
}


# ─────────────────────────────────────────────────────────────
# Salary Component definitions
# ─────────────────────────────────────────────────────────────

# Each spec describes ONE Salary Component. Order matters at slip-
# generation time (see _STRUCTURE_EARNINGS / _STRUCTURE_DEDUCTIONS
# below) — but at the component level, order is irrelevant.
_COMPONENTS = [
    # ── Earnings (real, fully taxable except where noted) ──
    {"name": "Salaire de Base",     "abbr": "SB",  "type": "Earning",
     "is_tax_applicable": 1,
     "description": "Per-employee — set on the Salary Structure Assignment's `base` field."},

    {"name": "Prime de Transport",  "abbr": "PT",  "type": "Earning",
     "is_tax_applicable": 1,
     "description": "Default 30,000 XAF (Cameroon tax-exempt cap). Excess becomes taxable via SBI formula. Override per-employee with an Additional Salary."},

    {"name": "Prime de Logement",   "abbr": "PL",  "type": "Earning",
     "is_tax_applicable": 1,
     "description": "Per-employee. Tax-exempt portion = min(PL, 15% of SB, 500,000). Excess folded into SBI."},

    {"name": "Prime d'Ancienneté",  "abbr": "PA",  "type": "Earning",
     "is_tax_applicable": 1,
     "description": "Per-employee, manual. Cameroon Labor Code: 4% after 2 yrs, +2% per 2 yrs, capped 25%. HR enters via Additional Salary monthly until we wire automatic computation."},

    {"name": "Prime de Restauration", "abbr": "PR", "type": "Earning",
     "is_tax_applicable": 1,
     "description": "Catering / meal allowance. Default 30,000 XAF/month for every employee. Fully taxable in Cameroon (no specific exemption like Prime de Transport's first 30k)."},

    {"name": "Prime d'Assurance", "abbr": "PI", "type": "Earning",
     "is_tax_applicable": 1,
     "description": "Insurance benefit (health, life, etc). Default 0 — set per-employee via Additional Salary or override on the SSA. Treated as fully taxable; if a specific insurance qualifies for a CGI exemption, subtract that portion in the SBI formula."},

    # ── Intermediate calc — STATISTICAL Deduction (idx=1 in the
    # deductions table; see _STRUCTURE_DEDUCTIONS below).
    #
    # Why statistical, and why in deductions:
    #
    #   * Statistical components don't add a row to the slip and don't
    #     post a GL entry (the accrual JE generation iterates slip
    #     rows; missing-account validation never fires for SBI).
    #
    #   * Statistical values DO live in `self.data` for the duration of
    #     the phase that produced them, so subsequent rows in the same
    #     phase can reference SBI by abbreviation in their own
    #     formulas (CNPS_S, CFC, IRPP, TDL, RAV all do).
    #
    #   * Placing SBI in the deductions phase rather than earnings is
    #     mandatory: ERPNext computes earnings BEFORE Additional Salary
    #     entries override per-employee amounts (e.g. Prime de
    #     Transport at 50k or 75k for a specific employee). If SBI ran
    #     in the earnings phase, it would lock in the structure-default
    #     PT and ignore every override. The deductions phase rebuilds
    #     `self.data` from the slip's earnings table — which by then
    #     reflects the post-override values.
    {"name": "Salaire Brut Imposable", "abbr": "SBI", "type": "Deduction",
     "statistical_component": 1,
     "is_tax_applicable": 0,
     "description": "Statistical: taxable base used by every deduction formula. Computed at idx=1 of the deductions phase so it sees Additional Salary overrides on PT / PL / PA / PR / PI."},

    # ── Deductions (employee side, real) ──
    {"name": "CNPS Salariale", "abbr": "CNPS_S", "type": "Deduction",
     "description": "Cotisation salariale CNPS (PVID): 4.2% of capped 750k base."},

    {"name": "CFC", "abbr": "CFC", "type": "Deduction",
     "description": "Crédit Foncier du Cameroun (part salariale): 1% of SBI."},

    {"name": "Salaire Net Imposable", "abbr": "SNI", "type": "Deduction",
     "statistical_component": 1,
     "description": "Statistical: SBI × 0.70 − CNPS_S − 41,667 (abattement annuel 500k/12). Drives IRPP."},

    {"name": "IRPP", "abbr": "IRPP", "type": "Deduction",
     "description": "Impôt sur le Revenu — progressive: 11/16.5/27.5/38.5% on SNI mensuel."},

    {"name": "CAC", "abbr": "CAC", "type": "Deduction",
     "description": "Centimes Additionnels Communaux: 10% of IRPP."},

    {"name": "TDL", "abbr": "TDL", "type": "Deduction",
     "description": "Taxe de Développement Local: bracket schedule on SBI."},

    {"name": "RAV", "abbr": "RAV", "type": "Deduction",
     "description": "Redevance Audiovisuelle: bracket schedule on SBI."},

    # ── Employer (statistical — info only) ──
    {"name": "CNPS Patronale", "abbr": "CNPS_P", "type": "Deduction",
     "statistical_component": 1,
     "description": "PVID 4.2 + PF 7 + RP 1.75 = 12.95% of capped 750k base. Edit CNPS_P_RP_RATE in source if CNPS class changes."},

    {"name": "CFC Patronal", "abbr": "CFC_P", "type": "Deduction",
     "statistical_component": 1,
     "description": "Crédit Foncier (part patronale): 1.5% of SBI."},

    {"name": "FNE Patronal", "abbr": "FNE_P", "type": "Deduction",
     "statistical_component": 1,
     "description": "Fond National de l'Emploi: 1% of SBI. Employer-only (Cameroon)."},
]


# ─────────────────────────────────────────────────────────────
# Salary Structure rows — order matters
# ─────────────────────────────────────────────────────────────

# Each row: (component_name, formula_or_None, condition_or_None,
#            default_amount, amount_based_on_formula)
_STRUCTURE_EARNINGS = [
    # Salaire de Base flows from the SSA's `base` field via formula="base".
    ("Salaire de Base",         "base", None,            None, 1),
    ("Prime de Transport",      None,   None,           30000, 0),
    ("Prime de Logement",       None,   None,               0, 0),
    ("Prime d'Ancienneté",      None,   None,               0, 0),
    ("Prime de Restauration",   None,   None,           30000, 0),
    ("Prime d'Assurance",       None,   None,               0, 0),
]

# Brackets pulled out into named constants so they're greppable.
_TDL_FORMULA = (
    "0 if SBI <= 62000 else "
    "250 if SBI <= 75000 else "
    "500 if SBI <= 100000 else "
    "750 if SBI <= 125000 else "
    "1000 if SBI <= 150000 else "
    "1250 if SBI <= 200000 else "
    "1500 if SBI <= 250000 else "
    "2000 if SBI <= 300000 else "
    "2250 if SBI <= 500000 else "
    "2500"
)

_RAV_FORMULA = (
    "0 if SBI < 50000 else "
    "750 if SBI < 100000 else "
    "1950 if SBI < 200000 else "
    "3250 if SBI < 300000 else "
    "4550 if SBI < 400000 else "
    "5850 if SBI < 500000 else "
    "7150 if SBI < 600000 else "
    "8450 if SBI < 700000 else "
    "9750 if SBI < 800000 else "
    "11050 if SBI < 900000 else "
    "12350 if SBI < 1000000 else "
    "13000"
)

_IRPP_FORMULA = (
    "(SNI * 0.11) if SNI <= 166667 else "
    "(18333.33 + (SNI - 166667) * 0.165) if SNI <= 250000 else "
    "(32083.33 + (SNI - 250000) * 0.275) if SNI <= 416667 else "
    "(78000 + (SNI - 416667) * 0.385)"
)

# ERPNext's salary-formula sandbox does NOT expose Python's `max` / `min`
# builtins. We use ternary expressions instead (`(a if a <= b else b)`
# instead of `min(a, b)`).
#
# SBI lives at idx=1 in DEDUCTIONS (not earnings), even though it's
# really an "earning intermediate". Reason: ERPNext computes earning
# rows BEFORE Additional Salary entries override per-employee amounts
# (Prime de Transport, Prime de Logement, etc.). If SBI were in
# earnings, it would lock in the structure-default amounts and miss
# every per-employee override. Computing it as the FIRST deduction
# (with do_not_include_in_total=1 to keep it out of total_deduction)
# means by the time it runs, the slip's earnings table already
# reflects every Additional Salary override, so SBI sees the right
# values.
_STRUCTURE_DEDUCTIONS = [
    ("Salaire Brut Imposable",
     "SB + (PT - 30000 if PT > 30000 else 0)"
     " + (PL - (PL if (PL <= SB * 0.15 and PL <= 500000) "
     "          else (SB * 0.15 if SB * 0.15 <= 500000 else 500000)) "
     "    if PL > 0 else 0)"
     " + PA + PR + PI",
     None, None, 1),
    ("CNPS Salariale",        "(SBI if SBI <= 750000 else 750000) * 0.042",         None, None, 1),
    ("CFC",                   "SBI * 0.01",                                          None, None, 1),
    ("Salaire Net Imposable",
     "((SBI * 0.7 - CNPS_S - 41667) if (SBI * 0.7 - CNPS_S - 41667) > 0 else 0)",   None, None, 1),
    ("IRPP",                  _IRPP_FORMULA,                                         None, None, 1),
    ("CAC",                   "IRPP * 0.10",                                         None, None, 1),
    ("TDL",                   _TDL_FORMULA,                                          None, None, 1),
    ("RAV",                   _RAV_FORMULA,                                          None, None, 1),
    ("CNPS Patronale",        f"(SBI if SBI <= 750000 else 750000) * {CNPS_P_TOTAL_RATE}",
                              None, None, 1),
    ("CFC Patronal",          "SBI * 0.015",                                         None, None, 1),
    ("FNE Patronal",          "SBI * 0.01",                                          None, None, 1),
]


# ─────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────

def setup_cameroon_payroll():
    """Run all three steps: components, structure, account mapping."""
    _upsert_components()
    _ensure_structure(STRUCTURE_NAME)
    _map_component_accounts()
    frappe.db.commit()


# ─────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────

def _upsert_components():
    """Create or update each Salary Component with its canonical
    abbr, type, statistical flag, and description. Idempotent."""
    for spec in _COMPONENTS:
        name = spec["name"]
        if frappe.db.exists("Salary Component", name):
            sc = frappe.get_doc("Salary Component", name)
        else:
            sc = frappe.new_doc("Salary Component")
            sc.salary_component = name
            sc.name = name

        sc.salary_component       = name
        sc.salary_component_abbr  = spec["abbr"]
        sc.type                   = spec["type"]
        sc.statistical_component  = spec.get("statistical_component", 0)
        sc.is_tax_applicable      = spec.get("is_tax_applicable", 0)
        sc.disabled               = 0
        sc.description            = spec.get("description", "")
        # Disable depends_on_payment_days for every component we manage —
        # ERPNext refuses to combine that flag with `amount_based_on_formula`,
        # and our formula-driven flow assumes monthly fixed amounts (the
        # employee's effective working days are accounted for via the
        # Salary Slip's start_date / end_date, not by pro-rating each
        # component row).
        sc.depends_on_payment_days = 0

        try:
            sc.save(ignore_permissions=True)
        except Exception:
            frappe.logger("skyengpro").exception(
                "_upsert_components: failed for %s", name,
            )


def _ensure_structure(name: str):
    """Create the Salary Structure if missing. Existing structure (any
    docstatus) is left alone — the assumption is that re-running this
    on every migrate must NEVER mutate a submitted Salary Structure
    that's already in production. To roll out a new version, bump the
    version in the name (e.g. `Cameroon Standard 2027`)."""
    if frappe.db.exists("Salary Structure", name):
        return

    company = _pick_default_company()
    if not company:
        frappe.logger("skyengpro").warning(
            "_ensure_structure: no Company on this site — skipping",
        )
        return

    ss = frappe.new_doc("Salary Structure")
    ss.name              = name
    ss.is_active         = "Yes"
    ss.payroll_frequency = "Monthly"
    ss.company           = company
    ss.currency          = frappe.db.get_value("Company", company, "default_currency") or "XAF"
    ss.salary_slip_based_on_timesheet = 0

    for (cname, formula, condition, default_amount, abof) in _STRUCTURE_EARNINGS:
        ss.append("earnings", _row(cname, formula, condition, default_amount, abof))
    for (cname, formula, condition, default_amount, abof) in _STRUCTURE_DEDUCTIONS:
        ss.append("deductions", _row(cname, formula, condition, default_amount, abof))

    ss.insert(ignore_permissions=True)
    # Submit so it's usable for assignments. If validation fails (e.g.
    # missing Salary Component Account on this Company), the structure
    # stays in draft and HR can fix the missing account in the UI.
    try:
        ss.submit()
    except Exception:
        frappe.logger("skyengpro").exception(
            "_ensure_structure: %s saved but not submitted — fix Salary "
            "Component → Accounts mapping for company %s and submit "
            "manually.", name, company,
        )


def _row(component_name, formula, condition, default_amount, amount_based_on_formula):
    abbr = next(c["abbr"] for c in _COMPONENTS if c["name"] == component_name)
    row = {
        "salary_component":         component_name,
        "abbr":                     abbr,
        "amount_based_on_formula":  amount_based_on_formula,
        # See _upsert_components — every row is monthly fixed,
        # not pro-rated by individual day.
        "depends_on_payment_days":  0,
    }
    if formula:
        row["formula"] = formula
    if condition:
        row["condition"] = condition
    if default_amount is not None:
        row["amount"] = default_amount
    return row


def _map_component_accounts():
    """Upsert each Salary Component's `accounts` child row for the
    company-specific GL account. Idempotent — a re-run leaves an
    already-correct mapping untouched, and corrects any drift."""
    for company, mapping in COMPONENT_ACCOUNT_MAP.items():
        if not frappe.db.exists("Company", company):
            continue
        for component, account in mapping:
            if not frappe.db.exists("Salary Component", component):
                frappe.logger("skyengpro").warning(
                    "_map_component_accounts: missing component %s — skipping",
                    component,
                )
                continue
            if not frappe.db.exists("Account", account):
                frappe.logger("skyengpro").warning(
                    "_map_component_accounts: missing account %s for company %s — skipping",
                    account, company,
                )
                continue
            existing = frappe.db.get_value(
                "Salary Component Account",
                {"parent": component, "company": company},
                "name",
            )
            if existing:
                cur = frappe.db.get_value("Salary Component Account", existing, "account")
                if cur == account:
                    continue
                frappe.db.set_value(
                    "Salary Component Account", existing, "account", account,
                    update_modified=False,
                )
                continue
            sc = frappe.get_doc("Salary Component", component)
            sc.append("accounts", {"company": company, "account": account})
            sc.save(ignore_permissions=True)


def _pick_default_company():
    """Return the company we should anchor the canonical structure
    on. Prefers `Sky Engineering Professional` if present, else falls
    back to the first Company in the system, else None."""
    if frappe.db.exists("Company", "Sky Engineering Professional"):
        return "Sky Engineering Professional"
    rows = frappe.db.get_all("Company", limit_page_length=1, pluck="name")
    return rows[0] if rows else None
