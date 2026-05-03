"""Bulletin de Paie installer — runs from after_install / after_migrate.

Two responsibilities:
  1. Ensure Cameroon HR custom fields exist on Employee and Company so the
     Bulletin de Paie template has fields to read.
  2. Insert/refresh the `Bulletin de Paie` Print Format with the canonical
     HTML template (mimics the PDF the user provided as ground-truth).

Idempotent on every call — the print format HTML is rewritten each time,
so updates land via image rebuild + bench migrate.
"""
import frappe


# ---------------------------------------------------------------------------
# Custom field definitions
# ---------------------------------------------------------------------------

EMPLOYEE_FIELDS = [
    {
        "fieldname": "section_break_cm_payroll",
        "label": "Cameroon HR / Payroll",
        "fieldtype": "Section Break",
        "insert_after": "salary_currency",
        "collapsible": 1,
    },
    {"fieldname": "niu_employee", "label": "Numéro contribuable",
     "fieldtype": "Data", "insert_after": "section_break_cm_payroll"},
    {"fieldname": "cnps_employee", "label": "Matricule CNPS",
     "fieldtype": "Data", "insert_after": "niu_employee"},
    {"fieldname": "cnps_office", "label": "Lieu de cotisation CPS",
     "fieldtype": "Data", "insert_after": "cnps_employee"},
    {"fieldname": "column_break_cm_payroll", "label": "",
     "fieldtype": "Column Break", "insert_after": "cnps_office"},
    {"fieldname": "category", "label": "Catégorie",
     "fieldtype": "Data", "insert_after": "column_break_cm_payroll",
     "description": "Conv. coll. category — e.g. 'VII C'"},
    {"fieldname": "level", "label": "Niveau",
     "fieldtype": "Data", "insert_after": "category",
     "description": "Education / professional level — e.g. 'Master II'"},
    {"fieldname": "collective_convention", "label": "Conv. coll. Nat.",
     "fieldtype": "Data", "insert_after": "level",
     "default": "Du Commerce"},
    {"fieldname": "monthly_hours", "label": "Horaire mensuel",
     "fieldtype": "Float", "insert_after": "collective_convention",
     "default": "173.33"},
]

COMPANY_FIELDS = [
    {"fieldname": "niu_company", "label": "Numéro contribuable (NIU)",
     "fieldtype": "Data", "insert_after": "tax_id"},
    {"fieldname": "cnps_company", "label": "Numéro CNPS",
     "fieldtype": "Data", "insert_after": "niu_company"},
    {"fieldname": "company_phone", "label": "Téléphone",
     "fieldtype": "Data", "insert_after": "cnps_company"},
    {"fieldname": "company_address_lines", "label": "Adresse (multi-lignes)",
     "fieldtype": "Small Text", "insert_after": "company_phone",
     "description": "Address shown on Bulletin de Paie. One line per row."},
]


