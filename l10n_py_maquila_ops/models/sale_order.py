# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    l10n_py_maquila_program_id = fields.Many2one(
        "l10n_py.maquila.program",
        string="Maquila Program",
    )
    l10n_py_is_maquila_export = fields.Boolean(
        compute="_compute_is_maquila_export",
    )

    @api.depends("l10n_py_maquila_program_id")
    def _compute_is_maquila_export(self):
        for order in self:
            order.l10n_py_is_maquila_export = bool(order.l10n_py_maquila_program_id)

    @api.onchange("l10n_py_maquila_program_id")
    def _onchange_maquila_program(self):
        if not self.l10n_py_maquila_program_id:
            return
        partner = self.partner_id
        company = self.company_id or self.env.company
        is_foreign = (
            bool(partner.country_id) and partner.country_id != company.country_id
        )
        if (
            is_foreign
            and self.fiscal_position_id
            and self.fiscal_position_id.auto_apply
        ):
            # A fiscal position was already auto-detected for the foreign
            # partner (e.g. the chart's "Ventas - Exportación" position,
            # which maps IVA to the exonerated tax). Keep it instead of
            # overwriting it with the maquila position below, which has no
            # tax mapping of its own and would leave the VAT untouched.
            return
        fp = self._get_maquila_export_fiscal_position(company)
        if fp:
            self.fiscal_position_id = fp

    def _get_maquila_export_fiscal_position(self, company):
        """Resolve (or create) the maquila export fiscal position for
        ``company`` and make sure it maps the company's taxed sale taxes to
        the exonerated one.

        Fiscal positions are company-specific records, so the position
        cannot be a single hardcoded xmlid shared by every company (that
        raises "Incompatible companies" for orders of any other company).
        Instead, look it up (or create it) per company and build its tax
        mapping from the company's own taxes.
        """
        Position = self.env["account.fiscal.position"].sudo()
        name = _("Maquila - Exportacion Exenta")
        fp = Position.search(
            [("name", "=", name), ("company_id", "=", company.id)], limit=1
        )
        if not fp:
            template = self.env.ref(
                "l10n_py_maquila_ops.fiscal_position_maquila_export",
                raise_if_not_found=False,
            )
            if template and template.company_id.id in (False, company.id):
                fp = template
                if not fp.company_id:
                    fp.company_id = company.id
            else:
                fp = Position.create(
                    {
                        "name": name,
                        "company_id": company.id,
                        "auto_apply": False,
                        "note": template.note if template else False,
                    }
                )
        self._ensure_maquila_exoneration_mapping(fp, company)
        return fp

    def _ensure_maquila_exoneration_mapping(self, fiscal_position, company):
        """Populate ``fiscal_position`` with a mapping from the company's
        taxed sale taxes (Gravado IVA) to its exonerated one, so orders
        under this fiscal position end up with exonerated VAT instead of
        losing the tax mapping entirely."""
        if fiscal_position.tax_ids:
            return
        Tax = self.env["account.tax"].sudo()
        if "l10n_py_iva_affectation" not in Tax._fields:
            # l10n_py_account (which adds the IVA affectation field used to
            # tell taxed and exonerated taxes apart) is not installed.
            return
        exonerado = Tax.search(
            [
                ("company_id", "=", company.id),
                ("type_tax_use", "=", "sale"),
                ("l10n_py_iva_affectation", "=", "2"),
            ],
            limit=1,
        )
        if not exonerado:
            return
        gravadas = Tax.search(
            [
                ("company_id", "=", company.id),
                ("type_tax_use", "=", "sale"),
                ("l10n_py_iva_affectation", "=", "1"),
            ]
        )
        FiscalPositionTax = self.env["account.fiscal.position.tax"].sudo()
        for tax in gravadas:
            FiscalPositionTax.create(
                {
                    "position_id": fiscal_position.id,
                    "tax_src_id": tax.id,
                    "tax_dest_id": exonerado.id,
                }
            )

    def action_confirm(self):
        py_country = self.env.ref("base.py", raise_if_not_found=False)
        for order in self:
            program = order.l10n_py_maquila_program_id
            # Art. 18 caps domestic sales only for the "pura" modality.
            if not (program and py_country and program.maquila_type == "pura"):
                continue
            if order.partner_id.country_id == py_country:
                order._check_maquila_domestic_cap(program)
        return super().action_confirm()

    def _check_maquila_domestic_cap(self, program):
        """Ley 7547/2025 Art. 18: pure maquila may sell to the domestic market
        up to a percentage (10% by default) of the prior-year exported value.
        Amounts are converted to the company currency before comparing."""
        self.ensure_one()
        company = self.company_id
        company_currency = company.currency_id
        today = fields.Date.context_today(self)
        pct = program.internal_sale_pct or 10.0
        year = today.year
        prior_exports = self.env["l10n_py.maquila.export.line"].search(
            [
                ("export_id.program_id", "=", program.id),
                ("export_id.date_export", ">=", f"{year - 1}-01-01"),
                ("export_id.date_export", "<=", f"{year - 1}-12-31"),
            ]
        )
        export_base = sum(
            line.currency_id._convert(
                line.fob_value,
                company_currency,
                company,
                line.export_id.date_export or today,
            )
            for line in prior_exports
        )
        # New maquiladora with no prior-year exports: nothing to cap against.
        if not export_base:
            return
        cap = export_base * pct / 100.0
        py_country = self.env.ref("base.py")
        other_domestic = self.search(
            [
                ("l10n_py_maquila_program_id", "=", program.id),
                ("state", "=", "sale"),
                ("id", "!=", self.id),
            ]
        ).filtered(lambda o: o.partner_id.country_id == py_country)
        already = sum(
            o.currency_id._convert(o.amount_untaxed, company_currency, company, today)
            for o in other_domestic
        )
        current = self.currency_id._convert(
            self.amount_untaxed, company_currency, company, today
        )
        if already + current > cap:
            raise UserError(
                _(
                    "Domestic sales for program %(program)s would exceed the "
                    "%(pct)s%% cap of prior-year exports (cap: %(cap).2f %(cur)s).",
                    program=program.code,
                    pct=pct,
                    cap=cap,
                    cur=company_currency.name,
                )
            )
