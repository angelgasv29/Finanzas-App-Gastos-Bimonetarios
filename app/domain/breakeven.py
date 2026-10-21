"""Punto de equilibrio: reparto entre gasto fijo y variable.

Implementación de la versión **efectiva** de ``renderBreakEven`` (capa de compatibilidad, línea
7618). Frente a la declaración de la línea 3218, el mes analizado pasa a ser el
mes auditado y los rótulos cambian por completo.

"Fijo" es lo marcado como ``Recurrente``; "variable" es todo lo demás. El
de referencia no calcula un punto de equilibrio contable (ventas mínimas): mide qué
parte del gasto es **comprometido**. Se respeta ese significado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..core.money import MoneyContext, fmt_money, js_number_or_zero, js_to_fixed
from .dates import resolve_active_audit_month
from .runrate import _sum, transactions_of_month

__all__ = ["BreakEven", "compute_break_even", "break_even_view"]

# ``t.nature === 'Recurrente'``.
FIXED_NATURE = "Recurrente"


@dataclass(frozen=True)
class BreakEven:
    """Reparto del gasto del mes auditado.

    >>> be = BreakEven("2026-03", 200.0, 8000.0, 300.0, 12000.0)
    >>> be.total_usd, be.total_bs
    (500.0, 20000.0)
    >>> be.fixed_pct
    40.0
    """

    month_key: str
    fixed_usd: float
    fixed_bs: float
    variable_usd: float
    variable_bs: float

    @property
    def total_usd(self) -> float:
        return self.fixed_usd + self.variable_usd

    @property
    def total_bs(self) -> float:
        return self.fixed_bs + self.variable_bs

    @property
    def fixed_pct(self) -> float:
        """``totU > 0 ? (fUsd/totU)*100 : 50`` — el 50 es de la versión de referencia."""
        if self.total_usd > 0:
            return (self.fixed_usd / self.total_usd) * 100
        return 50.0

    @property
    def variable_pct(self) -> float:
        """``100 - fPct`` (no ``vUsd/totU*100``): la versión de referencia resta del 100."""
        return 100 - self.fixed_pct

    @property
    def has_spend(self) -> bool:
        """``totU > 0``."""
        return self.total_usd > 0


def compute_break_even(
    txs: list[dict[str, Any]], *, fiscal_year: Any, now: datetime
) -> BreakEven:
    """Separa el gasto del mes auditado en fijo y variable.

    >>> import datetime as dt
    >>> txs = [
    ...   {"date": "2026-03-02", "nature": "Recurrente", "amountUsd": 100, "amountBs": 4000},
    ...   {"date": "2026-03-20", "nature": "Recurrente", "amountUsd": 100, "amountBs": 4000},
    ...   {"date": "2026-03-25", "nature": "Extraordinario", "amountUsd": 50, "amountBs": 2000},
    ...   {"date": "2026-04-01", "nature": "Recurrente", "amountUsd": 999, "amountBs": 1}]
    >>> be = compute_break_even(txs, fiscal_year=2026, now=dt.datetime(2026, 3, 15, 12))
    >>> be.month_key, be.fixed_usd, be.variable_usd, be.total_usd
    ('2026-03', 200.0, 50.0, 250.0)
    >>> be.fixed_pct, be.variable_pct
    (80.0, 20.0)
    """
    audit = resolve_active_audit_month(txs, fiscal_year=fiscal_year, now=now)
    month_txs = transactions_of_month(txs, audit.key)

    fixed = [tx for tx in month_txs if tx.get("nature") == FIXED_NATURE]
    variable = [tx for tx in month_txs if tx.get("nature") != FIXED_NATURE]

    return BreakEven(
        month_key=audit.key,
        fixed_usd=_sum([js_number_or_zero(tx.get("amountUsd")) for tx in fixed]),
        fixed_bs=_sum([js_number_or_zero(tx.get("amountBs")) for tx in fixed]),
        variable_usd=_sum([js_number_or_zero(tx.get("amountUsd")) for tx in variable]),
        variable_bs=_sum([js_number_or_zero(tx.get("amountBs")) for tx in variable]),
    )


def break_even_view(
    txs: list[dict[str, Any]],
    *,
    fiscal_year: Any,
    now: datetime,
    ctx: MoneyContext,
) -> dict[str, str]:
    """Lo que la versión de referencia escribe en los seis nodos del bloque de equilibrio.

    >>> import datetime as dt
    >>> txs = [{"date": "2026-03-02", "nature": "Recurrente", "amountUsd": 100, "amountBs": 4000},
    ...        {"date": "2026-03-25", "nature": "Extraordinario", "amountUsd": 50, "amountBs": 2000}]
    >>> view = break_even_view(txs, fiscal_year=2026,
    ...                        now=dt.datetime(2026, 3, 15, 12), ctx=MoneyContext("USD", 2, 40.0))
    >>> view["breakEvenTotal"], view["breakEvenSub"]
    ('$ 150.00', 'Período 2026-03 · 66.7% Fijo vs 33.3% Variable')
    >>> view["beFixedBar"], view["beVarBar"]
    ('66.7%', '33.3%')
    """
    be = compute_break_even(txs, fiscal_year=fiscal_year, now=now)

    if be.has_spend:
        subtitle = (
            f"Período {be.month_key} · {js_to_fixed(be.fixed_pct, 1)}% Fijo vs "
            f"{js_to_fixed(be.variable_pct, 1)}% Variable"
        )
    else:
        subtitle = f"Sin gastos en {be.month_key}"

    return {
        "breakEvenTotal": fmt_money(be.total_usd, be.total_bs, ctx),
        "breakEvenSub": subtitle,
        "beFixedBar": js_to_fixed(be.fixed_pct, 1) + "%",
        "beVarBar": js_to_fixed(be.variable_pct, 1) + "%",
        "beFixedVal": fmt_money(be.fixed_usd, be.fixed_bs, ctx),
        "beVarVal": fmt_money(be.variable_usd, be.variable_bs, ctx),
    }
