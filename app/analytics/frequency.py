"""Sub-pestaña C · Frecuencia de compra (``runAnalysisC``, 5415-5485).

Intervalo medio entre compras por producto, categoría, comercio, marca,
subcategoría, unidad, forma de pago o plataforma, y fecha de la próxima compra
estimada.

Ojo con la fecha estimada: el original parte de ``new Date('YYYY-MM-DD')``
(medianoche **UTC**), suma los días y la vuelve a texto con ``dateToISO``
(getters **locales**). En un huso negativo eso devuelve el día anterior; se
replica porque la tabla muestra ese valor.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..core.money import format_usd, js_number_or_zero, js_to_fixed
from ..core.periods import date_to_iso
from ..core.stats import mean
from ..domain.dates import local_date_at, utc_midnight_ms
from .common import group_key

__all__ = ["frequency_view"]

MS_PER_DAY = 86_400_000


def _interval_days(previous: str, current: str) -> float:
    """Días entre dos fechas ISO (medianoche UTC, como el original)."""
    start = utc_midnight_ms(previous)
    end = utc_midnight_ms(current)
    if start is None or end is None:
        return 0.0
    return (end - start) / MS_PER_DAY


def next_date_iso(last_date: str, average_interval: float) -> str | None:
    """``dateToISO(new Date(last) + intervalo)``.

    >>> next_date_iso("2026-03-06", 30)
    '2026-04-04'

    El día anterior al esperado es consecuencia del huso local (UTC−4): la
    medianoche UTC del 5 de abril es, en local, el 4 a las 20:00.
    """
    start = utc_midnight_ms(last_date)
    if start is None or not average_interval:
        return None
    return date_to_iso(local_date_at(start + average_interval * MS_PER_DAY))


def frequency_view(
    txs: list[dict[str, Any]],
    categories: list[dict[str, Any]] | None = None,
    *,
    group_by: str = "provider",
    order_by: str = "total",
    decimals: int = 2,
    now: datetime | None = None,
    chart_available: bool = True,
) -> dict[str, Any]:
    """Vista de la tabla de frecuencia.

    >>> txs = [
    ...   {"provider": "A", "date": "2026-03-01", "quantity": 2, "amountUsd": 4},
    ...   {"provider": "A", "date": "2026-03-11", "quantity": 1, "amountUsd": 6},
    ... ]
    >>> view = frequency_view(txs)
    >>> row = view["rows"][0]
    >>> row["key"], row["count"], row["interval"], row["avgQty"], row["next"]
    ('A', '2', '10.0 días', '1.50', '2026-03-20')
    """
    category_names = {
        category.get("id"): category.get("name") or "—"
        for category in (categories or [])
    }

    groups: dict[str, list[dict[str, Any]]] = {}
    for tx in txs:
        key = group_key(
            tx,
            group_by,
            category_names,
            defaults={
                "product": "—",
                "category": "—",
                "provider": "— Sin especificar —",
            },
        )
        groups.setdefault(key, []).append(tx)

    rows: list[dict[str, Any]] = []
    for key, purchases in groups.items():
        purchases.sort(key=lambda tx: tx.get("date") or "")
        count = len(purchases)
        average_interval = 0.0
        if count >= 2:
            total_days = 0.0
            for index in range(1, count):
                total_days += _interval_days(
                    purchases[index - 1].get("date") or "",
                    purchases[index].get("date") or "",
                )
            average_interval = total_days / (count - 1)

        last_date = purchases[-1].get("date") or ""
        next_date = next_date_iso(last_date, average_interval)

        quantities = [js_number_or_zero(tx.get("quantity")) or 1 for tx in purchases]
        tickets = [js_number_or_zero(tx.get("amountUsd")) for tx in purchases]
        total_usd = 0.0
        for value in tickets:
            total_usd += value

        rows.append(
            {
                "key": key,
                "count": count,
                "avgInterval": average_interval,
                "lastDate": last_date,
                "nextDate": next_date,
                "avgQty": mean(quantities),
                "avgTicket": mean(tickets),
                "totalUsd": total_usd,
            }
        )

    if order_by == "count":
        rows.sort(key=lambda row: row["count"], reverse=True)
    elif order_by == "interval":
        rows.sort(key=lambda row: row["avgInterval"] or 9999)
    else:
        rows.sort(key=lambda row: row["totalUsd"], reverse=True)

    context = now or datetime.now()
    now_ms = context.timestamp() * 1000
    has_interval = any(row["avgInterval"] > 0 for row in rows)

    view_rows = []
    for row in rows:
        soon = False
        if row["nextDate"]:
            next_ms = utc_midnight_ms(row["nextDate"])
            # ``new Date(r.nextDate) - new Date()``: el original compara la
            # medianoche UTC con el instante actual.
            delta = (next_ms if next_ms is not None else 0) - now_ms
            soon = delta < 7 * MS_PER_DAY and delta > -14 * MS_PER_DAY
        if row["avgInterval"]:
            interval = js_to_fixed(row["avgInterval"], 1) + " días"
        elif row["count"] >= 2:
            interval = "Mismo día"
        else:
            interval = "—"
        view_rows.append(
            {
                "key": row["key"],
                "count": str(row["count"]),
                "interval": interval,
                "avgQty": js_to_fixed(row["avgQty"], 2),
                "avgTicket": format_usd(row["avgTicket"], decimals),
                "totalUsd": format_usd(row["totalUsd"], decimals),
                "lastDate": row["lastDate"],
                "next": row["nextDate"] or "—",
                "soon": soon,
            }
        )

    view: dict[str, Any] = {
        "empty": None if rows else "Sin datos.",
        "rows": view_rows,
        "notice": (
            "Ningún grupo tiene compras en fechas distintas. El intervalo y la "
            "próxima compra aparecen cuando hay al menos dos fechas por grupo."
            if rows and not has_interval
            else None
        ),
        "chart": {"labels": [], "counts": []},
    }

    if chart_available and rows:
        top = rows[:12]
        view["chart"] = {
            "labels": [
                row["key"][:18] + "…" if len(row["key"]) > 18 else row["key"]
                for row in top
            ],
            "counts": [row["count"] for row in top],
        }

    return view
