"""Cierre anual: qué transacciones se retiran al archivar.

Implementación de la parte con lógica del ajuste de ``runCloseWizard``.

La versión de referencia añade al asistente de cierre una casilla —«Limpiar transacciones de
<AÑO> tras archivar el Acta»— que, al confirmar, borra las compras del año
fiscal del entorno activo. El catálogo de SKU, las categorías y los cierres se
conservan: solo se vacían las transacciones.

El acta en sí se construye en :mod:`app.exports.acta`.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from ..core.ids import now_ms as _now_ms
from ..core.ids import uid
from ..core.money import js_number_or_zero, js_round
from ..core.stats import cagr, mean, unit_price

__all__ = [
    "INDEX_WORKSPACE_YEAR",
    "build_closure_snapshot",
    "count_by_year",
    "year_transactions",
]

#: Consulta de la versión de referencia: ``queryByIndex(transactions, 'workspace_year', [ws, yr])``.
INDEX_WORKSPACE_YEAR = "workspace_year"


def year_transactions(
    transactions: list[dict[str, Any]], *, workspace: str, year: Any
) -> list[dict[str, Any]]:
    """Compras del año fiscal del entorno (las que el cierre borraría).

    >>> txs = [
    ...   {"id": 1, "workspace": "personal", "year": 2026},
    ...   {"id": 2, "workspace": "trabajo", "year": 2026},
    ...   {"id": 3, "workspace": "personal", "year": 2025},
    ... ]
    >>> [tx["id"] for tx in year_transactions(txs, workspace="personal", year=2026)]
    [1]
    >>> year_transactions(txs, workspace="personal", year=2027)
    []
    """
    return [
        tx
        for tx in transactions
        if tx.get("workspace") == workspace and tx.get("year") == year
    ]


def count_by_year(
    transactions: list[dict[str, Any]], *, workspace: str
) -> dict[Any, int]:
    """Cuántas compras hay por año en un entorno (para la vista previa del cierre).

    >>> txs = [
    ...   {"workspace": "personal", "year": 2025},
    ...   {"workspace": "personal", "year": 2026},
    ...   {"workspace": "personal", "year": 2026},
    ...   {"workspace": "trabajo", "year": 2026},
    ... ]
    >>> count_by_year(txs, workspace="personal")
    {2025: 1, 2026: 2}
    """
    counts: dict[Any, int] = {}
    for tx in transactions:
        if tx.get("workspace") != workspace:
            continue
        year = tx.get("year")
        counts[year] = counts.get(year, 0) + 1
    return counts


def _days_utc(start: Any, end: Any) -> float:
    """``(new Date(end) - new Date(start)) / 86400000`` para fechas ``YYYY-MM-DD``.

    ``new Date('2026-01-01')`` se interpreta como medianoche **UTC**, así que la
    diferencia es exacta.
    """
    from datetime import datetime, timezone

    def parse(value: Any) -> datetime:
        text = str(value)
        try:
            return datetime.fromisoformat(text[:10]).replace(tzinfo=timezone.utc)
        except ValueError:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)

    return (parse(end) - parse(start)).total_seconds() * 1000 / 86_400_000


def build_closure_snapshot(
    transactions: list[dict[str, Any]],
    *,
    workspace: str,
    year: Any,
    categories: list[dict[str, Any]],
    rates: list[dict[str, Any]],
    timestamp: int | None = None,
    id_factory: Callable[[str], str] | None = None,
) -> dict[str, Any] | None:
    """Snapshot del ejercicio tal como lo arma ``runCloseWizard``.

    Devuelve ``None`` si el año no tiene compras: la versión de referencia avisa y no abre el
    asistente. Las sumas son **secuenciales** (``reduce``), se conserva el orden
    de aparición de las categorías y el producto y las fechas se comparan en UTC,
    igual que la versión de referencia.

    >>> cats = [{"id": "c1", "name": "Comida", "color": "#111111"}]
    >>> txs = [
    ...   {"workspace": "personal", "year": 2026, "date": "2026-01-10",
    ...    "categoryId": "c1", "productId": "p1", "quantity": 2,
    ...    "amountUsd": 10, "amountBs": 400, "ivaMonto": 55.17, "baseImponible": 344.83},
    ...   {"workspace": "personal", "year": 2026, "date": "2026-06-10",
    ...    "categoryId": "c1", "productId": "p1", "quantity": 2,
    ...    "amountUsd": 20, "amountBs": 800, "ivaMonto": 110.34, "baseImponible": 689.66},
    ... ]
    >>> rates = [{"date": "2026-01-01", "value": 40}, {"date": "2026-06-01", "value": 44}]
    >>> snap = build_closure_snapshot(txs, workspace="personal", year=2026,
    ...     categories=cats, rates=rates, timestamp=1, id_factory=lambda p: "closure-1")
    >>> snap["id"], snap["year"], snap["txCount"]
    ('closure-1', 2026, 2)
    >>> snap["totalBs"], snap["totalUsd"], snap["ivaTotal"], snap["baseTotal"]
    (1200.0, 30.0, 165.51, 1034.49)
    >>> snap["topCategories"][0]["name"], snap["topCategories"][0]["count"]
    ('Comida', 2)
    >>> snap["rateStart"], snap["rateEnd"], snap["rateDelta"]
    (40, 44, 10.0)
    >>> build_closure_snapshot([], workspace="personal", year=2026,
    ...     categories=cats, rates=[]) is None
    True
    """
    year_txs = year_transactions(transactions, workspace=workspace, year=year)
    if not year_txs:
        return None

    total_bs = 0.0
    total_usd = 0.0
    iva_total = 0.0
    base_total = 0.0
    for tx in year_txs:
        total_bs += js_number_or_zero(tx.get("amountBs"))
        total_usd += js_number_or_zero(tx.get("amountUsd"))
        iva_total += js_number_or_zero(tx.get("ivaMonto"))
        base_total += js_number_or_zero(tx.get("baseImponible"))

    by_cat: dict[str, dict[str, float]] = {}
    for tx in year_txs:
        key = tx.get("categoryId") or "none"
        group = by_cat.setdefault(key, {"total": 0.0, "count": 0})
        group["total"] += js_number_or_zero(tx.get("amountUsd"))
        group["count"] += 1

    top_cats = []
    for key, group in sorted(by_cat.items(), key=lambda item: -item[1]["total"])[:5]:
        category = next((c for c in categories if c.get("id") == key), None)
        top_cats.append(
            {
                "name": (category or {}).get("name") or "Sin categoría",
                "color": (category or {}).get("color") or "#6B7280",
                "total": group["total"],
                "count": group["count"],
            }
        )

    top_expenses = [
        {
            "productName": tx.get("productName"),
            "date": tx.get("date"),
            "amountBs": tx.get("amountBs"),
            "amountUsd": tx.get("amountUsd"),
        }
        for tx in sorted(year_txs, key=lambda tx: -js_number_or_zero(tx.get("amountUsd")))[:5]
    ]

    year_rates = sorted(
        [rate for rate in rates if str(rate.get("date") or "").startswith(str(year))],
        key=lambda rate: str(rate.get("date") or ""),
    )
    rate_start = year_rates[0] if year_rates else None
    rate_end = year_rates[-1] if year_rates else None
    rate_delta = 0.0
    if rate_start and rate_end:
        start_value = js_number_or_zero(rate_start.get("value"))
        rate_delta = (
            (js_number_or_zero(rate_end.get("value")) - start_value) / start_value * 100
            if start_value
            else 0.0
        )

    by_product: dict[str, list[dict[str, Any]]] = {}
    for tx in year_txs:
        if tx.get("productId"):
            by_product.setdefault(tx["productId"], []).append(tx)

    inflation: list[float] = []
    for purchases in by_product.values():
        if len(purchases) < 2:
            continue
        ordered = sorted(purchases, key=lambda tx: str(tx.get("date") or ""))
        first = unit_price(ordered[0])["unitUsd"]
        last = unit_price(ordered[-1])["unitUsd"]
        days = _days_utc(ordered[0].get("date"), ordered[-1].get("date"))
        value = cagr(first, last, days)
        if not math.isnan(value) and math.isfinite(value) and value != 0:
            inflation.append(value)

    stamp = timestamp if timestamp is not None else _now_ms()
    make_id = id_factory or uid
    return {
        "id": make_id("closure"),
        "workspace": workspace,
        "year": year,
        "closedAt": stamp,
        "totalBs": js_round(total_bs, 2),
        "totalUsd": js_round(total_usd, 4),
        "ivaTotal": js_round(iva_total, 2),
        "baseTotal": js_round(base_total, 2),
        "txCount": len(year_txs),
        "topCategories": top_cats,
        "topExpenses": top_expenses,
        "rateStart": rate_start.get("value") if rate_start else None,
        "rateEnd": rate_end.get("value") if rate_end else None,
        "rateStartDate": rate_start.get("date") if rate_start else None,
        "rateEndDate": rate_end.get("date") if rate_end else None,
        "rateDelta": js_round(rate_delta, 2),
        "inflationAvg": js_round(mean(inflation) if inflation else 0, 2),
        "notes": "",
    }
