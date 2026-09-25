# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Paraguay - Presupuesto vs Real (MIS Budget)",
    "summary": "Instancia de Estado de Resultados con orçamento por KPI (MIS Budget)",
    "version": "18.0.1.0.0",
    "category": "Accounting/Localizations/Reporting",
    "author": "KMEE, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-paraguay",
    "license": "AGPL-3",
    "depends": [
        "l10n_py_mis_report",
        "mis_builder_budget",
    ],
    "data": [
        "data/mis_report_instance_presupuesto_vs_real.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
