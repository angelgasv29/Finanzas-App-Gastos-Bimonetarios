"""Acta de cierre de ejercicio (``buildClosureActHTML``, 6930-7012).

La versión de referencia devuelve una cadena HTML que se inyecta en ``#printArea`` y se manda
a imprimir. Esta implementación devuelve **la misma cadena**: así el verificación puede comparar
carácter a carácter lo que la versión de referencia escribió y lo que escribe esta implementación, sin
navegador.

Los importes del acta usan ``Number(x).toFixed(2)`` (sin separador de miles) y
solo los totales de Bs usan ``formatBs``; el año fiscal se escapa con
``escapeHtml(String(x ?? ''))``.
"""

from __future__ import annotations

from typing import Any

from ..core.js_locale import locale_datetime, parse_date_ms
from ..core.money import format_bs, format_rate, js_number_or_zero, js_to_fixed
from ..core.text import escape_html, js_to_string

__all__ = ["build_closure_act_html"]

# Una compra del top de gastos (índice).
_TOP_EXPENSE_ROW = (
    "\n    <tr>"
    '\n      <td class="num">{position}</td>'
    "\n      <td>{name}</td>"
    "\n      <td>{date}</td>"
    '\n      <td class="num">Bs. {amount_bs}</td>'
    '\n      <td class="num">${amount_usd}</td>'
    "\n    </tr>"
)

# Una fila del top de categorías.
_TOP_CATEGORY_ROW = (
    "\n    <tr>"
    '\n      <td class="num">{position}</td>'
    "\n      <td>{name}</td>"
    '\n      <td class="num">{count}</td>'
    '\n      <td class="num">${total}</td>'
    "\n    </tr>"
)


def _safe(value: Any) -> str:
    """``escapeHtml(String(value ?? ''))``."""
    return escape_html(js_to_string(value, ""))


def _fixed2(value: Any) -> str:
    """``Number(value || 0).toFixed(2)``."""
    return js_to_fixed(js_number_or_zero(value), 2)


def _top_categories_html(snapshot: dict[str, Any]) -> str:
    rows = []
    for index, category in enumerate(snapshot.get("topCategories") or []):
        rows.append(
            _TOP_CATEGORY_ROW.format(
                position=index + 1,
                name=_safe(category.get("name")),
                count=js_to_string(category.get("count"), ""),
                total=_fixed2(category.get("total")),
            )
        )
    return "".join(rows)


def _top_expenses_html(snapshot: dict[str, Any]) -> str:
    rows = []
    for index, expense in enumerate(snapshot.get("topExpenses") or []):
        rows.append(
            _TOP_EXPENSE_ROW.format(
                position=index + 1,
                name=_safe(expense.get("productName")),
                date=_safe(expense.get("date")),
                amount_bs=_fixed2(expense.get("amountBs")),
                amount_usd=_fixed2(expense.get("amountUsd")),
            )
        )
    return "".join(rows)


