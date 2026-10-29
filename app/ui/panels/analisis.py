"""Panel 5 · Análisis: las cinco sub-pestañas y los cinco extras del panel E.

Todo el cálculo vive en :mod:`app.analytics`; este módulo solo elige el rango
temporal, recoge los controles y pinta los resultados (tablas y gráficos). Los
valores provienen de las vistas ya verificadas contra la versión de referencia, así que la
interfaz no reformatea nada: muestra lo que devuelve el motor.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from nicegui import ui

from ...analytics import categories as analytics_categories
from ...analytics import common as analytics_common
from ...analytics import extras as analytics_extras
from ...analytics import frequency as analytics_frequency
from ...analytics import inflation as analytics_inflation
from ...analytics import pivot as analytics_pivot
from ...analytics import projection as analytics_projection
from ...analytics import variants as analytics_variants
from ...core.periods import (
    TemporalState,
    date_to_iso,
    format_temporal_label,
    get_temporal_range,
    shift_temporal,
)
from ...core.text import escape_html
from .. import components as c
from ..state import AppState

__all__ = ["render"]

GROUP_LABELS = {
    "unit": "Unidad",
    "brand": "Marca",
    "subcategory": "Subcategoría",
    "provider": "Comercio",
    "paymentMethod": "Forma de pago",
    "originPlatform": "Plataforma",
    "category": "Categoría",
    "product": "Producto",
}
PIVOT_LABELS = {
    "provider": "Comercio",
    "brand": "Marca",
    "payment": "Forma de pago",
    "originPlatform": "Plataforma",
    "subcategory": "Subcategoría",
}
ORDER_LABELS = {"total": "Gasto total", "count": "Nº de compras", "interval": "Intervalo"}


def render(state: AppState) -> None:
    temporal: dict[str, Any] = {
        "mode": "month",
        "ref": datetime.now(),
        "start": None,
        "end": None,
    }

    @ui.refreshable
    def content() -> None:
        _build(state, temporal, content.refresh)

    content()
    state.subscribe(content.refresh)


def _temporal_state(temporal: dict[str, Any]) -> TemporalState:
    return TemporalState(
        mode=temporal["mode"],
        ref_date=temporal["ref"],
        custom_start=temporal["start"],
        custom_end=temporal["end"],
    )


def _build(state: AppState, temporal: dict[str, Any], refresh: Callable[[], None]) -> None:
    ts = _temporal_state(temporal)
    start, end = get_temporal_range(ts)
    start_iso, end_iso = date_to_iso(start), date_to_iso(end)
    txs = analytics_common.filtered_by_range(state.transactions(), start_iso, end_iso)

    with ui.column().classes("w-full gap-4 p-4"):
        with c.card():
            c.section_title("Período de análisis")
            with ui.row().classes("grid grid-cols-2 md:grid-cols-5 gap-3 w-full items-end"):
                mode = ui.select(
                    MODE_OPTIONS,
                    value=temporal["mode"],
                    label="Tipo de período",
                ).classes("w-full")
                if temporal["mode"] == "custom":
                    custom_start = ui.input(
                        "Desde",
                        value=date_to_iso(temporal["start"] or start),
                    ).props("type=date").classes("w-full")
                    custom_end = ui.input(
                        "Hasta",
                        value=date_to_iso(temporal["end"] or end),
                    ).props("type=date").classes("w-full")
                else:
                    custom_start = custom_end = None

                def apply_mode() -> None:
                    temporal["mode"] = mode.value
                    refresh()

                mode.on_value_change(lambda _e=None: apply_mode())

                def apply_custom() -> None:
                    if custom_start and custom_start.value:
                        temporal["start"] = datetime.fromisoformat(custom_start.value)
                    if custom_end and custom_end.value:
                        temporal["end"] = datetime.fromisoformat(custom_end.value)
                    refresh()

                for widget in (custom_start, custom_end):
                    if widget is not None:
                        widget.on_value_change(lambda _e=None: apply_custom())

                def shift(direction: int) -> Callable[[], None]:
                    def action() -> None:
                        temporal["ref"] = shift_temporal(ts, direction).ref_date
                        refresh()

                    return action

                ui.button(icon="chevron_left", on_click=shift(-1)).props("flat round")
                ui.button(icon="chevron_right", on_click=shift(1)).props("flat round")

            ui.html(
                f'<div class="row wrap" style="gap:8px">'
                f'{c.chip_html(format_temporal_label(ts), "brand")}'
                f'{c.chip_html(f"{start_iso} → {end_iso}")}'
                f'{c.chip_html(f"{len(txs)} movimientos")}'
                f"</div>"
            )

        with ui.tabs().classes("w-full") as tabs:
            tab_prices = ui.tab("Precios")
            tab_variants = ui.tab("Variantes")
            tab_pivot = ui.tab("Pivote")
            tab_frequency = ui.tab("Frecuencia")
            tab_projection = ui.tab("Proyecciones")
            tab_categories = ui.tab("Categorías")
            tab_extras = ui.tab("Extras")

        with ui.tab_panels(tabs, value=tab_prices).classes("w-full"):
            with ui.tab_panel(tab_prices):
                _tab_prices(state, txs)
            with ui.tab_panel(tab_variants):
                _tab_variants(state, txs)
            with ui.tab_panel(tab_pivot):
                _tab_pivot(state, txs)
            with ui.tab_panel(tab_frequency):
                _tab_frequency(state, txs)
            with ui.tab_panel(tab_projection):
                _tab_projection(state, txs)
            with ui.tab_panel(tab_categories):
                _tab_categories(state, txs)
            with ui.tab_panel(tab_extras):
                _tab_extras(state, txs)


#: (clave, etiqueta) de los períodos del selector temporal.
MODE_OPTIONS = {
    "week": "Semana",
    "month": "Mes",
    "bimester": "Bimestre",
    "quarter": "Trimestre",
    "quadrimester": "Cuatrimestre",
    "semester": "Semestre",
    "year": "Año",
    "custom": "Personalizado",
}


def _product_options(state: AppState, txs: list[dict[str, Any]]) -> dict[str, str]:
    ids = list(analytics_common.by_product(txs))
    names = {product.get("id"): product.get("name") for product in state.products}
    return {pid: names.get(pid) or pid for pid in ids}


def _tab_prices(state: AppState, txs: list[dict[str, Any]]) -> None:
    options = _product_options(state, txs)
    if not options:
        ui.html(c.empty_html("No hay productos con compras en el período."))
        return
    keys = list(options)
    with ui.row().classes("grid grid-cols-2 md:grid-cols-4 gap-3 w-full items-end"):
        pid_a = ui.select(options, value=keys[0], label="Producto A").classes("w-full")
        pid_b = ui.select(options, value=keys[1] if len(keys) > 1 else None, label="Producto B").classes("w-full")
        metric = ui.select({"usd": "Dólares", "bs": "Bolívares"}, value="usd", label="Métrica").classes("w-full")
    body = ui.column().classes("w-full gap-3")

    def recompute() -> None:
        view = analytics_inflation.analysis_a(
            txs,
            state.products,
            pid_a=pid_a.value or "",
            pid_b=pid_b.value or "",
            metric=metric.value or "usd",
            ctx=state.money,
        )
        body.clear()
        with body:
            ui.html(
                f'<div class="row wrap" style="gap:8px">'
                f'{c.chip_html(f"{view['puCount']} compras")}'
                f"{c.chip_html('Precio unitario medio ' + view['puAvg'], 'brand')}"
                f"{c.chip_html('Variación ' + view['puDelta'])}"
                f"{c.chip_html('CAGR ' + view['puCagr'])}"
                f"{c.chip_html('Laspeyres ' + view['laspeyresVal'], 'warn')}"
                f"{c.chip_html('Simple ' + view['laspeyresSimple'])}"
                f"{c.chip_html('Diferencia ' + view['laspeyresDiff'])}"
                f"</div>"
            )
            if view["chartLabels"]:
                series = [
                    {
                        "name": "A",
                        "type": "line",
                        "smooth": True,
                        "data": view["chartA"],
                        "connectNulls": True,
                    }
                ]
                if view["chartB"]:
                    series.append(
                        {
                            "name": "B",
                            "type": "line",
                            "smooth": True,
                            "data": view["chartB"],
                            "connectNulls": True,
                        }
                    )
                ui.echart(
                    {
                        "tooltip": {"trigger": "axis"},
                        "legend": {"top": 0},
                        "grid": {"left": 52, "right": 16, "top": 32, "bottom": 28},
                        "xAxis": {"type": "category", "data": view["chartLabels"]},
                        "yAxis": {"type": "value", "scale": True},
                        "series": series,
                    }
                ).classes("w-full h-64")
            if view["history"]:
                c.section_title("Histórico de precios del producto A")
                c.data_table(
                    ["Compra", "Detalle", "Precio", "Variación"],
                    [
                        (row["name"], row["meta"], row["price"], row["diff"])
                        for row in view["history"]
                    ],
                    align_right=(2, 3),
                )
            if view["top"]:
                c.section_title("Mayores subidas")
                c.data_table(
                    ["#", "Producto", "Detalle", "Variación"],
                    [
                        (row["pos"], row["name"], row["meta"], row["diff"])
                        for row in view["top"]
                    ],
                    align_right=(3,),
                )
            if view["stable"]:
                c.section_title("Más estables")
                c.data_table(
                    ["#", "Producto", "Detalle", "Variación"],
                    [
                        (str(position + 1), row["name"], row["meta"], row["diff"])
                        for position, row in enumerate(view["stable"])
                    ],
                    align_right=(3,),
                )

    for widget in (pid_a, pid_b, metric):
        widget.on_value_change(lambda _e=None: recompute())
    recompute()


def _tab_variants(state: AppState, txs: list[dict[str, Any]]) -> None:
    with ui.row().classes("grid grid-cols-2 gap-3 w-full items-end"):
        group_by = ui.select(GROUP_LABELS, value="unit", label="Agrupar por").classes("w-full").mark("analysis-variants-group")
        product_filter = ui.select(
            {pid: name for pid, name in _product_options(state, txs).items()},
            value=None,
            label="Filtrar por producto",
        ).classes("w-full").mark("analysis-variants-product")
    body = ui.column().classes("w-full gap-3")

    def recompute() -> None:
        view = analytics_variants.variants_view(
            txs,
            state.categories,
            group_by=group_by.value or "unit",
            product_filter=product_filter.value or "",
            ctx=state.money,
        )
        body.clear()
        with body:
            if view["empty"]:
                ui.html(c.empty_html(str(view["empty"])))
                return
            label = GROUP_LABELS.get(group_by.value or "unit", "Unidad")
            c.section_title(f"Variantes · {label}")
            chips = view["chips"]
            ui.html(
                f'{c.chip_html(f"{chips['variants']} variantes", "brand")}'
                f'{c.chip_html("Más económica: " + str(chips['bestKey']))}'
                f'{c.chip_html(str(chips["bestUnit"]))}'
            )
            if view["points"]:
                points = view["points"]
                data = []
                for row, point in zip(view["rows"], points):
                    data.append(
                        {
                            "name": row["key"],
                            "value": [point["x"], round(point["y"], 4)],
                            "symbolSize": round(point["r"] * 2, 2),
                            "itemStyle": {
                                "color": point["color"],
                                "borderColor": point["border"],
                                "borderWidth": point["width"],
                            },
                        }
                    )
                ui.echart(
                    {
                        "tooltip": {"trigger": "item"},
                        "grid": {"left": 64, "right": 24, "top": 24, "bottom": 44},
                        "xAxis": {"type": "value", "name": "Cantidad"},
                        "yAxis": {
                            "type": "value",
                            "name": "USD por unidad",
                            "scale": True,
                        },
                        "series": [
                            {
                                "type": "scatter",
                                "data": data,
                                "emphasis": {"focus": "series"},
                            }
                        ],
                    }
                ).classes("w-full h-64")
            c.data_table(
                ["Grupo", "Compras", "Cantidad", "Total", "Precio unitario", "Peso"],
                [
                    (
                        row["key"],
                        row["count"],
                        row["qty"],
                        row["usd"],
                        row["unitUsd"],
                        row["pct"],
                    )
                    for row in view["rows"]
                ],
                align_right=(1, 2, 3, 4, 5),
            )

    group_by.on_value_change(lambda _e=None: recompute())
    product_filter.on_value_change(lambda _e=None: recompute())
    recompute()


def _tab_pivot(state: AppState, txs: list[dict[str, Any]]) -> None:
    with ui.row().classes("grid grid-cols-3 gap-3 w-full items-end"):
        pivot_type = ui.select(PIVOT_LABELS, value="provider", label="Pivote por").classes("w-full")
        product_filter = ui.select(
            {pid: name for pid, name in _product_options(state, txs).items()},
            value=None,
            label="Filtrar por producto",
        ).classes("w-full")
        same_day = ui.checkbox("Solo compras del mismo día")
    body = ui.column().classes("w-full gap-3")

    def recompute() -> None:
        view = analytics_pivot.pivot_view(
            txs,
            pivot_type=pivot_type.value or "provider",
            product_filter=product_filter.value or "",
            same_day_only=bool(same_day.value),
            decimals=state.decimals,
        )
        body.clear()
        with body:
            if view["empty"]:
                ui.html(c.empty_html(str(view["empty"])))
                return
            summary = view["summary"]
            ui.html(
                f'{c.chip_html(f"{summary['groups']} grupos", "brand")}'
                f'{c.chip_html("Total " + summary["total"])}'
                f'{c.chip_html("Mejor: " + summary["cheapest"] + " · " + summary["cheapestAvg"], "ok")}'
                f'{c.chip_html("Peor: " + summary["mostExpensive"])}'
                f'{c.chip_html("Ahorro " + summary["savings"], "warn")}'
            )
            if view["chart"]["labels"]:
                chart = view["chart"]
                ui.echart(
                    {
                        "tooltip": {"trigger": "axis"},
                        "legend": {"top": 0},
                        "grid": {"left": 52, "right": 16, "top": 32, "bottom": 28},
                        "xAxis": {
                            "type": "category",
                            "data": chart["labels"],
                            "axisLabel": {"rotate": 30},
                        },
                        "yAxis": {"type": "value"},
                        "series": [
                            {"name": "Mínimo", "type": "bar", "data": chart["min"]},
                            {"name": "Medio", "type": "bar", "data": chart["avg"]},
                            {"name": "Máximo", "type": "bar", "data": chart["max"]},
                        ],
                    }
                ).classes("w-full h-64")
            c.data_table(
                ["Grupo", "Compras", "Total", "Mín", "Máx", "Media", "Mediana", "Desv."],
                [
                    (
                        row["key"],
                        row["count"],
                        row["totalUsd"],
                        row["minUsd"],
                        row["maxUsd"],
                        row["avgUsd"],
                        row["medUsd"],
                        row["stdUsd"],
                    )
                    for row in view["rows"]
                ],
                align_right=(1, 2, 3, 4, 5, 6, 7),
            )

    pivot_type.on_value_change(lambda _e=None: recompute())
    product_filter.on_value_change(lambda _e=None: recompute())
    same_day.on_value_change(lambda _e=None: recompute())
    recompute()


def _tab_frequency(state: AppState, txs: list[dict[str, Any]]) -> None:
    with ui.row().classes("grid grid-cols-2 gap-3 w-full items-end"):
        group_by = ui.select(GROUP_LABELS, value="provider", label="Agrupar por").classes("w-full").mark("analysis-frequency-group")
        order_by = ui.select(ORDER_LABELS, value="total", label="Ordenar por").classes("w-full").mark("analysis-frequency-order")
    body = ui.column().classes("w-full gap-3")

    def recompute() -> None:
        view = analytics_frequency.frequency_view(
            txs,
            state.categories,
            group_by=group_by.value or "provider",
            order_by=order_by.value or "total",
            decimals=state.decimals,
            now=state.audit_now(),
        )
        body.clear()
        with body:
            if view["empty"]:
                ui.html(c.empty_html(str(view["empty"])))
                return
            label = GROUP_LABELS.get(group_by.value or "provider", "Comercio")
            c.section_title(f"Frecuencia · {label}")
            if view.get("notice"):
                ui.html(
                    f'<div class="muted">{escape_html(str(view["notice"]))}</div>'
                )
            c.data_table(
                ["Grupo", "Compras", "Intervalo", "Cant. media", "Ticket medio", "Total", "Última", "Próxima"],
                [
                    (
                        row["key"],
                        row["count"],
                        row["interval"],
                        row["avgQty"],
                        row["avgTicket"],
                        row["totalUsd"],
                        row["lastDate"],
                        c.chip_html(row["next"], "warn") if row["soon"] else row["next"],
                    )
                    for row in view["rows"]
                ],
                align_right=(1, 3, 4, 5),
            )
            chart = view["chart"]
            if chart["labels"]:
                ui.echart(
                    {
                        "tooltip": {"trigger": "axis"},
                        "grid": {"left": 52, "right": 16, "top": 16, "bottom": 60},
                        "xAxis": {
                            "type": "category",
                            "data": chart["labels"],
                            "axisLabel": {"rotate": 30},
                        },
                        "yAxis": {"type": "value"},
                        "series": [
                            {"type": "bar", "data": chart["counts"], "itemStyle": {"color": "#2563EB"}}
                        ],
                    }
                ).classes("w-full h-56")

    group_by.on_value_change(lambda _e=None: recompute())
    order_by.on_value_change(lambda _e=None: recompute())
    recompute()


def _tab_projection(state: AppState, txs: list[dict[str, Any]]) -> None:
    with c.card():
        c.section_title("Proyección de la tasa de cambio")
        view = analytics_projection.rate_projection(state.rate_cache)
        if view["empty"]:
            ui.html(c.empty_html(str(view["empty"])))
        else:
            ui.html(c.chip_html(view["model"], "brand"))
            c.data_table(
                ["Días", "Tasa proyectada", "Variación"],
                [(str(row["days"]), row["rate"], row["pct"]) for row in view["rows"]],
                align_right=(1, 2),
            )
            chart = view["chart"]
            if chart:
                ui.echart(
                    {
                        "tooltip": {"trigger": "axis"},
                        "legend": {"top": 0},
                        "grid": {"left": 62, "right": 16, "top": 32, "bottom": 28},
                        "xAxis": {"type": "category", "data": chart["labels"]},
                        "yAxis": {"type": "value", "scale": True},
                        "series": [
                            {"name": "Real", "type": "line", "data": chart["actual"]},
                            {"name": "Proyectada", "type": "line", "data": chart["projected"], "lineStyle": {"type": "dashed"}},
                        ],
                    }
                ).classes("w-full h-64")

    options = _product_options(state, txs)
    with c.card():
        c.section_title("Proyección del precio de un producto")
        if not options:
            ui.html(c.empty_html("No hay productos con compras en el período."))
            return
        with ui.row().classes("grid grid-cols-3 gap-3 w-full items-end"):
            product = ui.select(options, value=next(iter(options)), label="Producto").classes("w-full")
            horizon = ui.select(
                {"30": "30 días", "60": "60 días", "90": "90 días", "custom": "Personalizado"},
                value="90",
                label="Horizonte",
            ).classes("w-full")
            custom_days = ui.number("Días", value=None, min=1).classes("w-full")
        body = ui.column().classes("w-full gap-2")

        def recompute() -> None:
            purchases = [
                tx for tx in txs if tx.get("productId") == product.value
            ]
            view = analytics_projection.product_projection(
                purchases,
                state.rate_cache,
                app_rate_value=state.rate_value,
                horizon_value=horizon.value or "90",
                custom_days=str(custom_days.value or ""),
                selected=bool(product.value),
            )
            body.clear()
            with body:
                if view["empty"]:
                    ui.html(c.empty_html(str(view["empty"])))
                    return
                stats = view["stats"]
                ui.html(
                    f'{c.chip_html("Actual " + stats['currentUsd'], "brand")}'
                    f'{c.chip_html("Proyectado " + stats["projUsd"])}'
                    f'{c.chip_html("Variación " + stats["deltaUsd"], "warn")}'
                )
                ui.html(
                    f'{c.chip_html("Actual Bs " + stats["currentBs"])}'
                    f'{c.chip_html("Proyectado Bs " + stats["projBs"])}'
                    f'{c.chip_html("Tasa " + stats["rate"])}'
                )
                ui.html(f'<div class="muted">{escape_html(view["model"] or "")}</div>')
                chart = view["chart"]
                if chart:
                    ui.echart(
                        {
                            "tooltip": {"trigger": "axis"},
                            "legend": {"top": 0},
                            "grid": {"left": 62, "right": 16, "top": 32, "bottom": 28},
                            "xAxis": {"type": "category", "data": chart["labels"]},
                            "yAxis": {"type": "value", "scale": True},
                            "series": [
                                {
                                    "name": "Real",
                                    "type": "line",
                                    "data": chart["actual"],
                                },
                                {
                                    "name": "Proyectada",
                                    "type": "line",
                                    "data": chart["projected"],
                                    "lineStyle": {"type": "dashed"},
                                },
                            ],
                        }
                    ).classes("w-full h-64")

        product.on_value_change(lambda _e=None: recompute())
        horizon.on_value_change(lambda _e=None: recompute())
        custom_days.on_value_change(lambda _e=None: recompute())
        recompute()


def _tab_categories(state: AppState, txs: list[dict[str, Any]]) -> None:
    impact = analytics_categories.category_impact(
        txs,
        state.categories,
        app_rate_value=state.rate_value,
        decimals=state.decimals,
    )
    audit = analytics_categories.vat_audit(txs)
    payments = analytics_categories.payment_impact(txs, decimals=state.decimals)

    with c.card():
        c.section_title("Impacto por categoría")
        if impact["empty"]:
            ui.html(c.empty_html(str(impact["empty"])))
        else:
            ui.html(
                f'{c.chip_html("IVA total " + audit["ivaTotal"])}'
                f'{c.chip_html("Base " + audit["baseTotal"])}'
                f'{c.chip_html("IVA ponderado " + audit["weightedIva"], "brand")}'
                f'{c.chip_html("Gravadas " + audit["taxed"])}'
                f'{c.chip_html("Exentas " + audit["exento"])}'
                f'{c.chip_html("Exento " + audit["exentoTotal"], "ok")}'
            )
            c.data_table(
                ["Categoría", "Compras", "Total", "Peso", "IVA", "Inflación extra"],
                [
                    (
                        row["name"],
                        row["count"],
                        row["totalUsd"],
                        row["pct"],
                        row["ivaUsd"],
                        row["extraInflation"],
                    )
                    for row in impact["rows"]
                ],
                align_right=(1, 2, 3, 4, 5),
            )
            chart = impact["chart"]
            if chart["labels"]:
                ui.echart(
                    {
                        "tooltip": {"trigger": "item"},
                        "series": [
                            {
                                "type": "pie",
                                "radius": ["45%", "72%"],
                                "data": [
                                    {"name": name, "value": round(value, 2)}
                                    for name, value in zip(chart["labels"], chart["values"])
                                ],
                            }
                        ],
                    }
                ).classes("w-full h-64")

    with c.card():
        c.section_title("Reparto por método de pago")
        if not payments["rows"]:
            ui.html(c.empty_html("Sin datos de pago."))
        else:
            c.data_table(
                ["Método", "Compras", "Total", "Peso"],
                [
                    (row["key"], row["count"], row["totalUsd"], row["pct"])
                    for row in payments["rows"]
                ],
                align_right=(1, 2, 3),
            )


def _tab_extras(state: AppState, txs: list[dict[str, Any]]) -> None:
    now = state.audit_now()

    with c.card():
        c.section_title("Semáforo de presupuesto por categoría")
        budget = analytics_extras.budget_traffic_light(
            txs, state.categories, fiscal_year=state.fiscal_year, now=now, ctx=state.money
        )
        if budget["empty"]:
            ui.html(c.empty_html(str(budget["empty"])))
        else:
            c.data_table(
                ["Categoría", "Mes actual", "Media previa", "Variación", "Meses", "Estado"],
                [
                    (
                        row["name"],
                        row["current"],
                        row["average"],
                        row["delta"],
                        row["months"],
                        c.chip_html(
                            row["chip"],
                            {
                                "over": "bad",
                                "under": "ok",
                                "ok": "ok",
                                "zero": "",
                                "new": "brand",
                            }.get(row.get("state", "ok"), ""),
                        ),
                    )
                    for row in budget["rows"]
                ],
                align_right=(1, 2, 3, 4),
            )

    with c.card():
        c.section_title("Pareto 80/20 por categoría")
        pareto = analytics_extras.pareto(txs, state.categories)
        if pareto["empty"]:
            ui.html(c.empty_html("Sin datos para el Pareto."))
        else:
            ui.echart(
                {
                    "tooltip": {"trigger": "axis"},
                    "legend": {"top": 0},
                    "grid": {"left": 52, "right": 52, "top": 32, "bottom": 60},
                    "xAxis": {
                        "type": "category",
                        "data": pareto["labels"],
                        "axisLabel": {"rotate": 30},
                    },
                    "yAxis": [
                        {"type": "value"},
                        {"type": "value", "max": 100, "axisLabel": {"formatter": "{value}%"}},
                    ],
                    "series": [
                        {
                            "name": "Gasto",
                            "type": "bar",
                            "data": [
                                {"value": round(value, 2), "itemStyle": {"color": color}}
                                for value, color in zip(pareto["values"], pareto["colors"])
                            ],
                        },
                        {
                            "name": "Acumulado",
                            "type": "line",
                            "yAxisIndex": 1,
                            "data": [round(value, 2) for value in pareto["cumulative"]],
                        },
                    ],
                }
            ).classes("w-full h-64")

    with c.card():
        c.section_title("Dispersión de importes por día")
        scatter = analytics_extras.outlier_scatter(txs, state.categories)
        if scatter["empty"]:
            ui.html(c.empty_html("Sin datos para la dispersión."))
        else:
            ui.html(c.chip_html(f"Umbral de outlier: {scatter['threshold']:.2f} USD", "warn"))
            per_category: dict[str, dict[str, Any]] = {}
            for point in scatter["points"]:
                group = per_category.setdefault(
                    point["catName"],
                    {"label": point["catName"], "color": point["color"], "data": []},
                )
                group["data"].append(
                    {
                        "value": [point["x"], round(point["y"], 2)],
                        "itemStyle": {
                            "color": point["color"],
                            "borderColor": "#EF4444" if point["outlier"] else point["color"],
                            "borderWidth": 2 if point["outlier"] else 1,
                        },
                        "name": point["tooltip"],
                    }
                )
            ui.echart(
                {
                    "tooltip": {"trigger": "item"},
                    "grid": {"left": 52, "right": 16, "top": 24, "bottom": 32},
                    "xAxis": {"type": "value", "name": "día"},
                    "yAxis": {"type": "value", "name": "USD"},
                    "series": [
                        {"name": group["label"], "type": "scatter", "data": group["data"]}
                        for group in per_category.values()
                    ],
                }
            ).classes("w-full h-64")

    with c.card():
        c.section_title("Árbol jerárquico categoría → subcategoría → producto")
        tree = analytics_extras.hierarchical_tree(txs, state.categories, ctx=state.money)
        if tree["empty"]:
            ui.html(c.empty_html(str(tree["empty"])))
        else:
            c.data_table(
                ["Nivel", "Nombre", "Cantidad", "Total"],
                [
                    (
                        "Categoría" if node["level"] == "cat" else "Subcategoría",
                        node["name"],
                        node["qty"],
                        node["total"],
                    )
                    for node in tree["nodes"]
                ],
                align_right=(2, 3),
            )
            if tree["prods"]:
                c.section_title("Productos")
                c.data_table(
                    ["SKU", "Veces", "Producto", "Detalle"],
                    [
                        (
                            c.raw(f'<span class="muted">{escape_html(row["id"])}</span>'),
                            row["pos"],
                            row["name"],
                            row["meta"],
                        )
                        for row in tree["prods"]
                    ],
                    align_right=(1,),
                )
