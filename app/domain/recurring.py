"""Compromisos recurrentes que toca reponer.

Implementación de la versión **efectiva** de ``renderRecurringCommitments`` (ajuste
maestro, línea 7638). Cambia bastante respecto de la declaración de la 3259:

- El agrupador es ``t.productId || t.productName``: los productos sin SKU también
  se agrupan (por nombre).
- Bastan **2** compras recurrentes (antes 3).
- El filtro ya no es "no lo he comprado este mes", sino "no falta demasiado":
  se descarta solo si la próxima compra esperada cae a **más de 35 días** y
  además después del cierre del mes auditado.
- El nombre mostrado es el de la **última** compra (no la primera).

Dos detalles heredados: el intervalo se mide entre medianoches **locales** y la
fecha esperada se obtiene sumando ``Math.round(intervalo)`` días completos
(``Math.round`` de JavaScript, no el redondeo bancario de Python).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..core.money import MoneyContext, fmt_money, js_number_or_zero, js_round
from ..core.periods import date_to_iso
from ..core.stats import mean
from .dates import MS_PER_DAY, local_date_at, local_midnight_ms, resolve_active_audit_month

__all__ = [
    "RecurringCommitment",
    "find_recurring_commitments",
    "recurring_chip",
    "recurring_view",
]

# Mínimo de compras recurrentes del mismo grupo (``rec.length < 2``).
MIN_RECURRENCES = 2

# ``(nextD - nowD)/86400000 > 35``.
FAR_FUTURE_DAYS = 35


@dataclass(frozen=True)
class RecurringCommitment:
    """Un compromiso recurrente que está por vencer.

    >>> c = RecurringCommitment("p1", "Netflix", "2026-03-20", 10.0, 400.0, 30, False, "2026-02-18")
    >>> c.overdue, c.avg_interval
    (False, 30)
    """

    product_id: str
    name: str
    projected_date: str
    expected_usd: float
    expected_bs: float
    avg_interval: int
    overdue: bool
    last_date: str


def _group_key(tx: dict[str, Any]) -> str:
    """``t.productId || t.productName`` (cadena vacía si no hay ninguno)."""
    product_id = tx.get("productId")
    if product_id:
        return str(product_id)
    name = tx.get("productName")
    return str(name) if name else ""


def find_recurring_commitments(
    txs: list[dict[str, Any]], *, fiscal_year: Any, now: datetime
) -> list[RecurringCommitment]:
    """Compromisos por vencer, ordenados por fecha esperada.

    >>> import datetime as dt
    >>> base = {"productId": "p1", "productName": "Netflix", "nature": "Recurrente",
    ...         "amountUsd": 10, "amountBs": 400}
    >>> txs = [{**base, "date": "2026-01-05"}, {**base, "date": "2026-02-04"}]
    >>> pend = find_recurring_commitments(txs, fiscal_year=2026, now=dt.datetime(2026, 3, 10, 12))
    >>> [(p.name, p.projected_date, p.avg_interval, p.overdue) for p in pend]
    [('Netflix', '2026-03-06', 30, True)]

    Con **dos** compras ya se considera recurrente (la versión de referencia exigía
    tres). El nombre y la fecha las toma de la última compra:

    >>> txs2 = [{**base, "date": "2026-01-05"}, {**base, "productName": "Netflix Plus",
    ...         "date": "2026-02-04"}]
    >>> find_recurring_commitments(txs2, fiscal_year=2026, now=dt.datetime(2026, 3, 10, 12))[0].name
    'Netflix Plus'

    Un compromiso que aún queda a más de 35 días **y** después del mes auditado
    no aparece:

    >>> txs3 = [{**base, "date": "2026-01-05"}, {**base, "date": "2026-02-04"}]
    >>> find_recurring_commitments(txs3, fiscal_year=2026, now=dt.datetime(2026, 3, 10, 12))
    [RecurringCommitment(product_id='p1', name='Netflix', projected_date='2026-03-06', expected_usd=10.0, expected_bs=400.0, avg_interval=30, overdue=True, last_date='2026-02-04')]
    """
    audit = resolve_active_audit_month(txs, fiscal_year=fiscal_year, now=now)
    reference_end_ms = int(
        datetime(
            int(audit.year), audit.month + 1, audit.last_day, 23, 59, 59
        ).timestamp()
        * 1000
    )
    now_ms = int(now.timestamp() * 1000)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for tx in txs:
        key = _group_key(tx)
        if key:
            grouped.setdefault(key, []).append(tx)

    pending: list[RecurringCommitment] = []

    for pid, group in grouped.items():
        recurrent = [tx for tx in group if tx.get("nature") == "Recurrente"]
        recurrent.sort(key=lambda tx: tx.get("date") or "")
        if len(recurrent) < MIN_RECURRENCES:
            continue

        total_days = 0.0
        for index in range(1, len(recurrent)):
            previous = local_midnight_ms(recurrent[index - 1].get("date"))
            current = local_midnight_ms(recurrent[index].get("date"))
            if previous is None or current is None:
                total_days = float("nan")
                break
            total_days += (current - previous) / MS_PER_DAY

        avg_interval = total_days / (len(recurrent) - 1)
        if not avg_interval or avg_interval != avg_interval or avg_interval < 1:
            continue
        if avg_interval in (float("inf"), float("-inf")):
            continue

        last_date = recurrent[-1].get("date")
        last_ms = local_midnight_ms(last_date)
        if last_ms is None:
            continue
        next_ms = last_ms + js_round(avg_interval, 0) * MS_PER_DAY

        if (next_ms - now_ms) / MS_PER_DAY > FAR_FUTURE_DAYS and next_ms > reference_end_ms:
            continue

        pending.append(
            RecurringCommitment(
                product_id=pid,
                name=recurrent[-1].get("productName") or pid,
                projected_date=date_to_iso(local_date_at(next_ms)),
                expected_usd=mean(
                    [js_number_or_zero(tx.get("amountUsd")) for tx in recurrent]
                ),
                expected_bs=mean(
                    [js_number_or_zero(tx.get("amountBs")) for tx in recurrent]
                ),
                avg_interval=int(js_round(avg_interval, 0)),
                overdue=next_ms <= now_ms,
                last_date=last_date,
            )
        )

    pending.sort(key=lambda item: item.projected_date)
    return pending


def recurring_chip(commitments: list[RecurringCommitment]) -> tuple[str, str]:
    """Texto y clase del chip de compromisos detectados.

    >>> recurring_chip([])
    ('0 detectados', 'chip ok')
    >>> c = RecurringCommitment("p", "X", "2026-03-20", 1.0, 1.0, 30, False, "2026-02-18")
    >>> recurring_chip([c])
    ('1 detectado', 'chip warn')
    >>> vencido = RecurringCommitment("p", "X", "2026-03-20", 1.0, 1.0, 30, True, "2026-02-18")
    >>> recurring_chip([vencido])
    ('1 detectado', 'chip bad')
    """
    count = len(commitments)
    plural = "" if count == 1 else "s"
    text = f"{count} detectado{plural}"

    if count == 0:
        level = "ok"
    elif any(item.overdue for item in commitments):
        level = "bad"
    else:
        level = "warn"
    return text, f"chip {level}"


def recurring_view(
    commitments: list[RecurringCommitment], ctx: MoneyContext
) -> dict[str, str]:
    """Lo que la versión de referencia escribe fuera de la lista: chip y total comprometido.

    >>> ctx = MoneyContext("USD", 2, 40.0)
    >>> c = RecurringCommitment("p", "X", "2026-03-20", 10.0, 400.0, 30, False, "2026-02-18")
    >>> view = recurring_view([c], ctx)
    >>> view["recurringChip"], view["recurringChipClass"], view["recurringCommitted"]
    ('1 detectado', 'chip warn', '$ 10.00')
    >>> recurring_view([], ctx)["recurringCommitted"]
    '—'
    """
    chip_text, chip_class = recurring_chip(commitments)

    committed_usd = 0.0
    committed_bs = 0.0
    for item in commitments:
        committed_usd += item.expected_usd
        committed_bs += item.expected_bs

    return {
        "recurringChip": chip_text,
        "recurringChipClass": chip_class,
        "recurringCommitted": (
            fmt_money(committed_usd, committed_bs, ctx) if commitments else "—"
        ),
    }