def build_closure_act_html(
    snapshot: dict[str, Any], *, now_ms: float, locale: str | None = None
) -> str:
    """HTML del acta de cierre tal como lo genera ``buildClosureActHTML``.

    ``snapshot`` es el objeto que guarda el asistente de cierre: ``year``,
    ``workspace``, ``closedAt``, ``txCount``, totales, tasas, los *top* y las
    ``notes``. ``now_ms`` es el instante de emisión (``new Date()``).
    """
    workspace_label = (
        "Personal" if snapshot.get("workspace") == "personal" else "Profesional"
    )
    closed_at = parse_date_ms(snapshot.get("closedAt"))
    closed_date = locale_datetime(closed_at, locale)

    top_cats_html = _top_categories_html(snapshot)
    top_exp_html = _top_expenses_html(snapshot)

    categories_block = (
        '<table>\n'
        '        <thead><tr><th class="num">#</th><th>Categoría</th>'
        '<th class="num">Compras</th><th class="num">Total USD</th></tr></thead>\n'
        f"        <tbody>{top_cats_html}</tbody>\n"
        "      </table>"
        if top_cats_html
        else "<p><i>Sin categorías registradas.</i></p>"
    )
    expenses_block = (
        '<table>\n'
        '        <thead><tr><th class="num">#</th><th>Producto</th><th>Fecha</th>'
        '<th class="num">Monto Bs</th><th class="num">Monto USD</th></tr></thead>\n'
        f"        <tbody>{top_exp_html}</tbody>\n"
        "      </table>"
        if top_exp_html
        else "<p><i>Sin gastos registrados.</i></p>"
    )

    lines = [
        "",
        '    <div class="acta-doc">',
        f"      <h1>Acta de Cierre de Ejercicio Fiscal {_safe(snapshot.get('year'))}</h1>",
        '      <div class="acta-meta">',
        f"        <b>Entorno:</b> {_safe(workspace_label)} &nbsp;&middot;&nbsp;",
        f"        <b>Año fiscal:</b> {_safe(snapshot.get('year'))} &nbsp;&middot;&nbsp;",
        f"        <b>Registros:</b> {_safe(snapshot.get('txCount'))} &nbsp;&middot;&nbsp;",
        f"        <b>Fecha de cierre:</b> {_safe(closed_date)}<br>",
        f"        <b>Referencia interna:</b> {_safe(snapshot.get('id'))}",
        "      </div>",
        "",
        "      <h2>1. Resumen financiero global</h2>",
        '      <div class="acta-kpi-grid">',
        "        <div class=\"acta-kpi\"><span class=\"lbl\">Total Bs</span>"
        f"<span class=\"val\">{format_bs(snapshot.get('totalBs'))}</span></div>",
        "        <div class=\"acta-kpi\"><span class=\"lbl\">Total USD</span>"
        f"<span class=\"val\">${_fixed2(snapshot.get('totalUsd'))}</span></div>",
        "        <div class=\"acta-kpi\"><span class=\"lbl\">Transacciones</span>"
        f"<span class=\"val\">{_safe(snapshot.get('txCount'))}</span></div>",
        "        <div class=\"acta-kpi\"><span class=\"lbl\">Base imponible</span>"
        f"<span class=\"val\">{format_bs(snapshot.get('baseTotal'))}</span></div>",
        "        <div class=\"acta-kpi\"><span class=\"lbl\">IVA acumulado</span>"
        f"<span class=\"val\">{format_bs(snapshot.get('ivaTotal'))}</span></div>",
        "        <div class=\"acta-kpi\"><span class=\"lbl\">Inflación micro prom.</span>"
        f"<span class=\"val\">{_fixed2(snapshot.get('inflationAvg'))}%</span></div>",
        "      </div>",
        "",
        "      <h2>2. Indicadores macro / tipo de cambio</h2>",
        "      <table>",
        "        <thead><tr>",
        '          <th>Concepto</th><th>Fecha</th><th class="num">Valor Bs / USD</th>',
        "        </tr></thead>",
        "        <tbody>",
        "          <tr><td>Tasa de apertura del ejercicio</td>"
        f"<td>{_safe(snapshot.get('rateStartDate') or '—')}</td>"
        f"<td class=\"num\">{format_rate(snapshot.get('rateStart')) if snapshot.get('rateStart') else '—'}</td></tr>",
        "          <tr><td>Tasa de cierre del ejercicio</td>"
        f"<td>{_safe(snapshot.get('rateEndDate') or '—')}</td>"
        f"<td class=\"num\">{format_rate(snapshot.get('rateEnd')) if snapshot.get('rateEnd') else '—'}</td></tr>",
        "          <tr><td><b>Devaluación acumulada</b></td><td>—</td>"
        f"<td class=\"num\"><b>{_fixed2(snapshot.get('rateDelta'))}%</b></td></tr>",
        "        </tbody>",
        "      </table>",
        "",
        "      <h2>3. Top categorías por inversión</h2>",
        f"      {categories_block}",
        "",
        "      <h2>4. Top 5 gastos individuales</h2>",
        f"      {expenses_block}",
        "",
        "      <h2>5. Observaciones del auditor</h2>",
        '      <p style="min-height:60px; border:1px solid #D1D5DB; border-radius:4px; '
        'padding:10px; font-size:10.5pt;">',
        "        "
        + (
            _safe(snapshot.get("notes"))
            if snapshot.get("notes")
            else "<i>Sin observaciones registradas.</i>"
        ),
        "      </p>",
        "",
        '      <div class="acta-signature">',
        '        <div class="line">Firma del responsable contable</div>',
        '        <div class="line">Firma del revisor / auditor externo</div>',
        "      </div>",
        "",
        '      <div class="acta-footer">',
        "        Documento generado automáticamente por Gastos Bimonetarios &middot; "
        "Auditoría local, sin transmisión de datos a terceros.<br>",
        f"        Emitido: {_safe(locale_datetime(now_ms, locale))}",
        "      </div>",
        "    </div>",
    ]
    return "\n".join(lines)
