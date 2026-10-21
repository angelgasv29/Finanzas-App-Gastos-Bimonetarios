"""Sub-pestaña A · Precio e inflación (``runAnalysisA``, líneas 5014-5192).

Incluye el comparador A/B y el índice de **Laspeyres** ponderado por gasto
(M9). Las series del gráfico replican ``seriesFromHist``: los días sin compra
repiten el último precio conocido.
"""

from __future__ import annotations

from typing import Any

from ..core.money import (
    MoneyContext,
    format_bs,
    format_pct,
    format_usd,
    js_to_fixed,
)
from ..core.stats import cagr, mean, unit_price
from ..core.text import js_to_string
from .common import MS_PER_DAY, ProductHistory, build_history, by_product, series_from_history

__all__ = ["analysis_a", "laspeyres", "inflation_rankings"]

# ``weighted > 15`` → rojo; ``> 0`` → ámbar (5099).
BAD_INFLATION = 15


def _js_number(value: float) -> str:
    """Número como texto de JavaScript (``2`` y no ``2.0``)."""
    return js_to_string(value)


def laspeyres(
    grouped: dict[str, list[dict[str, Any]]]
) -> dict[str, float]:
    """Inflación ponderada por gasto frente a la media simple (5076-5094).

    Solo entran los productos con al menos dos compras y gasto positivo; el peso
    es el gasto total en USD y la variación es la del precio unitario entre la
    primera y la última compra.

    >>> grouped = {
    ...   "a": [{"date": "2026-01-01", "quantity": 1, "amountUsd": 10},
    ...         {"date": "2026-02-01", "quantity": 1, "amountUsd": 12}],
    ...   "b": [{"date": "2026-01-01", "quantity": 1, "amountUsd": 90},
    ...         {"date": "2026-02-01", "quantity": 1, "amountUsd": 99}],
    ... }
    >>> r = laspeyres(grouped)
    >>> round(r["weighted"], 2), round(r["simple"], 2)
    (11.04, 15.0)

    El peso es el **gasto total** del producto (22 y 189), no el de una compra.

    >>> round(r["diff"], 2)
    -3.96
    """
    weights: list[tuple[float, float]] = []
    for purchases in grouped.values():
        if len(purchases) < 2:
            continue
        total_usd = 0.0
        for tx in purchases:
            total_usd += float(tx.get("amountUsd") or 0)
        if total_usd <= 0:
            continue
        first = unit_price(purchases[0])["unitUsd"]
        last = unit_price(purchases[-1])["unitUsd"]
        pct = ((last - first) / first) * 100 if first > 0 else 0.0
        weights.append((total_usd, pct))

    sum_w = 0.0
    for weight, _pct in weights:
        sum_w += weight

    weighted = 0.0
    if sum_w > 0:
        accumulated = 0.0
        for weight, pct in weights:
            accumulated += weight * pct
        weighted = accumulated / sum_w

    simple = 0.0
    if weights:
        accumulated = 0.0
        for _weight, pct in weights:
            accumulated += pct
        simple = accumulated / len(weights)

    return {"weighted": weighted, "simple": simple, "diff": weighted - simple}


def inflation_rankings(
    grouped: dict[str, list[dict[str, Any]]],
    products: list[dict[str, Any]],
    *,
    is_bs: bool = False,
) -> list[dict[str, Any]]:
    """Productos ordenados por variación de precio (5167-5177).

    >>> grouped = {"p1": [{"date": "2026-01-01", "quantity": 1, "amountUsd": 2},
    ...                  {"date": "2026-02-01", "quantity": 1, "amountUsd": 3}]}
    >>> rows = inflation_rankings(grouped, [{"id": "p1", "name": "Harina"}])
    >>> rows[0]["name"], round(rows[0]["pct"], 1), rows[0]["count"]
    ('Harina', 50.0, 2)
    """
    names = {product["id"]: product.get("name") or product["id"] for product in products}
    rankings: list[dict[str, Any]] = []
    for product_id, purchases in grouped.items():
        if len(purchases) < 2:
            continue
        first = unit_price(purchases[0])
        last = unit_price(purchases[-1])
        first_unit = first["unitBs"] if is_bs else first["unitUsd"]
        last_unit = last["unitBs"] if is_bs else last["unitUsd"]
        if not first_unit:
            continue
        pct = ((last_unit - first_unit) / first_unit) * 100
        rankings.append(
            {
                "pid": product_id,
                "name": names.get(product_id, product_id),
                "pct": pct,
                "count": len(purchases),
                "firstDate": purchases[0].get("date") or "",
                "lastDate": purchases[-1].get("date") or "",
            }
        )
    rankings.sort(key=lambda row: row["pct"], reverse=True)
    return rankings


def _history_row(point: ProductHistory, is_bs: bool, real_index: int) -> dict[str, Any]:
    price = format_bs(point.unit) if is_bs else format_usd(point.unit, 4)
    if real_index > 0:
        diff = ("+" if point.diff_pct >= 0 else "") + js_to_fixed(point.diff_pct, 2) + "%"
        diff_class = "up" if point.diff_pct > 0 else "down" if point.diff_pct < 0 else "flat"
    else:
        diff = "1ª compra"
        diff_class = "muted"
    return {
        "name": f"{point.date} · {point.provider or '—'}",
        "meta": f"Cant: {_js_number(point.qty)} {point.unit_name}",
        "price": price,
        "diff": diff,
        "diffClass": diff_class,
    }


