"""Per-invoice Company Bank Account picker.

Adds a `company_bank_account` Link field on Sales Invoice and rewires
the SkyEngPro Invoice print format so it prints exactly the bank the
user picked — falling back to "all company banks" when the field is
left blank, which preserves the existing behaviour.

Why this exists
───────────────
The print format used to render every Bank Account where
`company=doc.company AND is_company_account=1`. With three SEP bank
accounts active (CBC, BGFI, ECOBANK), every invoice rendered all
three side-by-side — there was no way for the user to point a
specific customer at a specific bank for a specific invoice.

Idempotent — re-running on every migrate is safe and cheap.
"""
import frappe


# ─────────────────────────────────────────────────────────────
# Custom Field on Sales Invoice
# ─────────────────────────────────────────────────────────────

_FIELD = {
    "fieldname":   "company_bank_account",
    "label":       "Company Bank Account (for invoice display)",
    "fieldtype":   "Link",
    "options":     "Bank Account",
    # Sit next to the other "how this gets paid" fields so it's
    # discoverable. payment_terms_template is on the standard
    # ERPNext layout in the Payment Terms section.
    "insert_after": "payment_terms_template",
    "description": (
        "Pick which company bank account appears on the printed "
        "invoice PDF. Leave blank to show all of this company's "
        "bank accounts."
    ),
    # link_filters left empty: a Client Script (installed below)
    # owns the dropdown filter via frm.set_query. Reasoning:
    #   * Array-of-triplets format `[[…,"=",0]]` triggers a Frappe v16
    #     frontend parsing bug that mangles integer-0 values into
    #     `{"=":[0,null]}` and crashes the backend.
    #   * Dict format `{"is_company_account":1,"disabled":0}` doesn't
    #     crash but the v16 autocomplete returns zero results
    #     regardless — the static-filter code path doesn't surface
    #     them in the dropdown.
    #   * Client Script with `frm.set_query` is reliable across
    #     versions and has the bonus of dynamic filtering on
    #     `frm.doc.company` (so the dropdown narrows to the
    #     invoice's company, which static filters can't do).
    "link_filters":      "[]",
    "in_standard_filter": 0,
    "translatable":       0,
    "no_copy":            1,
}


def ensure_invoice_bank_field():
    """Create the Custom Field idempotently."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field
    create_custom_field("Sales Invoice", _FIELD)


# ─────────────────────────────────────────────────────────────
# Print Format patch
# ─────────────────────────────────────────────────────────────

_PRINT_FORMAT_NAME = "SkyEngPro Invoice"

# Two known-good shapes of the old block — depending on whether the
# user's HTML uses CRLF, has trailing whitespace, etc. Each one is a
# verbatim slice that we string-replace in place.
_OLD_BLOCKS = [
    """{%- set bank_accounts = frappe.get_all("Bank Account",
    filters={"company": doc.company, "is_company_account": 1, "disabled": 0},
    fields=["account_name", "bank", "bank_account_no", "iban", "branch_code"],
    order_by="bank asc") -%}""",
]

_NEW_BLOCK = """{% if doc.company_bank_account %}
{%- set _selected = frappe.db.get_value("Bank Account", doc.company_bank_account,
    ["account_name", "bank", "bank_account_no", "iban", "branch_code"], as_dict=True) -%}
{%- set bank_accounts = [_selected] if _selected else [] -%}
{% else %}
{%- set bank_accounts = frappe.get_all("Bank Account",
    filters={"company": doc.company, "is_company_account": 1, "disabled": 0},
    fields=["account_name", "bank", "bank_account_no", "iban", "branch_code"],
    order_by="bank asc") -%}
{% endif %}"""

# Marker the new block contains. Used to detect "already patched"
# state cheaply, so re-runs on migrate are a no-op.
_PATCHED_MARKER = "doc.company_bank_account"


def update_invoice_print_format():
    """Patch the SkyEngPro Invoice print format so it honours
    `doc.company_bank_account` when set, falling back to the
    legacy "all banks" behaviour otherwise. Idempotent."""
    if not frappe.db.exists("Print Format", _PRINT_FORMAT_NAME):
        frappe.logger("skyengpro").info(
            "update_invoice_print_format: %s not found — skipping",
            _PRINT_FORMAT_NAME,
        )
        return

    pf = frappe.get_doc("Print Format", _PRINT_FORMAT_NAME)
    html = pf.html or ""

    if _PATCHED_MARKER in html:
        return  # already patched on a previous run

    for old in _OLD_BLOCKS:
        if old in html:
            pf.html = html.replace(old, _NEW_BLOCK, 1)
            pf.save(ignore_permissions=True)
            frappe.logger("skyengpro").info(
                "update_invoice_print_format: patched %s", _PRINT_FORMAT_NAME,
            )
            return

    frappe.logger("skyengpro").warning(
        "update_invoice_print_format: legacy bank block not found in %s — "
        "the print format may have been hand-edited; review and apply the "
        "company_bank_account branch manually.",
        _PRINT_FORMAT_NAME,
    )


# ─────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────

_CLIENT_SCRIPT_NAME = "Sales Invoice — company_bank_account filter"

_CLIENT_SCRIPT_BODY = (
    "frappe.ui.form.on('Sales Invoice', {"
    " setup(frm) {"
    "   frm.set_query('company_bank_account', function() {"
    "     return {"
    "       filters: {"
    "         is_company_account: 1,"
    "         disabled: 0,"
    "         company: frm.doc.company || ''"
    "       }"
    "     };"
    "   });"
    " },"
    " company(frm) {"
    "   frm.set_value('company_bank_account', null);"
    " }"
    "});"
)


def ensure_invoice_bank_client_script():
    """Install the Client Script that filters the company_bank_account
    dropdown to (is_company_account=1, disabled=0, company=doc.company)
    and clears the picked bank when the invoice's Company changes.

    Idempotent — re-runs upsert the script body and re-enable the
    rule, so an admin who toggled it off in the UI gets it back on
    the next migrate.
    """
    if frappe.db.exists("Client Script", _CLIENT_SCRIPT_NAME):
        cs = frappe.get_doc("Client Script", _CLIENT_SCRIPT_NAME)
        cs.dt      = "Sales Invoice"
        cs.view    = "Form"
        cs.script  = _CLIENT_SCRIPT_BODY
        cs.enabled = 1
        cs.save(ignore_permissions=True)
        return
    cs = frappe.get_doc({
        "doctype": "Client Script",
        "name":    _CLIENT_SCRIPT_NAME,
        "dt":      "Sales Invoice",
        "view":    "Form",
        "script":  _CLIENT_SCRIPT_BODY,
        "enabled": 1,
    })
    cs.insert(ignore_permissions=True)


def setup_invoice_bank_selection():
    """Run all three steps. Called from install.after_install."""
    ensure_invoice_bank_field()
    ensure_invoice_bank_client_script()
    update_invoice_print_format()
    frappe.db.commit()
