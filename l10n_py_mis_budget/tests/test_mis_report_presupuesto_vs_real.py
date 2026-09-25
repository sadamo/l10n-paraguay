# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re

from odoo.modules.module import get_module_path
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# AC6: no expression may match a raw single-digit group-root prefix
# without a "." separator (e.g. "[5%]", "[8%]"), which would accidentally
# match every group starting with that digit (5*, 50*, 8*, ...).
_RAW_SINGLE_DIGIT_PREFIX_RE = re.compile(r"\[\D*\d%\]")

# Prefixes used by each child/residual KPI of the 3 rewritten parent KPIs,
# parsed directly from their expression at test time (see
# test_ac7_parent_children_coverage) instead of hardcoded here, so the test
# breaks if the data file and this test drift apart.
_PARENT_GROUPS = {
    "er_py_ingresos_operativos": (
        "4",
        [
            "er_py_ventas_mercaderias",
            "er_py_ventas_agricolas",
            "er_py_exportaciones",
            "er_py_ventas_servicios",
            "er_py_ventas_regimenes_especiales",
            "er_py_descuentos_devoluciones",
        ],
    ),
    "er_py_gastos_comerciales": (
        "10",
        ["er_py_gc_personal", "er_py_gc_comisiones", "er_py_gc_otros"],
    ),
    "er_py_gastos_administrativos": (
        "11",
        ["er_py_ga_personal", "er_py_ga_servicios", "er_py_ga_otros"],
    ),
}

_EXPR_PREFIX_RE = re.compile(r"\[([\d.]+)%\]")


