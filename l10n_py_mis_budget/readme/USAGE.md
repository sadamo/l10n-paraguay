1. Instale el módulo (depende de `l10n_py_mis_report` y `mis_builder_budget`).
2. Cree un `mis.budget` para el ejercicio, con report_id apuntando a
   `Estado de Resultados (Paraguay - RG 49/14)`, y agregue un `mis.budget.item` por
   cada KPI orçable (`budgetable=True`) que desee presupuestar.
3. Asocie manualmente ese `mis.budget` al período **Presupuesto** de la instancia
   *Presupuesto vs Real* (*Contabilidad -> Configuración -> MIS Builder -> Instancias de
   Informes*). El módulo no carga ningún `mis.budget` de ejemplo con valores ficticios: es
   dato de negocio del cliente y debe asociarse después de la instalación.
4. Convención de signo del orçado (obligatoria para KPIs de los grupos 5 (Costo de
   Ventas), 10 (Gastos Comerciales) y 11 (Gastos Administrativos)): como el realizado de
   esos grupos usa la convención `-balp[...]` (egresos en negativo), los valores orçados
   lanzados en `mis.budget.item` para las KPIs de esos grupos deben ser también
   **negativos**, para que la variación (orçado - real) no salga invertida.
5. Sentido de las dos columnas de variación:
   - **Variación %** (`cmpcol`) = `(orçado - real) / abs(real)` — porcentaje sobre el
     realizado, no sobre el orçado (limitación de la API nativa de `mis_builder`: el
     denominador siempre es el valor del período "versus"/`from`).
   - **Variación (Gs.)** (`sumcol`) = `orçado - real`, en la misma moneda del informe.
6. Detalle por cuenta: esta instancia usa `no_auto_expand_accounts=True`, por lo que
   **no** muestra detalle por cuenta en ninguna columna (ni orçado ni real), a diferencia
   de las instancias de Balance/Flujo. Cuentas como Contador (11.04) y Energía (11.06)
   aparecen agregadas en la línea `ga_otros`. El detalle por cuenta sigue disponible en
   las instancias de realizado puro (Balance General, Flujo de Efectivo).
7. Orçamento por conta (`mis.budget.by.account`) no forma parte de este módulo; es una
   extensión posible a pedir explícitamente en el futuro.
