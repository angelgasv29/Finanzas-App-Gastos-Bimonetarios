"""Sub-pestaña E · extras (M2, M3a, M3b, M3c y M4).

Cinco renders que la versión de referencia lanza detrás del sub-panel E:

======================  ============================================
``renderBudgetTrafficLight``  Semáforo de gasto por categoría (M2)
``renderParetoChart``         Pareto 80/20 por categoría (M3a)
``renderCategorySparklines``  Mini-series de 6 meses por categoría (M3b)
``renderOutlierScatter``      Dispersión de importes con outliers (M3c)
``renderHierarchicalTree``    Árbol categoría → subcategoría → producto (M4)
======================  ============================================
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..core.money import MoneyContext, fmt_money, js_number_or_zero, js_to_fixed
from ..core.stats import mean, stdev
from ..domain.dates import js_date, resolve_active_audit_month

__all__ = [
    "budget_traffic_light",
    "pareto",
    "sparklines",
    "outlier_scatter",
    "hierarchical_tree",
]

NO_CATEGORY = "Sin categoría"
NO_CATEGORY_COLOR = "#6B7280"
NO_SUBCATEGORY = "— Sin subcategoría —"
SPARK_COLOR = "#2563EB"


def budget_traffic_light(
    txs: list[dict[str, Any]],
    categories: list[dict[str, Any]],
    *,
    fiscal_year: Any,
    now: datetime,
    ctx: MoneyContext,
) -> dict[str, Any]:
    """Semáforo de presupuesto por categoría (ajuste, línea 7676).

    Compara el gasto del **mes auditado** de cada categoría con su promedio de
    los meses anteriores. Estados: ``over`` (> +5 %), ``ok`` (±5 %), ``under``
    (< −5 %), ``zero`` (sin gasto este mes) y ``new`` (sin histórico).

    Frente a la declaración de referencia, ya **no** hay chips de cabecera ni orden
    por estado: las filas siguen el orden de ``categories`` y el chip de estado
    vive dentro de la fila. La tabla incorpora además una columna de tendencia
    (el ``<canvas>`` de las minigráficas) que aquí se representa como cadena vacía.

    >>> import datetime as dt
    >>> txs = [
    ...   {"date": "2026-02-05", "categoryId": "c1", "amountUsd": 100, "amountBs": 0},
    ...   {"date": "2026-03-05", "categoryId": "c1", "amountUsd": 130, "amountBs": 0},
    ... ]
    >>> cats = [{"id": "c1", "name": "Comida", "color": "#111111"}]
    >>> view = budget_traffic_light(txs, cats, fiscal_year=2026,
    ...                             now=dt.datetime(2026, 3, 15, 12),
    ...                             ctx=MoneyContext("USD", 2, 40.0))
    >>> row = view["rows"][0]
    >>> row["name"], row["current"], row["delta"], row["chip"], row["trend"], row["months"]
    ('Comida', '$ 130.00', '+30.0%', 'Excede +30.0%', '', '1')
    >>> view["chips"]
    ['Excede +30.0%']
    >>> view["empty"] is None
    True
    """
    audit = resolve_active_audit_month(txs, fiscal_year=fiscal_year, now=now)
    current_key = audit.key

    by_month: dict[str, dict[str, dict[str, float]]] = {}
    for tx in txs:
        date_str = tx.get("date")
        category_id = tx.get("categoryId")
        if not date_str or not category_id:
            continue
        month_key = date_str[:7]
        by_month.setdefault(month_key, {}).setdefault(
            category_id, {"usd": 0.0, "bs": 0.0}
        )
        by_month[month_key][category_id]["usd"] += js_number_or_zero(
            tx.get("amountUsd")
        )
        by_month[month_key][category_id]["bs"] += js_number_or_zero(
            tx.get("amountBs")
        )

    past_keys = [key for key in by_month if key < current_key]

    rows: list[dict[str, Any]] = []
    for category in categories:
        category_id = category.get("id")
        current = by_month.get(current_key, {}).get(category_id) or {
            "usd": 0.0,
            "bs": 0.0,
        }
        current_usd = current["usd"]
        current_bs = current["bs"]

        past_usd = [
            data["usd"]
            for key in past_keys
            if (data := by_month.get(key, {}).get(category_id)) and data["usd"] > 0
        ]

        if not past_usd:
            rows.append(
                {
                    "cat": category,
                    "curUsd": current_usd,
                    "curBs": current_bs,
                    "avgUsd": 0.0,
                    "avgBs": 0.0,
                    "delta": 0.0,
                    "state": "new",
                    "months": 0,
                }
            )
            continue

        average_usd = sum(past_usd) / len(past_usd)
        total_bs = 0.0
        for key in past_keys:
            data = by_month.get(key, {}).get(category_id)
            if data:
                total_bs += data["bs"] or 0.0
        average_bs = total_bs / len(past_usd)

        delta = (
            ((current_usd - average_usd) / average_usd) * 100
            if average_usd > 0
            else 0.0
        )
        if current_usd == 0:
            state = "zero"
        elif delta > 5:
            state = "over"
        elif delta >= -5:
            state = "ok"
        else:
            state = "under"
        rows.append(
            {
                "cat": category,
                "curUsd": current_usd,
                "curBs": current_bs,
                "avgUsd": average_usd,
                "avgBs": average_bs,
                "delta": delta,
                "state": state,
                "months": len(past_usd),
            }
        )

    # ``chipMap`` de la versión de referencia: el rótulo del chip de estado de cada fila.
    chips = {
        "over": lambda delta: f"Excede +{js_to_fixed(delta, 1)}%",
        "ok": lambda delta: "En Ppto.",
        "under": lambda delta: f"Ahorro {js_to_fixed(delta, 1)}%",
        "zero": lambda delta: "Sin gasto",
        "new": lambda delta: "Nueva",
    }

    view_rows = []
    for row in rows:
        delta = row["delta"]
        months = row["months"]
        chip = chips[row["state"]](delta)
        view_rows.append(
            {
                "name": row["cat"].get("name") or "",
                "color": row["cat"].get("color") or NO_CATEGORY_COLOR,
                "current": fmt_money(row["curUsd"], row["curBs"], ctx),
                "average": (
                    fmt_money(row["avgUsd"], row["avgBs"], ctx) if months else "—"
                ),
                "delta": (
                    ("+" if delta >= 0 else "") + js_to_fixed(delta, 1) + "%"
                    if months
                    else "—"
                ),
                "state": row["state"],
                "chip": chip,
                # La columna «Tendencia 6m» solo contiene el <canvas> de las
                # minigráficas, así que su texto es la cadena vacía.
                "trend": "",
                "months": str(months) if months else "—",
            }
        )

    return {
        "empty": None,
        "chips": [row["chip"] for row in view_rows],
        "rows": view_rows,
    }


def pareto(
    txs: list[dict[str, Any]], categories: list[dict[str, Any]]
) -> dict[str, Any]:
    """Pareto 80/20 por categoría (``renderParetoChart``).

    >>> txs = [
    ...   {"categoryId": "c1", "amountUsd": 80},
    ...   {"categoryId": "c2", "amountUsd": 20},
    ... ]
    >>> view = pareto(txs, [{"id": "c1", "name": "A", "color": "#111111"},
    ...                      {"id": "c2", "name": "B", "color": "#222222"}])
    >>> view["values"], view["cumulative"]
    ([80.0, 20.0], [80.0, 100.0])
    >>> view["colors"]
    ['#111111c0', '#222222c0']
    """
    by_category: dict[str, dict[str, Any]] = {}
    for tx in txs:
        found = next(
            (c for c in categories if c.get("id") == tx.get("categoryId")), None
        )
        key = tx.get("categoryId") or "none"
        group = by_category.get(key)
        if group is None:
            group = {
                "name": (found or {}).get("name") or NO_CATEGORY,
                "color": (found or {}).get("color") or NO_CATEGORY_COLOR,
                "usd": 0.0,
            }
            by_category[key] = group
        group["usd"] += js_number_or_zero(tx.get("amountUsd"))

    series = [group for group in by_category.values() if group["usd"] > 0]
    if not series:
        return {"empty": True, "labels": [], "values": [], "cumulative": [], "colors": []}
    series.sort(key=lambda group: group["usd"], reverse=True)

    total = 0.0
    for group in series:
        total += group["usd"]
    cumulative: list[float] = []
    accumulated = 0.0
    for group in series:
        accumulated += group["usd"]
        cumulative.append((accumulated / total) * 100)

    return {
        "empty": False,
        "labels": [
            group["name"][:18] + "…" if len(group["name"]) > 18 else group["name"]
            for group in series
        ],
        "values": [group["usd"] for group in series],
        "cumulative": cumulative,
        "colors": [group["color"] + "c0" for group in series],
        "borders": [group["color"] for group in series],
    }


def sparklines(
    txs: list[dict[str, Any]],
    categories: list[dict[str, Any]],
    *,
    fiscal_year: Any,
    now: datetime,
    width: int,
    height: int,
    canvas_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Series mensuales de 6 meses por categoría (ajuste, línea 7708).

    La ventana de seis meses termina en el **mes auditado**, no en el mes del
    reloj. La geometría del ajuste deja 4 px de margen a los lados y 3 px abajo
    (``x = (i/(n-1))*(w-4)+2``, ``y = h-3-(v/mx)*(h-6)``) y ya **no** dibuja el
    punto final de la serie.

    >>> import datetime as dt
    >>> txs = [
    ...   {"date": "2026-02-05", "categoryId": "c1", "amountUsd": 5},
    ...   {"date": "2026-03-05", "categoryId": "c1", "amountUsd": 10},
    ... ]
    >>> view = sparklines(txs, [{"id": "c1", "color": "#111111"}],
    ...                   fiscal_year=2026, now=dt.datetime(2026, 3, 15, 12),
    ...                   width=6, height=8)
    >>> view["series"]["c1"]
    [0.0, 0.0, 0.0, 0.0, 5.0, 10.0]
    >>> view["points"]["c1"][-1]
    [4.0, 3.0]
    """
    audit = resolve_active_audit_month(txs, fiscal_year=fiscal_year, now=now)

    months: list[str] = []
    for offset in range(5, -1, -1):
        shifted = js_date(audit.year, audit.month - offset, 1)
        months.append(f"{shifted.year}-{shifted.month:02d}")

    by_month: dict[str, dict[str, float]] = {key: {} for key in months}
    for tx in txs:
        date_str = tx.get("date")
        category_id = tx.get("categoryId")
        if not date_str or not category_id:
            continue
        month_key = date_str[:7]
        if month_key not in by_month:
            continue
        by_month[month_key][category_id] = by_month[month_key].get(
            category_id, 0.0
        ) + js_number_or_zero(tx.get("amountUsd"))

    colors = {
        category.get("id"): category.get("color") or SPARK_COLOR
        for category in categories
    }

    series: dict[str, list[float]] = {}
    points: dict[str, list[list[float]]] = {}
    for category_id in canvas_ids if canvas_ids is not None else colors:
        values = [by_month[key].get(category_id, 0.0) for key in months]
        maximum = max(*values, 1)
        count = len(values)
        coordinates: list[list[float]] = []
        for index, value in enumerate(values):
            x = (index / (count - 1)) * (width - 4) + 2
            y = height - 3 - ((value / maximum) * (height - 6))
            coordinates.append([x, y])
        series[category_id] = values
        points[category_id] = coordinates

    if canvas_ids is not None:
        for category_id in canvas_ids:
            colors.setdefault(category_id, SPARK_COLOR)

    return {
        "months": months,
        "series": series,
        "points": points,
        "colors": colors,
    }


