"""Sub-pestaña A.2 · Lupa de variantes (``runAnalysisVariants``).

Porteo de la versión **efectiva** (parche maestro, línea 7935). Agrupa las
compras por unidad, subcategoría o marca y dibuja una burbuja por variante:
X = volumen comprado, Y = precio unitario medio, radio = inversión.

Frente a la declaración de la línea 5199, la "óptima" deja de ser la variante
más eficiente (precio por unidad de volumen) y pasa a ser **la más económica**
(la primera al ordenar por ``unitUsd``), y la inversión se formatea con
``fmtMoney`` (USD y Bs) en vez de solo USD.
"""

from __future__ import annotations

from typing import Any

from ..core.money import (
    MoneyContext,
    fmt_money,
    format_usd,
    js_number_or_zero,
    js_to_fixed,
)
from .common import group_key

__all__ = ["variants_view"]

NO_CATEGORY_COLOR = "#6B7280"
BEST_COLOR = "#10B981"


def _group_key(
    tx: dict[str, Any],
    group_by: str,
    category_names: dict[str, str] | None = None,
) -> str:
    """Clave de agrupación.

    >>> tx = {"unit": " kg ", "subcategory": "", "brand": ""}
    >>> _group_key(tx, "unit")
    'kg'
    >>> _group_key(tx, "subcategory")
    '— Sin subcat. —'
    >>> _group_key(tx, "brand")
    '— Sin marca —'
    """
    return group_key(tx, group_by, category_names)


def variants_view(
    txs: list[dict[str, Any]],
    categories: list[dict[str, Any]],
    *,
    group_by: str = "unit",
    product_filter: str = "",
    ctx: MoneyContext | None = None,
    chart_available: bool = True,
) -> dict[str, Any]:
    """Vista de la lupa de variantes.

    >>> ctx = MoneyContext("USD", 2, 40.0)
    >>> txs = [
    ...   {"unit": "kg", "quantity": 2, "amountUsd": 10, "amountBs": 400, "categoryId": "c1"},
    ...   {"unit": "kg", "quantity": 3, "amountUsd": 12, "amountBs": 480, "categoryId": "c1"},
    ...   {"unit": "litro", "quantity": 1, "amountUsd": 9, "amountBs": 360, "categoryId": "c1"},
    ... ]
    >>> view = variants_view(txs, [{"id": "c1", "color": "#111111"}], ctx=ctx)
    >>> [(row["key"], row["qty"], row["usd"], row["pct"]) for row in view["rows"]]
    [('kg', '5.00', '$ 22.00', '71.0%'), ('litro', '1.00', '$ 9.00', '29.0%')]
    >>> view["chips"]["bestKey"], view["chips"]["bestUnit"]
    ('kg', '$ 4.4000')

    La "óptima" es ahora la **más económica** (``arr[0]`` al ordenar por
    ``unitUsd``), no la de mejor precio por unidad de volumen.
    """
    if not chart_available:
        return {"empty": None, "chips": {}, "rows": [], "points": []}

    category_names = {
        category.get("id"): category.get("name") or ""
        for category in categories
    }
    filtered = [tx for tx in txs if js_number_or_zero(tx.get("amountUsd")) > 0]
    if product_filter:
        filtered = [tx for tx in filtered if tx.get("productId") == product_filter]

    groups: dict[str, dict[str, Any]] = {}
    for tx in filtered:
        key = _group_key(tx, group_by, category_names)
        # ``if (!groups[key])``: una clave vacía se considera *siempre* ausente y
        # el grupo se recrea (el original pierde las compras anteriores).
        group = groups.get(key) if key else None
        if group is None:
            group = {
                "key": key,
                "cat": tx.get("categoryId") or "none",
                "qty": 0.0,
                "usd": 0.0,
                "bs": 0.0,
                "count": 0,
            }
            groups[key] = group
        group["qty"] += js_number_or_zero(tx.get("quantity")) or 1
        group["usd"] += js_number_or_zero(tx.get("amountUsd"))
        group["bs"] += js_number_or_zero(tx.get("amountBs"))
        group["count"] += 1

    colors = {
        category.get("id"): category.get("color") or NO_CATEGORY_COLOR
        for category in categories
    }

    rows: list[dict[str, Any]] = []
    for group in groups.values():
        unit_usd = group["usd"] / group["qty"] if group["qty"] > 0 else 0.0
        rows.append(
            {
                "key": group["key"],
                "qty": group["qty"],
                "usd": group["usd"],
                "bs": group["bs"],
                "count": group["count"],
                "unitUsd": unit_usd,
                "color": colors.get(group["cat"], NO_CATEGORY_COLOR),
            }
        )

    rows = [row for row in rows if row["unitUsd"] > 0]
    # El parche ordena por ``unitUsd`` ascendente sin tocar el orden de inserción.
    rows.sort(key=lambda row: row["unitUsd"])

    if not rows:
        return {
            "empty": "Sin datos para construir variantes.",
            "chips": {},
            "rows": [],
            "points": [],
        }

    best_key = rows[0]["key"]
    max_usd = max(row["usd"] for row in rows)

    points = []
    for row in rows:
        highlight = row["key"] == best_key
        ratio = (row["usd"] / max_usd) * 34 * 34 / 3.141592653589793
        radius = max(6.0, min(34.0, ratio**0.5 * 3.141592653589793))
        points.append(
            {
                "x": row["qty"],
                "y": row["unitUsd"],
                "r": radius,
                "catColor": row["color"],
                "highlight": highlight,
                "color": row["color"] + ("e0" if highlight else "90"),
                "border": BEST_COLOR if highlight else row["color"],
                "width": 3 if highlight else 1,
            }
        )

    total_usd = 0.0
    for row in rows:
        total_usd += row["usd"]

    money_ctx = ctx or MoneyContext("USD", 2, None)
    best = rows[0]

    return {
        "empty": None,
        "chips": {
            "variants": len(rows),
            "bestKey": best_key or "—",
            "bestUnit": format_usd(best["unitUsd"], 4),
        },
        "rows": [
            {
                "key": row["key"],
                "count": str(row["count"]),
                "qty": js_to_fixed(row["qty"], 2),
                "usd": fmt_money(row["usd"], row["bs"], money_ctx),
                "unitUsd": format_usd(row["unitUsd"], 4),
                "pct": (
                    js_to_fixed((row["usd"] / total_usd) * 100, 1) + "%"
                    if total_usd
                    else "0%"
                ),
                "best": row["key"] == best_key,
            }
            for row in rows
        ],
        "points": points,
    }