@tagged("post_install", "-at_install")
class TestMisReportPresupuestoVsReal(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create(
            {
                "name": "PY Presupuesto Test Co",
                "country_id": cls.env.ref("base.py").id,
            }
        )
        cls.env["account.chart.template"].try_loading(
            template_code="py", company=cls.company
        )

        cls.report = cls.env.ref("l10n_py_mis_report.mis_report_estado_resultados_py")
        cls.instance = cls.env.ref(
            "l10n_py_mis_budget.mis_instance_presupuesto_vs_real_py"
        )
        # Fix the instance on our test company and a fixed pivot date, so the
        # relative yearly periods resolve to a known, stable date range
        # (Requisito/OBJ-12: avoid flakiness near year-end).
        cls.instance.write({"company_id": cls.company.id})
        cls.pivot_date = "2026-06-15"
        cls.period_from = "2026-01-01"
        cls.period_to = "2026-12-31"

        cls.kpi_ventas = cls.env.ref("l10n_py_mis_report.er_py_ventas_mercaderias")
        cls.kpi_costo = cls.env.ref("l10n_py_mis_report.er_py_costo_ventas")
        cls.kpi_ga_servicios = cls.env.ref("l10n_py_mis_report.er_py_ga_servicios")

        cls.budget = cls.env["mis.budget"].create(
            {
                "name": "Presupuesto 2026",
                "report_id": cls.report.id,
                "date_from": cls.period_from,
                "date_to": cls.period_to,
                "company_id": cls.company.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "kpi_expression_id": cls.kpi_ventas.expression_ids[0].id,
                            "date_from": cls.period_from,
                            "date_to": cls.period_to,
                            "amount": 1200000,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            # Requisito 5: convención de signo negativa para
                            # KPIs de costo/gasto (grupos 5/10/11).
                            "kpi_expression_id": cls.kpi_costo.expression_ids[0].id,
                            "date_from": cls.period_from,
                            "date_to": cls.period_to,
                            "amount": -350000,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "kpi_expression_id": cls.kpi_ga_servicios.expression_ids[
                                0
                            ].id,
                            "date_from": cls.period_from,
                            "date_to": cls.period_to,
                            "amount": -120000,
                        },
                    ),
                ],
            }
        )
        cls.instance.period_ids.filtered(
            lambda p: p.source == "mis_budget"
        ).source_mis_budget_id = cls.budget.id

        cls._post_actuals()

        # The assignment above only queues a dirty write in cache; without an
        # explicit flush, env.clear() below discards it before it ever
        # reaches the DB, leaving source_mis_budget_id empty for the rest of
        # the tests and making the "Presupuesto" column resolve to
        # AccountingNone (QA-01: real bug, not just a fixture issue).
        cls.env.flush_all()
        cls.env.clear()

    @classmethod
    def _account(cls, code):
        # "code" is company_dependent (code_store per company root, Odoo 18);
        # it only resolves through the ORM when read/searched with the
        # target company active, otherwise it evaluates to False and any
        # domain on "code" silently matches nothing (QA-01).
        account = (
            cls.env["account.account"]
            .with_company(cls.company)
            .search(
                [("company_ids", "in", cls.company.id), ("code", "=", code)], limit=1
            )
        )
        if not account:
            raise AssertionError(
                f"Nenhuma conta com código {code!r} encontrada para a company "
                f"de teste {cls.company.display_name!r} (chart 'py' pode não "
                "ter carregado essa conta)."
            )
        return account

    @classmethod
    def _post_actuals(cls):
        journal = cls.env["account.journal"].search(
            [("company_id", "=", cls.company.id), ("type", "=", "general")], limit=1
        )
        bank_account = cls._account("1.01.01.04")
        ventas_account = cls._account("4.01.01")
        costo_account = cls._account("5.01.01")
        # Real chart code for "ALQUILERES" is "11.050" (3-digit residual
        # scheme for this subgroup), matched by the KPI's "balp[11.05%]"
        # prefix expression.
        ga_servicios_account = cls._account("11.050")

        # Real ventas_mercaderias = 1.000.000 (income: crédito > débito, y el
        # KPI usa -balp[] para mostrarlo positivo).
        cls.env["account.move"].create(
            {
                "journal_id": journal.id,
                "company_id": cls.company.id,
                "date": "2026-03-15",
                "line_ids": [
                    (
                        0,
                        0,
                        {"account_id": bank_account.id, "debit": 1000000, "credit": 0},
                    ),
                    (
                        0,
                        0,
                        {
                            "account_id": ventas_account.id,
                            "debit": 0,
                            "credit": 1000000,
                        },
                    ),
                ],
            }
        ).action_post()

        # Real costo_ventas = -300.000 (expense: débito > crédito).
        cls.env["account.move"].create(
            {
                "journal_id": journal.id,
                "company_id": cls.company.id,
                "date": "2026-04-10",
                "line_ids": [
                    (
                        0,
                        0,
                        {"account_id": costo_account.id, "debit": 300000, "credit": 0},
                    ),
                    (
                        0,
                        0,
                        {"account_id": bank_account.id, "debit": 0, "credit": 300000},
                    ),
                ],
            }
        ).action_post()

        # Real ga_servicios = -100.000 (expense: débito > crédito).
        cls.env["account.move"].create(
            {
                "journal_id": journal.id,
                "company_id": cls.company.id,
                "date": "2026-05-20",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": ga_servicios_account.id,
                            "debit": 100000,
                            "credit": 0,
                        },
                    ),
                    (
                        0,
                        0,
                        {"account_id": bank_account.id, "debit": 0, "credit": 100000},
                    ),
                ],
            }
        ).action_post()

    def _matrix(self):
        return self.instance.with_context(
            mis_pivot_date=self.pivot_date
        )._compute_matrix()

    def _row_values(self, matrix, kpi):
        for row in matrix.iter_rows():
            if row.kpi == kpi and row.account_id is None:
                return {
                    subcol.col.label: cell.val
                    for subcol, cell in zip(
                        matrix.iter_subcols(), row.iter_cells(), strict=False
                    )
                }
        self.fail(f"No row found for kpi {kpi.name}")

    def test_ac2_orcado_real_variacoes(self):
        """AC2: orçado, realizado, cmpcol e sumcol calculados corretamente."""
        matrix = self._matrix()

        expected = {
            self.kpi_ventas: {
                "Presupuesto": 1200000,
                "Real": 1000000,
                "gs": 200000,
                "pct": (1200000 - 1000000) / abs(1000000),
            },
            self.kpi_costo: {
                "Presupuesto": -350000,
                "Real": -300000,
                "gs": -50000,
                "pct": (-350000 - -300000) / abs(-300000),
            },
            self.kpi_ga_servicios: {
                "Presupuesto": -120000,
                "Real": -100000,
                "gs": -20000,
                "pct": (-120000 - -100000) / abs(-100000),
            },
        }
        for kpi, expected_vals in expected.items():
            values = self._row_values(matrix, kpi)
            self.assertAlmostEqual(
                values["Presupuesto"], expected_vals["Presupuesto"], places=2
            )
            self.assertAlmostEqual(values["Real"], expected_vals["Real"], places=2)
            self.assertAlmostEqual(
                values["Variación (Gs.)"], expected_vals["gs"], places=2
            )
            self.assertAlmostEqual(
                values["Variación %"], expected_vals["pct"], places=4
            )
            # cmpcol e sumcol devem apontar no mesmo sentido (orçado - real)
            # para KPIs de despesa (Requisito 3/5).
            self.assertEqual(values["Variación (Gs.)"] < 0, values["Variación %"] < 0)

    def test_ac3_no_account_detail_rows(self):
        """AC3: sem no_auto_expand_accounts=True nenhuma linha de detalhe por
        conta deve existir nesta instância, nem na coluna orçado nem na real
        (evita grid incompleto/inconsistente entre colunas)."""
        matrix = self._matrix()
        detail_rows = [row for row in matrix.iter_rows() if row.account_id]
        self.assertFalse(
            detail_rows,
            "no_auto_expand_accounts=True não deveria gerar detalhe por conta",
        )

    def test_ac6_no_raw_single_digit_prefix(self):
        """AC6: nenhuma expressão do arquivo tocado usa prefixo cru de grupo-
        raiz de 1 dígito sem separador '.'."""
        module_path = get_module_path("l10n_py_mis_report")
        xml_path = f"{module_path}/data/mis_report_estado_resultados.xml"
        with open(xml_path, encoding="utf-8") as f:
            content = f.read()
        matches = _RAW_SINGLE_DIGIT_PREFIX_RE.findall(content)
        self.assertFalse(
            matches,
            f"Prefixo cru de grupo-raiz de 1 dígito encontrado: {matches}",
        )

    def test_ac7_parent_children_coverage(self):
        """AC7: para cada um dos 3 KPIs-pai reescritos, os filhos (+residual)
        cobrem exatamente as contas reais do grupo, sem lacunas e sem
        sobreposição."""
        # See _account(): "code" is company_dependent and only resolves with
        # the target company active (QA-01).
        Account = self.env["account.account"].with_company(self.company)
        for parent_name, (group_prefix, child_names) in _PARENT_GROUPS.items():
            group_accounts = Account.search(
                [
                    ("company_ids", "in", self.company.id),
                    ("code", "=like", f"{group_prefix}.%"),
                ]
            )
            self.assertTrue(
                group_accounts, f"Nenhuma conta encontrada para o grupo {group_prefix}"
            )

            children_accounts = []
            for child_name in child_names:
                kpi = self.env.ref(f"l10n_py_mis_report.{child_name}")
                prefixes = _EXPR_PREFIX_RE.findall(kpi.expression)
                self.assertTrue(
                    prefixes, f"Nenhum prefixo balp[] encontrado em {child_name}"
                )
                matched = Account.browse()
                for prefix in prefixes:
                    matched |= group_accounts.filtered(
                        lambda a, p=prefix: a.code.startswith(p)
                    )
                children_accounts.append(matched)

            union = Account.browse()
            for matched in children_accounts:
                union |= matched
            self.assertEqual(
                set(union.ids),
                set(group_accounts.ids),
                f"Cobertura incompleta do grupo {group_prefix} ({parent_name})",
            )

            for i, matched_i in enumerate(children_accounts):
                for matched_j in children_accounts[i + 1 :]:
                    overlap = matched_i & matched_j
                    self.assertFalse(
                        overlap,
                        f"Sobreposição de contas entre filhos de {parent_name}: "
                        f"{overlap.mapped('code')}",
                    )
