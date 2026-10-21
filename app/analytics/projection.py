"""Sub-pestaña D · Proyecciones (``runAnalysisD``, 5490-5610).

Dos bloques:

1. **Tasa de cambio**: regresión lineal sobre todas las tasas históricas y
   proyección a 7, 30, 90, 180 y 365 días.
2. **Precio de un producto**: regresión lineal del precio unitario (USD y Bs)
   sobre los días transcurridos desde su primera compra.

La fecha futura del gráfico se calcula como en la versión de referencia:
``dateToISO(new Date(fecha_utc + d días))``, es decir, con los getters
**locales**; en un huso negativo eso devuelve el día anterior.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from ..core.money import (
    format_bs,
    format_rate,
    format_usd,
    js_number_or_zero,
    js_to_fixed,
)
from ..core.periods import date_to_iso
from ..core.stats import linear_regression, unit_price
from ..domain.dates import local_date_at, utc_midnight_ms

__all__ = ["rate_projection", "product_projection"]

MS_PER_DAY = 86_400_000
HORIZONS = (7, 30, 90, 180, 365)


def _days_between(start: str, end: str) -> float:
    """``(new Date(end) - new Date(start)) / 86400000`` (medianoche UTC)."""
    first = utc_midnight_ms(start)
    second = utc_midnight_ms(end)
    if first is None or second is None:
        return 0.0
    return (second - first) / MS_PER_DAY


def _future_date(start: str, days: float) -> str:
    """``dateToISO(new Date(start) + días)`` con getters locales."""
    base = utc_midnight_ms(start)
    if base is None:
        return start
    return date_to_iso(local_date_at(base + days * MS_PER_DAY))


def _sorted_rates(rates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rates, key=lambda rate: rate.get("date") or "")


def rate_projection(
    rates: list[dict[str, Any]],
    *,
    chart_available: bool = True,
) -> dict[str, Any]:
    """Proyección de la tasa de cambio.

    >>> rates = [
    ...   {"date": "2026-01-01", "value": 40.0},
    ...   {"date": "2026-03-01", "value": 60.0},
    ... ]
    >>> view = rate_projection(rates)
    >>> [(row["days"], row["rate"], row["pct"]) for row in view["rows"]][:2]
    [(7, '62,3729 Bs/$', '+3.95%'), (30, '70,1695 Bs/$', '+16.95%')]
    >>> view["model"]
    'y = 40.0000 + 0.3390·días · R²=1.000'
    """
    ordered = _sorted_rates(rates)
    if len(ordered) < 2:
        return {
            "empty": "Se necesitan al menos 2 tasas históricas registradas.",
            "rows": [],
            "model": None,
            "chart": None,
        }

    base_date = ordered[0].get("date") or ""
    xs = [_days_between(base_date, rate.get("date") or "") for rate in ordered]
    ys = [js_number_or_zero(rate.get("value")) for rate in ordered]
    regression = linear_regression(xs, ys)
    last_x = xs[-1]
    last_y = ys[-1]

    rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        projected_x = last_x + horizon
        projected_y = regression["a"] + regression["b"] * projected_x
        pct = ((projected_y - last_y) / last_y) * 100 if last_y else 0.0
        rows.append(
            {
                "days": horizon,
                "rate": format_rate(projected_y) + " Bs/$",
                "pct": ("+" if pct >= 0 else "") + js_to_fixed(pct, 2) + "%",
                "up": pct > 0,
            }
        )

    model = (
        f"y = {js_to_fixed(regression['a'], 4)} + "
        f"{js_to_fixed(regression['b'], 4)}·días"
        f" · R²={js_to_fixed(regression['r2'], 3)}"
    )

    chart: dict[str, Any] | None = None
    if chart_available:
        labels = [rate.get("date") or "" for rate in ordered]
        actuals = list(ys)
        future_labels: list[str] = []
        future_values: list[float] = []
        days = 7
        while days <= 90:
            future_labels.append(_future_date(labels[-1], days))
            future_values.append(regression["a"] + regression["b"] * (last_x + days))
            days += 7
        chart = {
            "labels": labels + future_labels,
            "actual": actuals + [None] * len(future_labels),
            "projected": [None] * (len(labels) - 1) + [actuals[-1]] + future_values,
        }

    return {"empty": None, "rows": rows, "model": model, "chart": chart}


def product_projection(
    purchases: list[dict[str, Any]],
    rates: list[dict[str, Any]],
    *,
    app_rate_value: float | None = None,
    horizon_value: str = "90",
    custom_days: str = "",
    selected: bool = True,
    chart_available: bool = True,
) -> dict[str, Any]:
    """Proyección del precio unitario de un producto.

    >>> compras = [
    ...   {"date": "2026-01-01", "quantity": 1, "amountUsd": 2, "amountBs": 80},
    ...   {"date": "2026-04-01", "quantity": 1, "amountUsd": 4, "amountBs": 160},
    ... ]
    >>> view = product_projection(compras, [], horizon_value="30")
    >>> view["stats"]["currentUsd"], view["stats"]["projUsd"]
    ('$ 4.0000', '$ 4.6667')
    >>> view["stats"]["deltaUsd"]
    '+16.67%'
    """
    if not selected:
        return {
            "empty": "Selecciona un producto.",
            "stats": None,
            "model": None,
            "chart": None,
        }

    if len(purchases) < 2:
        return {
            "empty": "Se necesitan al menos 2 compras del producto.",
            "stats": None,
            "model": None,
            "chart": None,
        }

    ordered = sorted(purchases, key=lambda tx: tx.get("date") or "")
    base_date = ordered[0].get("date") or ""
    xs = [_days_between(base_date, tx.get("date") or "") for tx in ordered]
    units = [unit_price(tx) for tx in ordered]
    ys_usd = [price["unitUsd"] for price in units]
    ys_bs = [price["unitBs"] for price in units]
    regression_usd = linear_regression(xs, ys_usd)
    regression_bs = linear_regression(xs, ys_bs)

    last_x = xs[-1]
    last_usd = ys_usd[-1]
    last_bs = ys_bs[-1]

    if horizon_value == "custom":
        try:
            horizon = int(float(custom_days))
        except (TypeError, ValueError):
            horizon = 0
        if not horizon:
            horizon = 30
    else:
        try:
            horizon = int(float(horizon_value))
        except (TypeError, ValueError):
            horizon = 0

    projected_x = last_x + horizon
    proj_usd = regression_usd["a"] + regression_usd["b"] * projected_x
    proj_bs = regression_bs["a"] + regression_bs["b"] * projected_x
    delta_usd = ((proj_usd - last_usd) / last_usd) * 100 if last_usd else 0.0
    delta_bs = ((proj_bs - last_bs) / last_bs) * 100 if last_bs else 0.0

    ordered_rates = _sorted_rates(rates)
    projected_rate = js_number_or_zero(app_rate_value) or last_bs
    if len(ordered_rates) >= 2:
        rate_base = ordered_rates[0].get("date") or ""
        rate_xs = [
            _days_between(rate_base, rate.get("date") or "")
            for rate in ordered_rates
        ]
        rate_ys = [js_number_or_zero(rate.get("value")) for rate in ordered_rates]
        rate_regression = linear_regression(rate_xs, rate_ys)
        projected_rate = rate_regression["a"] + rate_regression["b"] * (
            rate_xs[-1] + horizon
        )

    model = {
        "usd": (
            f"y = {js_to_fixed(regression_usd['a'], 4)} + "
            f"{js_to_fixed(regression_usd['b'], 5)}·d · R² = "
            f"{js_to_fixed(regression_usd['r2'], 3)}"
        ),
        "bs": (
            f"y = {js_to_fixed(regression_bs['a'], 2)} + "
            f"{js_to_fixed(regression_bs['b'], 4)}·d · R² = "
            f"{js_to_fixed(regression_bs['r2'], 3)}"
        ),
        "count": len(ordered),
        "from": ordered[0].get("date") or "",
        "to": ordered[-1].get("date") or "",
    }

    stats = {
        "horizon": horizon,
        "currentUsd": format_usd(last_usd, 4),
        "projUsd": format_usd(proj_usd, 4),
        "deltaUsd": ("+" if delta_usd >= 0 else "") + js_to_fixed(delta_usd, 2) + "%",
        "deltaUsdUp": delta_usd > 0,
        "currentBs": format_bs(last_bs),
        "projBs": format_bs(proj_bs),
        "deltaBs": ("+" if delta_bs >= 0 else "") + js_to_fixed(delta_bs, 2) + "%",
        "deltaBsUp": delta_bs > 0,
        "rate": format_rate(projected_rate) + " Bs/$",
    }

    chart: dict[str, Any] | None = None
    if chart_available:
        step = -(-horizon // 6)  # Math.ceil(horizon / 6)
        labels = [tx.get("date") or "" for tx in ordered]
        future_labels: list[str] = []
        future_values: list[float] = []
        if step > 0:
            days = step
            while days <= horizon:
                future_labels.append(_future_date(labels[-1], days))
                future_values.append(
                    regression_usd["a"]
                    + regression_usd["b"] * (last_x + days)
                )
                days += step
        chart = {
            "labels": labels + future_labels,
            "actual": list(ys_usd) + [None] * len(future_labels),
            "projected": [None] * (len(labels) - 1)
            + [ys_usd[-1]]
            + future_values,
        }

    return {"empty": None, "stats": stats, "model": model, "chart": chart}
