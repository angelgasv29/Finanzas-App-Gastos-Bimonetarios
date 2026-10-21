"""Panel 1 · Dashboard: resumen del ejercicio y del mes en curso."""

from __future__ import annotations

from typing import Any

from nicegui import ui

from ...analytics import categories as analytics_categories
from ...domain import breakeven, pace, recurring, runrate
from .. import components as c
from ..state import AppState

__all__ = ["render"]


def _monthly_series(txs: list[dict[str, Any]]) -> tuple[list[str], list[float], list[float]]:
    """Suma por mes (``YYYY-MM``) en orden cronológico."""
    usd: dict[str, float] = {}
    bs: dict[str, float] = {}
    for tx in txs:
        key = runrate.month_key_of(tx.get("date"))
        usd[key] = usd.get(key, 0.0) + float(tx.get("amountUsd") or 0)
        bs[key] = bs.get(key, 0.0) + float(tx.get("amountBs") or 0)
    keys = sorted(key for key in usd if key)
    return keys, [usd[key] for key in keys], [bs[key] for key in keys]


def _build(state: AppState) -> None:
    now = state.audit_now()
    year_txs = state.year_transactions()
    ctx = state.money

    total_usd = 0.0
    total_bs = 0.0
    for tx in year_txs:
        total_usd += float(tx.get("amountUsd") or 0)
        total_bs += float(tx.get("amountBs") or 0)

    rate_view = runrate.run_rate_view(
        year_txs, fiscal_year=state.fiscal_year, now=now, ctx=ctx
    )
    indicator = pace.compute_pace_indicator(
        year_txs, fiscal_year=state.fiscal_year, now=now
    )
    pace_view = pace.pace_indicator_view(indicator, ctx)
    even = breakeven.break_even_view(
        year_txs, fiscal_year=state.fiscal_year, now=now, ctx=ctx
    )
    commitments = recurring.find_recurring_commitments(
        year_txs, fiscal_year=state.fiscal_year, now=now
    )
    recur_view = recurring.recurring_view(commitments, ctx)

    with ui.column().classes("w-full gap-4 p-4"):
        with ui.row().classes("grid grid-cols-2 md:grid-cols-4 gap-4 w-full"):
            with c.card():
                c.kpi(
                    f"Ejercicio {state.fiscal_year}",
                    state.fmt(total_usd, total_bs),
                    f"{len(year_txs)} movimientos",
                )
            with c.card():
                c.kpi("Proyección del mes", rate_view["runRateProj"], rate_view["runRateSub"])
                ui.html(c.bar_html(rate_view["runRateBar"].rstrip("%")))
                ui.html(f'<div class="muted text-xs">{rate_view["runRateDay"]}</div>')
            with c.card():
                c.kpi("Ritmo vs mes previo", pace_view["paceRatio"], pace_view["paceSub"])
                ui.html(
                    c.chip_html(
                        pace_view["paceChip"],
                        pace_view["paceChipClass"].replace("chip ", ""),
                    )
                )
            with c.card():
                c.kpi("Compromisos recurrentes", recur_view["recurringCommitted"], "pendientes")
                ui.html(
                    c.chip_html(
                        recur_view["recurringChip"],
                        recur_view["recurringChipClass"].replace("chip ", ""),
                    )
                )

        with ui.row().classes("grid grid-cols-1 lg:grid-cols-2 gap-4 w-full"):
            with c.card():
                c.section_title("Evolución mensual del ejercicio")
                keys, usd, bs = _monthly_series(year_txs)
                if not keys:
                    ui.html(c.empty_html("Todavía no hay movimientos este ejercicio."))
                else:
                    ui.echart(
                        {
                            "tooltip": {"trigger": "axis"},
                            "grid": {"left": 48, "right": 16, "top": 24, "bottom": 28},
                            "xAxis": {"type": "category", "data": keys},
                            "yAxis": {"type": "value"},
                            "series": [
                                {
                                    "name": "USD",
                                    "type": "bar",
                                    "data": [round(value, 2) for value in usd],
                                    "itemStyle": {"color": "#2563EB"},
                                }
                            ],
                        }
                    ).classes("w-full h-64")
            with c.card():
                c.section_title("Reparto por categoría")
                impact = analytics_categories.category_impact(
                    year_txs,
                    state.categories,
                    app_rate_value=state.rate_value,
                    decimals=state.decimals,
                )
                if not impact["rows"]:
                    ui.html(c.empty_html("Sin datos de categorías este ejercicio."))
                else:
                    ui.echart(
                        {
                            "tooltip": {"trigger": "item"},
                            "series": [
                                {
                                    "type": "pie",
                                    "radius": ["45%", "72%"],
                                    "data": [
                                        {"name": name, "value": round(value, 2)}
                                        for name, value in zip(
                                            impact["chart"]["labels"],
                                            impact["chart"]["values"],
                                        )
                                    ],
                                }
                            ],
                        }
                    ).classes("w-full h-64")

        with c.card():
            c.section_title(
                "Fijo vs. variable",
                c.chip_html(
                    f"Fijo {even['beFixedBar']}",
                    "ok",
                )
                + c.chip_html(f"Variable {even['beVarBar']}", "brand"),
            )
            ui.html(f'<div class="muted text-xs">{even["breakEvenSub"]}</div>')
            with ui.row().classes("grid grid-cols-2 gap-4 w-full"):
                with ui.column().classes("gap-1 w-full"):
                    ui.html(f'<div class="muted text-xs">Fijo · {even["beFixedVal"]}</div>')
                    ui.html(c.bar_html(even["beFixedBar"].rstrip("%"), "var(--ok)"))
                with ui.column().classes("gap-1 w-full"):
                    ui.html(f'<div class="muted text-xs">Variable · {even["beVarVal"]}</div>')
                    ui.html(c.bar_html(even["beVarBar"].rstrip("%"), "var(--accent)"))

        with c.card():
            c.section_title("Últimos movimientos", c.chip_html(f"{len(year_txs)} en el año"))
            recent = sorted(
                year_txs, key=lambda tx: (str(tx.get("date") or ""), tx.get("id") or 0), reverse=True
            )[:12]
            if not recent:
                ui.html(c.empty_html("Sin movimientos."))
            else:
                c.data_table(
                    ["Fecha", "Producto", "Categoría", "Cantidad", "Total", "IVA"],
                    [
                        (
                            tx.get("date") or "—",
                            tx.get("productName") or "—",
                            state.category_name(tx.get("categoryId")) or "—",
                            f"{tx.get('quantity') or 0} {tx.get('unit') or ''}".strip(),
                            state.fmt(tx.get("amountUsd"), tx.get("amountBs")),
                            c.chip_html(
                                tx.get("taxMode") or "incluido",
                                "" if tx.get("taxMode") != "exento" else "ok",
                            ),
                        )
                        for tx in recent
                    ],
                    align_right=(3, 4),
                )


def render(state: AppState) -> None:
    @ui.refreshable
    def content() -> None:
        _build(state)

    content()
    state.subscribe(content.refresh)
