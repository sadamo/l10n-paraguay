Agrega, sobre el Estado de Resultados (RG 49/14) de `l10n_py_mis_report`, una instancia de
informe **"Presupuesto vs Real"** por KPI, usando `mis_builder_budget`:

- columna **Presupuesto** (`source: mis_budget`);
- columna **Real** (`source: actuals`);
- columna **Variación %** (`source: cmpcol`, variación nativa porcentual);
- columna **Variación (Gs.)** (`source: sumcol`, variación absoluta en Guaraníes,
  presupuesto - real).

El orçamento se carga por KPI (`mis.budget` / `mis.budget.item`), no por cuenta
(`mis.budget.by.account` queda fuera del alcance de este módulo).
