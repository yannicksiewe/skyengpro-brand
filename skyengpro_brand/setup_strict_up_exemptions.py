"""Property Setters that exempt specific Link fields from User Permission
filtering, so that `apply_strict_user_permissions=1` doesn't block
multi-company users from creating ordinary docs.

Why this exists
───────────────
This site has `System Settings.apply_strict_user_permissions=1`, which
makes Frappe enforce User Permission filters even on EMPTY link fields.
Combined with multi-company users (e.g. Branda, who has UPs for both
adorsys and SEP), every doc with a Company-linked optional field
silently fails the per-doc permission check:

    pi = new Purchase Invoice
    pi.company = "SEP"               # OK, in Branda's UPs
    pi.represents_company = NULL     # str(None) NOT in [adorsys, SEP] → DENY
    pi.letter_head = "Company …Grey" # NULL company on the LH → DENY

The user-facing symptom is "You need the 'create' permission on
Purchase Invoice to perform this action." even though the role-based
DocPerm grants create.

Fixes (Property Setter, ignore_user_permissions=1):
  1. `<DocType>.letter_head` — Letter Heads are deliberately scoped to
     a Company in this site (custom field on Letter Head), but the
     default LH `Company Letterhead - Grey` has company=NULL by design
     (it's the "global / fall-back" letter head). The existing
     `tenant_scope.letter_head_has_perm` already handles NULL = global,
     but Frappe's UP filter intercepts BEFORE that hook runs.
  2. `<DocType>.represents_company` — only used for inter-company
     transactions; when blank (the common case), it shouldn't gate
     creation of a normal Purchase Invoice / Sales Invoice / etc.

Idempotent — re-running on every migrate is safe.
"""
import frappe


_LETTER_HEAD_DOCTYPES = [
    "Purchase Invoice", "Sales Invoice",
    "Sales Order", "Purchase Order",
    "Quotation", "Supplier Quotation",
    "Delivery Note", "Purchase Receipt",
    "Stock Entry", "Material Request",
    "Payment Entry", "Journal Entry",
    "Salary Slip",
]


def ensure_strict_up_exemptions():
    """Create Property Setters that mark specific Link fields with
    ignore_user_permissions=1. Idempotent."""
    # 1. letter_head fields on commonly-printed transaction doctypes
    for dt in _LETTER_HEAD_DOCTYPES:
        _set_ignore_up(dt, "letter_head")

    # 2. represents_company on every doctype that has the field
    represents_doctypes = frappe.db.sql(
        """
        SELECT DISTINCT parent FROM `tabDocField`
        WHERE fieldname = 'represents_company'
          AND fieldtype = 'Link'
          AND options   = 'Company'
        """,
        pluck="parent",
    )
    for dt in represents_doctypes:
        _set_ignore_up(dt, "represents_company")

    frappe.db.commit()


def _set_ignore_up(doctype: str, fieldname: str):
    """Upsert a single Property Setter setting ignore_user_permissions=1
    on the given (doctype, fieldname). Skip if the doctype or field
    doesn't exist on this site (so we don't fail on a slim install)."""
    if not frappe.db.exists("DocType", doctype):
        return
    df = frappe.get_meta(doctype).get_field(fieldname)
    if not df:
        return

    existing = frappe.db.exists("Property Setter", {
        "doc_type":   doctype,
        "field_name": fieldname,
        "property":   "ignore_user_permissions",
    })
    if existing:
        # Re-affirm the value in case someone toggled it off in the UI.
        frappe.db.set_value(
            "Property Setter", existing, "value", "1", update_modified=False,
        )
        return

    try:
        ps = frappe.new_doc("Property Setter")
        ps.doctype_or_field = "DocField"
        ps.doc_type         = doctype
        ps.field_name       = fieldname
        ps.property         = "ignore_user_permissions"
        ps.property_type    = "Check"
        ps.value            = "1"
        ps.insert(ignore_permissions=True)
        frappe.logger("skyengpro").info(
            "ensure_strict_up_exemptions: created PS for %s.%s",
            doctype, fieldname,
        )
    except Exception:
        frappe.logger("skyengpro").exception(
            "ensure_strict_up_exemptions: failed for %s.%s",
            doctype, fieldname,
        )
