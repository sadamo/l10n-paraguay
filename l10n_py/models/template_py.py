# Part of the Paraguayan localization. See LICENSE file for full copyright
# and licensing details.
from odoo import _, models

from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template("py")
    def _get_py_template_data(self):
        return {
            "name": _("Plan de Cuentas - Paraguay (Resolución General N° 49/14)"),
            "code_digits": "6",
            "property_account_receivable_id": "account_py_301",
            "property_account_payable_id": "account_py_2001",
            # TEMPORARIO/MIG 19.0: property_account_expense_categ_id e
            # property_account_income_categ_id NUNCA foram aplicados por
            # account.chart.template - _get_property_accounts() so reconhece
            # property_account_receivable_id/payable_id/property_stock_journal
            # por padrao (ver account/models/chart_template.py
            # _post_load_data/_get_property_accounts no core). Esses dois
            # ficavam sem efeito (nao e regressao do 19.0: mesmo "dead code"
            # existe em l10n_co, unico outro modulo core que declara essas
            # chaves). O default de conta de receita/despesa por categoria e
            # derivado de company.income_account_id/expense_account_id (ver
            # _get_py_res_company abaixo) - mantido aqui so por
            # compatibilidade/documentacao, sem efeito pratico.
            "property_account_expense_categ_id": "account_py_50101_expense",
            "property_account_income_categ_id": "account_py_40101_income",
        }

    @template("py", "res.company")
    def _get_py_res_company(self):
        return {
            self.env.company.id: {
                "account_fiscal_country_id": "base.py",
                "bank_account_code_prefix": "1.01.01.04",
                "cash_account_code_prefix": "1.01.01.02",
                "transfer_account_code_prefix": "1.01.01.03",
                "account_default_pos_receivable_account_id": "account_py_301",
                "income_currency_exchange_account_id": "account_py_805_income",
                "expense_currency_exchange_account_id": "account_py_1304_expense",
                "default_cash_difference_income_account_id": "account_py_802_income",
                "default_cash_difference_expense_account_id": (
                    "account_py_1116_expense"
                ),
                "account_journal_suspense_account_id": "account_py_103",
                "account_journal_payment_debit_account_id": "account_py_301",
                "account_journal_payment_credit_account_id": "account_py_2001",
                "account_sale_tax_id": "py_tax_vat_10_ventas",
                "account_purchase_tax_id": "py_tax_vat_10_compras",
                # FIX (nao especifico do 19.0): sem estes dois campos,
                # account.chart.template._post_load_data nunca seta o
                # ir.default de product.category.property_account_income/
                # expense_categ_id (ver core: esse default vem de
                # company.income_account_id/expense_account_id, nao das
                # chaves property_account_*_categ_id acima). Toda empresa
                # nova com o chart py ficava sem conta de receita/despesa
                # default por categoria - so nao aparecia em base.main_company
                # porque essa ja herdava income_account_id/expense_account_id
                # do chart generico instalado antes. Padrao confirmado em
                # l10n_ar/l10n_cl/l10n_mx e na maioria dos outros core charts.
                "income_account_id": "account_py_40101_income",
                "expense_account_id": "account_py_50101_expense",
            },
        }
