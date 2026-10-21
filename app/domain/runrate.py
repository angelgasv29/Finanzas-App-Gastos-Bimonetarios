"""Run-rate: proyección de cierre del mes **auditado**.

Implementación de la versión **efectiva** de ``renderRunRate`` (capa de compatibilidad, línea
7573). La versión que finalmente ejecuta la aplicación no es la declarada en la
línea 3166: el ajuste la reasigna y, en JavaScript, la asignación gana. La
diferencia es de fondo:

- El mes analizado no es el del reloj, sino el que decide
  :func:`~app.domain.dates.resolve_active_audit_month` (puede ser un mes pasado
  cuando el año fiscal ha quedado cerrado).
- El "día de corte" es el de hoy solo si el mes auditado es el mes en curso; si
  no, es el último día con movimientos.

El filtro por mes es ``t.date.slice(0, 7) === mKey`` (texto), no un constructor
de fecha, así que no depende del huso horario.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..core.money import MoneyContext, fmt_money, js_number_or_zero, js_to_fixed
from .dates import AuditMonth, day_of_month, resolve_active_audit_month

__all__ = [
    "RunRate",
    "compute_run_rate",
    "run_rate_view",
    "month_key_of",
    "transactions_of_month",
]


def month_key_of(value: Any) -> str:
    """``(t.date || '').slice(0, 7)``.

    >>> month_key_of("2026-03-15"), month_key_of(None)
    ('2026-03', '')
    """
    return str(value or "")[:7]


def transactions_of_month(
    txs: list[dict[str, Any]], key: str
) -> list[dict[str, Any]]:
    """``all.filter(t => t.date && t.date.slice(0,7) === key)``.

    >>> txs = [{"date": "2026-03-01"}, {"date": "2026-03-31"}, {"date": "2026-04-01"}]
    >>> len(transactions_of_month(txs, "2026-03"))
    2
    """
    return [tx for tx in txs if tx.get("date") and month_key_of(tx["date"]) == key]


def _sum(values: list[float]) -> float:
    """Suma secuencial: mismo orden (y mismo error) que el ``reduce`` de la versión de referencia."""
    total = 0.0
    for value in values:
        total += value
    return total


@dataclass(frozen=True)
class RunRate:
    """Números del run-rate del mes auditado.

    >>> rr = RunRate(AuditMonth(2026, 2, True), "2026-03", 31, 20, 15, 300.0, 12000.0, 2)
    >>> rr.projected_usd
    620.0
    >>> rr.day_progress
    48.38709677419355
    """

    audit: AuditMonth
    month_key: str
    days_in_month: int
    max_day: int
    current_day: int
    accumulated_usd: float
    accumulated_bs: float
    count: int

    @property
    def projected_usd(self) -> float:
        """``(accUsd / curD) * daysInM``."""
        return (self.accumulated_usd / self.current_day) * self.days_in_month

    @property
    def projected_bs(self) -> float:
        return (self.accumulated_bs / self.current_day) * self.days_in_month

    @property
    def day_progress(self) -> float:
        """``(curD / daysInM) * 100`` (el ancho de la barra de corte)."""
        return (self.current_day / self.days_in_month) * 100

    @property
    def daily_usd(self) -> float:
        return self.accumulated_usd / self.current_day

    @property
    def daily_bs(self) -> float:
        return self.accumulated_bs / self.current_day

    @property
    def has_data(self) -> bool:
        """``mTxs.length !== 0``.

        >>> RunRate(AuditMonth(2026, 2, True), "2026-03", 31, 1, 31, 0.0, 0.0, 0).has_data
        False
        """
        return self.count != 0


def compute_run_rate(
    txs: list[dict[str, Any]], *, fiscal_year: Any, now: datetime
) -> RunRate:
    """Run-rate del mes auditado.

    >>> import datetime as dt
    >>> txs = [{"date": "2026-03-01", "amountUsd": 100, "amountBs": 4000},
    ...        {"date": "2026-03-10", "amountUsd": 200, "amountBs": 8000},
    ...        {"date": "2026-02-10", "amountUsd": 999, "amountBs": 999}]
    >>> rr = compute_run_rate(txs, fiscal_year=2026, now=dt.datetime(2026, 3, 15, 12))
    >>> rr.count, rr.accumulated_usd, rr.projected_usd, rr.days_in_month
    (2, 300.0, 620.0, 31)
    >>> rr.current_day, rr.max_day, rr.day_progress
    (15, 10, 48.38709677419355)

    Si el mes auditado no es el del reloj, el corte es el último día con datos y
    no el día de hoy:

    >>> rr2 = compute_run_rate(txs, fiscal_year=2026, now=dt.datetime(2026, 6, 20, 12))
    >>> rr2.month_key, rr2.current_day, rr2.audit.is_live_month
    ('2026-03', 10, False)
    """
    audit = resolve_active_audit_month(txs, fiscal_year=fiscal_year, now=now)
    month_txs = transactions_of_month(txs, audit.key)

    max_day = 1
    for tx in month_txs:
        max_day = max(max_day, day_of_month(tx.get("date")) or 1)

    if audit.is_live_month:
        current_day = max(1, now.day)
    else:
        current_day = max_day if month_txs else audit.last_day

    return RunRate(
        audit=audit,
        month_key=audit.key,
        days_in_month=audit.last_day,
        max_day=max_day,
        current_day=current_day,
        accumulated_usd=_sum(
            [js_number_or_zero(tx.get("amountUsd")) for tx in month_txs]
        ),
        accumulated_bs=_sum([js_number_or_zero(tx.get("amountBs")) for tx in month_txs]),
        count=len(month_txs),
    )


def run_rate_view(
    txs: list[dict[str, Any]],
    *,
    fiscal_year: Any,
    now: datetime,
    ctx: MoneyContext,
) -> dict[str, str]:
    """Lo que la versión de referencia escribe en los cinco nodos del bloque run-rate.

    >>> import datetime as dt
    >>> ctx = MoneyContext("VES", 2, 40.0)
    >>> txs = [{"date": "2026-03-01", "amountUsd": 100, "amountBs": 4000}]
    >>> view = run_rate_view(txs, fiscal_year=2026, now=dt.datetime(2026, 3, 15, 12), ctx=ctx)
    >>> view["runRateDay"]
    'Corte día 15 de 31 (2026-03)'
    >>> view["runRateBar"]
    '48.4%'
    >>> view["runRateSub"]
    'Período 2026-03 · Acumulado: Bs. 4.000,00 (1 movs)'
    >>> view["runRatePacePct"]
    'Media: Bs. 266,67/día'
    """
    rate = compute_run_rate(txs, fiscal_year=fiscal_year, now=now)

    if rate.count:
        accrued = fmt_money(rate.accumulated_usd, rate.accumulated_bs, ctx)
        subtitle = (
            f"Período {rate.month_key} · Acumulado: {accrued} ({rate.count} movs)"
        )
    else:
        subtitle = f"Sin datos en {rate.month_key}"

    return {
        "runRateProj": fmt_money(rate.projected_usd, rate.projected_bs, ctx),
        "runRateSub": subtitle,
        "runRateBar": js_to_fixed(rate.day_progress, 1) + "%",
        "runRateDay": (
            f"Corte día {rate.current_day} de {rate.days_in_month} ({rate.month_key})"
        ),
        "runRatePacePct": f"Media: {fmt_money(rate.daily_usd, rate.daily_bs, ctx)}/día",
    }