def outlier_scatter(
    txs: list[dict[str, Any]], categories: list[dict[str, Any]]
) -> dict[str, Any]:
    """Dispersión día/importe con marca de outlier (``renderOutlierScatter``).

    Un punto es outlier si supera ``media + 2·desviación típica``.

    >>> txs = [{"date": f"2026-03-0{i}", "amountUsd": 10, "productName": "A"}
    ...        for i in range(1, 8)]
    >>> txs.append({"date": "2026-03-09", "amountUsd": 100, "productName": "Z"})
    >>> view = outlier_scatter(txs, [])
    >>> view["points"][-1]["outlier"], view["points"][0]["outlier"]
    (True, False)
    """
    points: list[dict[str, Any]] = []
    for tx in txs:
        if js_number_or_zero(tx.get("amountUsd")) <= 0:
            continue
        found = next(
            (c for c in categories if c.get("id") == tx.get("categoryId")), None
        )
        date_str = tx.get("date") or ""
        day = int(date_str[8:10]) if date_str[8:10].isdigit() else 0
        points.append(
            {
                "x": day or 1,
                "y": js_number_or_zero(tx.get("amountUsd")),
                "categoryId": tx.get("categoryId") or "none",
                "catName": (found or {}).get("name") or NO_CATEGORY,
                "color": (found or {}).get("color") or NO_CATEGORY_COLOR,
                "label": tx.get("productName") or "—",
                "provider": tx.get("provider") or "",
                "date": date_str,
            }
        )

    if not points:
        return {"empty": True, "groups": [], "points": []}

    values = [point["y"] for point in points]
    average = mean(values)
    deviation = stdev(values)
    threshold = average + 2 * deviation
    for point in points:
        point["outlier"] = point["y"] > threshold
        point["tooltip"] = (
            f"{point['label']} · {point['date']} · ${js_to_fixed(point['y'], 2)}"
            f" · {point['provider']}{'  Outlier' if point['outlier'] else ''}"
        )

    groups: dict[str, dict[str, Any]] = {}
    for point in points:
        group = groups.get(point["categoryId"])
        if group is None:
            group = {
                "label": point["catName"],
                "color": point["color"] + "90",
                "border": point["color"],
                "data": [],
            }
            groups[point["categoryId"]] = group
        group["data"].append(point)

    return {
        "empty": False,
        "threshold": threshold,
        "points": points,
        "groups": [
            {
                "label": group["label"],
                "color": group["color"],
                "border": group["border"],
                "points": [point["x"] for point in group["data"]],
            }
            for group in groups.values()
        ],
    }


