"""Sub-pestaña B · Pivote multivariable (``runAnalysisB``, 5330-5410).

Agrupa las compras por comercio, marca, método de pago, plataforma de origen o
subcategoría y compara mínimo, máximo, media, mediana y dispersión del precio
unitario. Incluye el filtro «solo días con varios comercios».
"""

from __future__ import annotations

from typing import Any

from ..core.money import format_usd, js_number_or_zero
from ..core.stats import mean, median, stdev, unit_price

__all__ = ["pivot_view", "PIVOT_FIELDS"]

# ``type`` → campo de la transacción (5344-5349).
PIVOT_FIELDS = {
    "provider": "provider",
    "brand": "brand",
    "payment": "paymentMethod",
    "originPlatform": "originPlatform",
    "subcategory": "subcategory",
}

NO_VALUE = "— Sin especificar —"


def pivot_view(
    txs: list[dict[str, Any]],
    *,
    pivot_type: str = "provider",
    product_filter: str = "",
    same_day_only: bool = False,
    decimals: int = 2,
    chart_available: bool = True,
) -> dict[str, Any]:
    """Vista del pivote.

    >>> txs = [
    ...   {"provider": "A", "date": "2026-03-01", "quantity": 1, "amountUsd": 4},
    ...   {"provider": "A", "date": "2026-03-02", "quantity": 1, "amountUsd": 6},
    ...   {"provider": "B", "date": "2026-03-01", "quantity": 1, "amountUsd": 9},
    ... ]
    >>> view = pivot_view(txs)
    >>> [(row["key"], row["count"], row["totalUsd"]) for row in view["rows"]]
    [('A', '2', '$ 10.00'), ('B', '1', '$ 9.00')]
    >>> view["summary"]["cheapest"], view["summary"]["savings"]
    ('A', '$ 4.0000')
    """
    field = PIVOT_FIELDS.get(pivot_type, "provider")
    filtered = list(txs)
    if product_filter:
        filtered = [tx for tx in filtered if tx.get("productId") == product_filter]

    if same_day_only and pivot_type == "provider":
        providers_by_date: dict[str, set[str]] = {}
        for tx in filtered:
            date_str = tx.get("date") or ""
            providers_by_date.setdefault(date_str, set()).add(
                tx.get("provider") or "—"
            )
        valid_dates = {
            date_str
            for date_str, providers in providers_by_date.items()
            if len(providers) >= 2
        }
        filtered = [tx for tx in filtered if (tx.get("date") or "") in valid_dates]

    groups: dict[str, list[dict[str, Any]]] = {}
    for tx in filtered:
        key = str(tx.get(field) or NO_VALUE)
        groups.setdefault(key, []).append(tx)

    rows: list[dict[str, Any]] = []
    for key, purchases in groups.items():
        units = [unit_price(tx)["unitUsd"] for tx in purchases]
        total_usd = 0.0
        for tx in purchases:
            total_usd += js_number_or_zero(tx.get("amountUsd"))
        rows.append(
            {
                "key": key,
                "count": len(purchases),
                "totalUsd": total_usd,
                "minUsd": min(units),
                "maxUsd": max(units),
                "avgUsd": mean(units),
                "medUsd": median(units),
                "stdUsd": stdev(units),
            }
        )

    rows.sort(key=lambda row: row["totalUsd"], reverse=True)

    total_usd_all = 0.0
    for row in rows:
        total_usd_all += row["totalUsd"]

    if rows:
        cheapest = rows[0]
        for row in rows[1:]:
            if row["avgUsd"] < cheapest["avgUsd"]:
                cheapest = row
        most_expensive = rows[0]
        for row in rows[1:]:
            if row["avgUsd"] > most_expensive["avgUsd"]:
                most_expensive = row
        savings = (
            most_expensive["avgUsd"] - cheapest["avgUsd"] if len(rows) >= 2 else 0.0
        )
    else:
        cheapest = {"avgUsd": 0.0, "key": "—"}
        most_expensive = {"avgUsd": 0.0, "key": "—"}
        savings = 0.0

    view: dict[str, Any] = {
        "empty": None if rows else "Sin datos para pivote en el período.",
        "summary": {
            "groups": str(len(rows)),
            "total": format_usd(total_usd_all, decimals),
            "cheapest": cheapest["key"],
            "cheapestAvg": format_usd(cheapest["avgUsd"], 4),
            "savings": format_usd(savings, 4),
            "mostExpensive": most_expensive["key"],
        },
        "rows": [
            {
                "key": row["key"],
                "count": str(row["count"]),
                "totalUsd": format_usd(row["totalUsd"], decimals),
                "minUsd": format_usd(row["minUsd"], 4),
                "maxUsd": format_usd(row["maxUsd"], 4),
                "avgUsd": format_usd(row["avgUsd"], 4),
                "medUsd": format_usd(row["medUsd"], 4),
                "stdUsd": format_usd(row["stdUsd"], 4),
            }
            for row in rows
        ],
        "chart": {"labels": [], "min": [], "avg": [], "max": []},
    }

    if chart_available and rows:
        top10 = rows[:10]
        view["chart"] = {
            "labels": [
                row["key"][:20] + "…" if len(row["key"]) > 20 else row["key"]
                for row in top10
            ],
            "min": [row["minUsd"] for row in top10],
            "avg": [row["avgUsd"] for row in top10],
            "max": [row["maxUsd"] for row in top10],
        }

    return view