def ensure_payroll_custom_fields():
    """Create / update Cameroon HR custom fields. Idempotent."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({
        "Employee": EMPLOYEE_FIELDS,
        "Company": COMPANY_FIELDS,
    }, ignore_validate=True)
    frappe.db.commit()
    frappe.logger("skyengpro").info("Bulletin de Paie custom fields synced.")


# ---------------------------------------------------------------------------
# Print Format HTML
# ---------------------------------------------------------------------------

# The HTML below is rendered by Frappe's Jinja engine inside a `print_format`
# context. `doc` is the Salary Slip; `frappe` is the framework module.
# Helper functions live in skyengpro_brand.payroll_helpers and are imported
# at the top of the template.
#
# Layout matches the user's reference PDF:
#   1. Header: SkyEngPro logo top-left, "BULLETIN DE PAIE" title centered.
#   2. Two-column info block: company info (left) + period/matricule (right).
#   3. Employee info block: Cotisation / Conv.coll / Niveau / Horaire / Emploi /
#      Catégorie / NIU / Matricule CNPS — name shown right-aligned bold.
#   4. Leave summary: Acquis/Pris/Restant for N-1 and N + dates.
#   5. Combined main table: N° | Désignation | Nombre | Part salariale (Base /
#      Gain / Taux / Retenue) | Part patronale (Taux / Retenue), with sections
#      for Rémunérations, totals, retenues patronales, retenues salariales.
#   6. Période/Année summary: Salaire brut / Charges / Net à payer × 2 rows.
#   7. Footer disclosure note.
BULLETIN_HTML = r"""
{%- from "templates/print_formats/standard_macros.html" import add_header -%}
{%- set emp = frappe.get_doc("Employee", doc.employee) -%}
{%- set company = frappe.get_doc("Company", doc.company) -%}
{%- set _split = split_deductions(doc.deductions) -%}
{%- set employer = _split[0] -%}
{%- set salarial = _split[1] -%}
{%- set ytd = ytd_totals(doc) -%}
{%- set logo = brand_image_data_uri("payslip_logo.png") -%}
{%- set ccy = doc.currency or "XAF" -%}
{# PDF shows integer amounts with thousand separators (e.g. 457,551).
   Use Python's format spec directly — no currency prefix, no decimals. #}
{%- macro money(v) -%}{{ "{:,.0f}".format(v or 0) }}{%- endmacro -%}

<style>
  /* Tight pixel-equivalent layout — must fit on one A4 page (297mm × 210mm
     with 8mm margins = 281mm × 194mm usable). All paddings in mm; row
     heights kept minimal. */
  .bp { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 8pt; color: #222; line-height: 1.15; }
  .bp h1 { text-align: center; font-size: 14pt; margin: 0 0 2mm; letter-spacing: .3mm; font-weight: 700; }
  .bp table { border-collapse: collapse; }
  .bp .top { width: 100%; margin: 0 0 2mm; }
  .bp .top td { vertical-align: top; padding: 0; }
  .bp .top .logo img { height: 16mm; }
  .bp .info { width: 100%; }
  .bp .info td { vertical-align: top; padding: 1mm 2mm; font-size: 8pt; }
  .bp .info-left, .bp .info-right { border: .25mm solid #555; }
  .bp .emp { width: 100%; margin-top: 1mm; }
  .bp .emp td { padding: .4mm 2mm; font-size: 8pt; vertical-align: top; }
  .bp .emp-block { border: .25mm solid #555; }
  .bp .emp-grid td { padding: .3mm 1.5mm; }
  .bp .emp-name { text-align: right; font-weight: bold; font-size: 9.5pt; padding: 3mm 3mm 0 0; vertical-align: top; }
  .bp .leave { width: 100%; margin: 1.5mm 0 1mm; }
  .bp .leave th, .bp .leave td { border: .25mm solid #555; padding: .4mm 1.5mm; font-size: 7.5pt; }
  .bp .leave th { background: #f0f0f0; font-weight: bold; }
  .bp .main { width: 100%; margin-top: 1mm; font-size: 7.5pt; }
  .bp .main th, .bp .main td { border: .25mm solid #555; padding: .35mm 1.2mm; }
  .bp .main th { background: #f0f0f0; font-weight: bold; text-align: center; vertical-align: middle; }
  .bp .num { text-align: right; }
  .bp .ctr { text-align: center; }
  .bp .section-row td { background: #fafafa; font-weight: bold; padding: .6mm 1.5mm; }
  .bp .total-row td { font-weight: bold; padding: .6mm 1.5mm; }
  .bp .summary { width: 100%; margin-top: 2mm; font-size: 8pt; }
  .bp .summary th, .bp .summary td { border: .25mm solid #555; padding: .8mm 1.5mm; }
  .bp .summary th { background: #f0f0f0; font-weight: bold; text-align: center; }
  .bp .signature-cell { width: 28%; vertical-align: middle; text-align: center; padding: 2mm 1mm; }
  .bp .footer { margin-top: 2mm; font-size: 7pt; font-style: italic; color: #555; text-align: center; }
</style>

<div class="bp">

  {# ── 1. Top: logo + title ─────────────────────────────────────────── #}
  <table class="top"><tr>
    <td class="logo" style="width:30%"><img src="{{ logo }}" /></td>
    <td><h1>BULLETIN DE PAIE</h1></td>
    <td style="width:30%"></td>
  </tr></table>

  {# ── 2. Company / Period info ─────────────────────────────────────── #}
  <table class="info"><tr>
    <td class="info-left" style="width:55%">
      <strong>{{ (company.company_name or doc.company)|upper }}</strong><br/>
      Tél : {{ company_field(doc.company, "company_phone") }}<br/>
      {% set addr_lines = (company_field(doc.company, "company_address_lines") or "").splitlines() %}
      {% for line in addr_lines %}{{ line }}<br/>{% endfor %}
      Numéro de contribuable : {{ company_field(doc.company, "niu_company") }}<br/>
      Numéro CNPS : {{ company_field(doc.company, "cnps_company") }}
    </td>
    <td style="width:2%"></td>
    <td class="info-right" style="width:43%">
      Période du <strong>{{ frappe.utils.formatdate(doc.start_date, "dd/MM/yyyy") }}</strong>
        au <strong>{{ frappe.utils.formatdate(doc.end_date, "dd/MM/yyyy") }}</strong><br/>
      Paiement le <strong>{{ frappe.utils.formatdate(doc.posting_date, "dd/MM/yyyy") }}</strong>
        par {{ doc.payment_days and "Virement Bancaire" or "Virement Bancaire" }}<br/>
      <br/>
      Matricule&nbsp;&nbsp;&nbsp;<strong>{{ emp.employee_number or doc.employee }}</strong><br/>
      Ancienneté&nbsp;&nbsp;<strong>{{ anciennete(emp.date_of_joining) }}</strong>
    </td>
  </tr></table>

  {# ── 3. Employee details block — 2-column compact grid + name on right #}
  <table class="emp emp-block"><tr>
    <td style="width:70%">
      <table class="emp emp-grid" style="width:100%">
        <tr>
          <td style="width:22%">Cotisation à</td>
          <td style="width:28%"><strong>CPS de {{ employee_field(doc.employee, "cnps_office") }}</strong></td>
          <td style="width:22%">Emploi</td>
          <td style="width:28%"><strong>{{ doc.designation or emp.designation }}</strong></td>
        </tr>
        <tr>
          <td>Conv.coll. Nat.</td>
          <td><strong>{{ employee_field(doc.employee, "collective_convention", "Du Commerce") }}</strong></td>
          <td>Catégorie</td>
          <td><strong>{{ employee_field(doc.employee, "category") }}</strong></td>
        </tr>
        <tr>
          <td>Niveau</td>
          <td><strong>{{ employee_field(doc.employee, "level") }}</strong></td>
          <td>Numero contribuable</td>
          <td><strong>{{ employee_field(doc.employee, "niu_employee") }}</strong></td>
        </tr>
        <tr>
          <td>Horaire</td>
          <td><strong>{{ "%.2f"|format(emp.monthly_hours or 173.33) }}</strong></td>
          <td>Matricule CNPS</td>
          <td><strong>{{ employee_field(doc.employee, "cnps_employee") }}</strong></td>
        </tr>
      </table>
    </td>
    <td class="emp-name">M. {{ doc.employee_name }}</td>
  </tr></table>

  {# ── 4. Leave summary — horizontal compact layout (3 N-1 cells + 3 N
        cells in 2 rows, with Payés + Dates on the right) ───────────── #}
  {%- set leave_total = (emp.leave_balance or 0) -%}
  <table class="leave">
    <thead>
      <tr>
        <th colspan="2" style="width:18%">Congés (en jours)</th>
        <th style="width:8%">Payés</th>
        <th colspan="2" style="width:30%">Dates de congés</th>
        <th colspan="2" style="width:18%">Congés (en jours)</th>
        <th style="width:8%">Payés</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Acquis N-1</td><td class="num">-</td><td class="num">-</td>
        <td colspan="2"></td>
        <td>Acquis N</td><td class="num">-</td><td class="num">-</td>
      </tr>
      <tr>
        <td>Pris N-1</td><td class="num">-</td><td class="num">-</td>
        <td colspan="2"></td>
        <td>Pris N</td><td class="num">-</td><td class="num">-</td>
      </tr>
      <tr>
        <td>Restant N-1</td><td class="num">-</td><td class="num">-</td>
        <td colspan="2"></td>
        <td>Restant N</td><td class="num">{{ "%.2f"|format(leave_total) }}</td><td class="num">-</td>
      </tr>
    </tbody>
  </table>

  {# ── 5. Combined main table ───────────────────────────────────────── #}
  <table class="main">
    <thead>
      <tr>
        <th rowspan="2" style="width:5%">N°</th>
        <th rowspan="2" style="width:30%">Désignation</th>
        <th rowspan="2" style="width:7%">Nombre</th>
        <th colspan="4" style="width:38%">Part salariale</th>
        <th colspan="2" style="width:20%">Part patronale</th>
      </tr>
      <tr>
        <th style="width:9%">Base</th>
        <th style="width:9%">Gain</th>
        <th style="width:7%">Taux</th>
        <th style="width:13%">Retenue</th>
        <th style="width:7%">Taux</th>
        <th style="width:13%">Retenue</th>
      </tr>
    </thead>
    <tbody>

      {# Rémunérations #}
      <tr class="section-row"><td colspan="9">Rémunérations</td></tr>
      {% for r in doc.earnings %}
      <tr>
        <td class="ctr">{{ component_code(r.salary_component) }}</td>
        <td>{{ component_label(r.salary_component) }}</td>
        <td class="num">{% if r.salary_component == "Salaire de Base" %}{{ "%.2f"|format(emp.monthly_hours or 173.33) }}{% endif %}</td>
        <td class="num">{% if r.salary_component == "Salaire de Base" and emp.monthly_hours %}{{ "%.0f"|format((r.amount or 0) / (emp.monthly_hours or 173.33)) }}{% endif %}</td>
        <td class="num">{{ money(r.amount) }}</td>
        <td></td><td></td><td></td><td></td>
      </tr>
      {% endfor %}

      <tr class="total-row">
        <td></td><td>Total Brut</td><td></td><td></td>
        <td class="num">{{ money(doc.gross_pay) }}</td>
        <td colspan="4"></td>
      </tr>
      <tr class="total-row">
        <td></td><td>Total imposable</td><td></td>
        <td class="num">{{ money(total_imposable(doc)) }}</td>
        <td colspan="5"></td>
      </tr>
      <tr class="total-row">
        <td></td><td>Total cotisation</td><td></td>
        <td class="num">{{ money(total_cotisation(doc)) }}</td>
        <td colspan="5"></td>
      </tr>

      {# Retenues patronales (employer side) #}
      {% if employer %}
      <tr class="section-row"><td colspan="9">Retenues patronales</td></tr>
      {% for r in employer %}
      <tr>
        <td class="ctr">{{ component_code(r.salary_component) }}</td>
        <td>{{ component_label(r.salary_component) }}</td>
        <td></td>
        <td class="num">{{ money(format_base(r, doc)) }}</td>
        <td colspan="3"></td>
        <td class="num">{{ format_taux(r) }}</td>
        <td class="num">{{ money(r.amount) }}</td>
      </tr>
      {% endfor %}
      {% endif %}

      {# Retenues salariales #}
      <tr class="section-row"><td colspan="9">Retenues salariales</td></tr>
      {% for r in salarial %}
      <tr>
        <td class="ctr">{{ component_code(r.salary_component) }}</td>
        <td>{{ component_label(r.salary_component) }}</td>
        <td></td>
        <td class="num">{{ money(format_base(r, doc)) }}</td>
        <td></td>
        <td class="num">{{ format_taux(r) }}</td>
        <td class="num">{{ money(r.amount) }}</td>
        <td colspan="2"></td>
      </tr>
      {% endfor %}

      {%- set salarial_total = (salarial | sum(attribute="amount")) -%}
      {%- set employer_total = (employer | sum(attribute="amount")) -%}
      <tr class="total-row">
        <td></td><td>Total Retenues</td><td></td><td></td><td></td><td></td>
        <td class="num">{{ money(salarial_total) }}</td>
        <td></td>
        <td class="num">{{ money(employer_total) }}</td>
      </tr>

    </tbody>
  </table>

  {# ── 6. Période / Année summary ───────────────────────────────────── #}
  <table class="summary">
    <thead>
      <tr>
        <th rowspan="3" class="signature-cell">Signature<br/><br/><br/></th>
        <th></th>
        <th>Salaire brut</th>
        <th>Charges</th>
        <th>Net à payer</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="ctr"><strong>F CFA</strong></td>
        <td class="ctr label">Période</td>
        <td class="num">{{ money(doc.gross_pay) }}</td>
        <td class="num">{{ money(doc.total_deduction) }}</td>
        <td class="num"><strong>{{ money(doc.net_pay) }}</strong></td>
      </tr>
      <tr>
        <td></td>
        <td class="ctr label">Année</td>
        <td class="num">{{ money(ytd.gross) }}</td>
        <td class="num">{{ money(ytd.deductions) }}</td>
        <td class="num"><strong>{{ money(ytd.net) }}</strong></td>
      </tr>
    </tbody>
  </table>

  <div class="footer">
    Ce bulletin est établi en Francs CFA. Pour vous aider à faire valoir vos droits, conserver ce bulletin de paie sans limitation de durée.
  </div>
</div>
"""


def _ensure_module_custom_flag():
    """Mark `Module Def: SkyEngPro Brand` as custom so Frappe's print-format
    loader skips the filesystem path lookup and reads `print_format.html`
    directly. Without this flag, `get_print_format()` calls `get_module_path`
    which tries to import `skyengpro_brand.skyengpro_brand` (the submodule
    derived from the scrubbed module name) — which doesn't exist as a
    Python package and raises ModuleNotFoundError.
    """
    if frappe.db.exists("Module Def", "SkyEngPro Brand"):
        cur = frappe.db.get_value("Module Def", "SkyEngPro Brand", "custom")
        if not cur:
            frappe.db.set_value("Module Def", "SkyEngPro Brand", "custom", 1)


def install_bulletin_de_paie():
    """Insert/refresh the `Bulletin de Paie` Print Format. Idempotent."""
    _ensure_module_custom_flag()
    name = "Bulletin de Paie"
    if frappe.db.exists("Print Format", name):
        pf = frappe.get_doc("Print Format", name)
    else:
        pf = frappe.new_doc("Print Format")
        pf.name = name
    pf.update({
        "doc_type": "Salary Slip",
        "module": "Payroll",
        "standard": "No",
        "disabled": 0,
        "custom_format": 1,
        "print_format_type": "Jinja",
        "html": BULLETIN_HTML,
        "default_print_language": "fr",
        "font_size": 9,
        "margin_top": 8,
        "margin_bottom": 8,
        "margin_left": 8,
        "margin_right": 8,
        "page_number": "Hide",
    })
    pf.flags.ignore_permissions = True
    if pf.is_new():
        pf.insert(ignore_permissions=True)
    else:
        pf.save(ignore_permissions=True)
    frappe.db.commit()
    frappe.logger("skyengpro").info("Bulletin de Paie print format synced.")


def set_bulletin_as_default_print_format():
    """Make 'Bulletin de Paie' the default Print Format for Salary Slip
    via a Property Setter so every user's print dialog auto-selects it.
    """
    name = "Salary Slip-main-default_print_format"
    if frappe.db.exists("Property Setter", name):
        ps = frappe.get_doc("Property Setter", name)
    else:
        ps = frappe.new_doc("Property Setter")
    ps.update({
        "doctype_or_field": "DocType",
        "doc_type": "Salary Slip",
        "property": "default_print_format",
        "value": "Bulletin de Paie",
        "property_type": "Data",
    })
    ps.flags.ignore_permissions = True
    if ps.is_new():
        ps.insert(ignore_permissions=True)
    else:
        ps.save(ignore_permissions=True)
    frappe.db.commit()


# ---------------------------------------------------------------------------
# Combined entry point — called from install.after_install
# ---------------------------------------------------------------------------

def setup_payroll():
    """Run all payroll setup steps in order."""
    ensure_payroll_custom_fields()
    install_bulletin_de_paie()
    set_bulletin_as_default_print_format()