def hierarchical_tree(
    txs: list[dict[str, Any]],
    categories: list[dict[str, Any]],
    *,
    ctx: MoneyContext,
) -> dict[str, Any]:
    """Árbol categoría → subcategoría → producto (``renderHierarchicalTree``).

    >>> txs = [
    ...   {"categoryId": "c1", "subcategory": "Lácteos", "productId": "p1",
    ...    "productName": "Leche", "quantity": 2, "amountUsd": 10, "amountBs": 400},
    ...   {"categoryId": "c1", "subcategory": "Lácteos", "productId": "p1",
    ...    "productName": "Leche", "quantity": 1, "amountUsd": 5, "amountBs": 200},
    ... ]
    >>> view = hierarchical_tree(txs, [{"id": "c1", "name": "Comida", "color": "#111111"}],
    ...                          ctx=MoneyContext("USD", 2, 40.0))
    >>> [(node["level"], node["name"], node["qty"]) for node in view["nodes"]]
    [('cat', 'Comida', '3.00 unid.'), ('sub', 'Lácteos', '3.00 unid.')]
    >>> view["prods"][0]["pos"], view["prods"][0]["meta"]
    ('2×', '3.00 unidad · $ 15.00')
    """
    if not txs:
        return {"empty": "Sin transacciones en el período.", "nodes": [], "prods": []}

    tree: dict[str, dict[str, Any]] = {}
    for tx in txs:
        found = next(
            (c for c in categories if c.get("id") == tx.get("categoryId")), None
        )
        category_key = tx.get("categoryId") or "none"
        subcategory_key = (tx.get("subcategory") or NO_SUBCATEGORY).strip()
        product_key = tx.get("productId") or tx.get("productName") or "—"

        category = tree.get(category_key)
        if category is None:
            category = {
                "name": (found or {}).get("name") or NO_CATEGORY,
                "color": (found or {}).get("color") or NO_CATEGORY_COLOR,
                "subs": {},
            }
            tree[category_key] = category
        subcategory = category["subs"].get(subcategory_key)
        if subcategory is None:
            subcategory = {"prods": {}}
            category["subs"][subcategory_key] = subcategory
        product = subcategory["prods"].get(product_key)
        if product is None:
            product = {
                "name": tx.get("productName") or "—",
                "unit": tx.get("unit") or "unidad",
                "qty": 0.0,
                "usd": 0.0,
                "bs": 0.0,
                "count": 0,
            }
            subcategory["prods"][product_key] = product
        product["qty"] += js_number_or_zero(tx.get("quantity")) or 1
        product["usd"] += js_number_or_zero(tx.get("amountUsd"))
        product["bs"] += js_number_or_zero(tx.get("amountBs"))
        product["count"] += 1

    nodes: list[dict[str, Any]] = []
    prods: list[dict[str, Any]] = []
    for category in tree.values():
        category_usd = 0.0
        category_bs = 0.0
        category_qty = 0.0
        for subcategory in category["subs"].values():
            for product in subcategory["prods"].values():
                category_usd += product["usd"]
                category_bs += product["bs"]
                category_qty += product["qty"]
        nodes.append(
            {
                "level": "cat",
                "name": category["name"],
                "color": category["color"],
                "qty": js_to_fixed(category_qty, 2) + " unid.",
                "total": fmt_money(category_usd, category_bs, ctx),
            }
        )

        for subcategory_name, subcategory in category["subs"].items():
            subcategory_usd = 0.0
            subcategory_bs = 0.0
            subcategory_qty = 0.0
            for product in subcategory["prods"].values():
                subcategory_usd += product["usd"]
                subcategory_bs += product["bs"]
                subcategory_qty += product["qty"]
            nodes.append(
                {
                    "level": "sub",
                    "name": subcategory_name,
                    "qty": js_to_fixed(subcategory_qty, 2) + " unid.",
                    "total": fmt_money(subcategory_usd, subcategory_bs, ctx),
                }
            )
            for product_key, product in subcategory["prods"].items():
                prods.append(
                    {
                        "id": product_key,
                        "pos": f"{product['count']}×",
                        "name": product["name"],
                        "meta": (
                            f"{js_to_fixed(product['qty'], 2)} {product['unit']}"
                            f" · {fmt_money(product['usd'], product['bs'], ctx)}"
                        ),
                    }
                )

    return {"empty": None, "nodes": nodes, "prods": prods}