def analysis_a(
    txs: list[dict[str, Any]],
    products: list[dict[str, Any]],
    *,
    pid_a: str = "",
    pid_b: str = "",
    metric: str = "usd",
    ctx: MoneyContext | None = None,
) -> dict[str, Any]:
    """Vista completa de la sub-pestaña A.

    >>> ctx = MoneyContext("USD", 2, 40.0)
    >>> compras = [
    ...   {"productId": "p1", "date": "2026-01-10", "quantity": 2, "amountUsd": 5,
    ...    "amountBs": 200, "provider": "Mercado"},
    ...   {"productId": "p1", "date": "2026-02-10", "quantity": 2, "amountUsd": 8,
    ...    "amountBs": 320},
    ... ]
    >>> view = analysis_a(compras, [{"id": "p1", "name": "Harina"}], pid_a="p1", ctx=ctx)
    >>> view["puCount"], view["puAvg"], view["puDelta"]
    ('2', '$ 3.25', '+60.00%')
    >>> [row["diff"] for row in view["history"]]
    ['+60.00%', '1ª compra']
    >>> view["chartLabels"], view["chartA"]
    (['2026-01-10', '2026-02-10'], [2.5, 4.0])
    """
    ctx = ctx or MoneyContext("USD", 2, None)
    is_bs = metric == "bs"
    grouped = by_product(txs)

    product_txs = [
        tx for tx in txs if tx.get("productId") and tx.get("productId") != ""
    ]

    view: dict[str, Any] = {}

    if pid_a:
        history = build_history(grouped.get(pid_a, []), is_bs=is_bs)
        count = len(history)
        view["puCount"] = str(count)
        if count:
            units = [point.unit for point in history]
            average = mean(units)
            view["puAvg"] = format_bs(average) if is_bs else format_usd(average, ctx.decimals)
            first = history[0].unit
            last = history[-1].unit
            delta = ((last - first) / first) * 100 if first else 0.0
            view["puDelta"] = ("+" if delta >= 0 else "") + format_pct(delta)
            view["puDeltaClass"] = (
                "val bad" if delta > 1 else "val ok" if delta < -1 else "val warn"
            )
            first_date = _parse_iso(history[0].date)
            last_date = _parse_iso(history[-1].date)
            days = (
                (last_date - first_date).days if first_date and last_date else 0
            )
            growth = cagr(first, last, days)
            view["puCagr"] = ("+" if growth >= 0 else "") + format_pct(growth) + " / año"
            view["puCagrClass"] = (
                "val bad" if growth > 20 else "val warn" if growth > 0 else "val ok"
            )
        else:
            view["puAvg"] = "—"
            view["puDelta"] = "—"
            view["puDeltaClass"] = ""
            view["puCagr"] = "—"
            view["puCagrClass"] = ""

        total = len(history)
        view["history"] = [
            _history_row(point, is_bs, total - 1 - index)
            for index, point in enumerate(reversed(history))
        ]
    else:
        view["puCount"] = str(len(product_txs))
        view["puAvg"] = "—"
        view["puDelta"] = "—"
        view["puDeltaClass"] = ""
        view["puCagr"] = "—"
        view["puCagrClass"] = ""
        view["history"] = []

    # --- Laspeyres ---------------------------------------------------------
    index = laspeyres(grouped)
    view["laspeyresVal"] = (
        ("+" if index["weighted"] >= 0 else "") + js_to_fixed(index["weighted"], 2) + "%"
    )
    view["laspeyresValClass"] = (
        "val bad"
        if index["weighted"] > BAD_INFLATION
        else "val warn"
        if index["weighted"] > 0
        else "val ok"
    )
    view["laspeyresSimple"] = (
        ("+" if index["simple"] >= 0 else "") + js_to_fixed(index["simple"], 2) + "%"
    )
    view["laspeyresSimpleClass"] = (
        "val bad"
        if index["simple"] > BAD_INFLATION
        else "val warn"
        if index["simple"] > 0
        else "val ok"
    )
    view["laspeyresDiff"] = (
        ("+" if index["diff"] >= 0 else "") + js_to_fixed(index["diff"], 2) + " pp"
    )
    view["laspeyresDiffClass"] = "val brand" if abs(index["diff"]) > 3 else "val muted"

    # --- Serie del gráfico A/B --------------------------------------------
    if pid_a:
        history_a = build_history(grouped.get(pid_a, []), is_bs=is_bs)
        history_b = build_history(grouped.get(pid_b, []), is_bs=is_bs) if pid_b else []
        dates = sorted(
            {point.date for point in history_a} | {point.date for point in history_b}
        )
        view["chartLabels"] = dates
        view["chartA"] = series_from_history(history_a, dates)
        view["chartB"] = series_from_history(history_b, dates) if history_b else []
    else:
        view["chartLabels"] = []
        view["chartA"] = []
        view["chartB"] = []

    # --- Rankings ----------------------------------------------------------
    rankings = inflation_rankings(grouped, products, is_bs=is_bs)
    top = [row for row in rankings if row["pct"] > 0][:10]
    stable = [
        row for row in rankings if row["pct"] <= 0 or abs(row["pct"]) < 5
    ][-8:]
    stable.reverse()

    view["top"] = [
        {
            "pos": str(position + 1),
            "name": row["name"],
            "meta": (
                f"{row['count']} compras · {row['firstDate']} → {row['lastDate']}"
            ),
            "diff": "+" + js_to_fixed(row["pct"], 1) + "%",
            "cls": f"top{position + 1}" if position < 3 else "",
        }
        for position, row in enumerate(top)
    ]
    view["stable"] = [
        {
            "name": row["name"],
            "meta": f"{row['count']} compras",
            "diff": (
                ("" if row["pct"] < 0 else "+" if row["pct"] > 0 else "")
                + js_to_fixed(row["pct"], 1)
                + "%"
            ),
            "diffClass": "down" if row["pct"] < 0 else "flat",
        }
        for row in stable
    ]

    return view


def _parse_iso(value: str) -> Any:
    from datetime import date

    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None
