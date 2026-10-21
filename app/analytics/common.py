"""Utilidades compartidas por las sub-pestañas de Análisis.

Implementación de ``getFilteredTx``, del agrupamiento por producto de
``runAnalysisA`` (5020-5023) y de ``buildHist`` (5025-5034).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..core.periods import date_to_iso
from ..core.stats import unit_price

__all__ = [
    "ProductHistory",
    "build_history",
    "by_product",
    "filtered_by_range",
    "series_from_history",
    "MS_PER_DAY",
]

MS_PER_DAY = 86_400_000


@dataclass(frozen=True)
class ProductHistory:
    """Una compra dentro del histórico de un producto.

    >>> h = ProductHistory(date="2026-03-01", unit=3.0, diff_abs=1.0, diff_pct=50.0,
    ...                    qty=2.0, unit_name="kg")
    >>> h.date, h.unit, h.diff_pct
    ('2026-03-01', 3.0, 50.0)
    """

    date: str
    unit: float
    diff_abs: float
    diff_pct: float
    qty: float
    unit_name: str
    provider: str = ""


def by_product(txs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Agrupa por ``productId`` (ignorando los vacíos) y ordena por fecha.

    El orden de inserción del diccionario se conserva: la versión de referencia lo usa para
    recorrer los productos y ese orden afecta a las sumas en coma flotante.

    >>> txs = [{"productId": "b", "date": "2026-03-02"},
    ...        {"productId": "a", "date": "2026-03-05"},
    ...        {"productId": "", "date": "2026-03-01"},
    ...        {"productId": "a", "date": "2026-03-01"}]
    >>> list(by_product(txs))
    ['b', 'a']
    >>> [t["date"] for t in by_product(txs)["a"]]
    ['2026-03-01', '2026-03-05']
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for tx in txs:
        product_id = tx.get("productId")
        if not product_id:
            continue
        grouped.setdefault(product_id, []).append(tx)
    for rows in grouped.values():
        rows.sort(key=lambda tx: tx.get("date") or "")
    return grouped


def build_history(
    purchases: list[dict[str, Any]], *, is_bs: bool = False
) -> list[ProductHistory]:
    """Precio unitario de cada compra y variación frente a la anterior.

    Referencia (5025-5034)::

        const up = unitPrice(t); const u = isBs ? up.unitBs : up.unitUsd;
        if (i > 0) { diffAbs = u - prev; diffPct = prev ? (diffAbs/prev)*100 : 0; }

    >>> compras = [
    ...   {"date": "2026-01-10", "quantity": 2, "amountUsd": 5, "amountBs": 200},
    ...   {"date": "2026-02-10", "quantity": 2, "amountUsd": 8, "amountBs": 320},
    ... ]
    >>> [round(h.unit, 2) for h in build_history(compras)]
    [2.5, 4.0]
    >>> [round(h.diff_pct, 2) for h in build_history(compras)]
    [0.0, 60.0]
    """
    history: list[ProductHistory] = []
    for index, tx in enumerate(purchases):
        price = unit_price(tx)
        value = price["unitBs"] if is_bs else price["unitUsd"]
        diff_abs = 0.0
        diff_pct = 0.0
        if index > 0:
            previous_price = unit_price(purchases[index - 1])
            previous = (
                previous_price["unitBs"] if is_bs else previous_price["unitUsd"]
            )
            diff_abs = value - previous
            diff_pct = (diff_abs / previous) * 100 if previous else 0.0
        history.append(
            ProductHistory(
                date=str(tx.get("date") or ""),
                unit=value,
                diff_abs=diff_abs,
                diff_pct=diff_pct,
                qty=price["qty"],
                unit_name=price["unit"],
                provider=str(tx.get("provider") or tx.get("brand") or ""),
            )
        )
    return history


def series_from_history(
    history: list[ProductHistory], sorted_dates: list[str]
) -> list[float | None]:
    """Rellena los huecos con el último precio conocido (``seriesFromHist``).

    Antes de la primera compra el valor es ``None`` (``null`` en la versión de referencia).

    >>> h = ProductHistory("2026-01-10", 2.5, 0, 0, 1, "unidad")
    >>> h2 = ProductHistory("2026-03-10", 3.5, 1, 40, 1, "unidad")
    >>> series_from_history([h, h2], ["2026-01-10", "2026-02-10", "2026-03-10"])
    [2.5, 2.5, 3.5]
    >>> series_from_history([h2], ["2026-01-10", "2026-03-10"])
    [None, 3.5]
    """
    by_date: dict[str, float] = {}
    for point in history:
        by_date[point.date] = point.unit
    series: list[float | None] = []
    last_known: float | None = None
    for date_str in sorted_dates:
        if date_str in by_date:
            last_known = by_date[date_str]
        series.append(last_known)
    return series


def filtered_by_range(
    txs: list[dict[str, Any]], start: Any, end: Any
) -> list[dict[str, Any]]:
    """``getFilteredTx``: fechas ISO entre ``start`` y ``end``, ambos incluidos.

    Compara cadenas ISO, igual que la versión de referencia (correcto para ``YYYY-MM-DD``).

    >>> txs = [{"date": "2026-03-01"}, {"date": "2026-03-31"}, {"date": "2026-04-01"}]
    >>> [t["date"] for t in filtered_by_range(txs, "2026-03-01", "2026-03-31")]
    ['2026-03-01', '2026-03-31']
    """
    start_iso = start if isinstance(start, str) else date_to_iso(start)
    end_iso = end if isinstance(end, str) else date_to_iso(end)
    return [
        tx
        for tx in txs
        if start_iso <= (tx.get("date") or "") <= end_iso
    ]
