"""Indicador de ritmo: mes auditado contra el mes anterior comparable.

Implementación de la versión **efectiva** de ``renderPaceIndicator`` (capa de compatibilidad,
línea 7590); la declaración de la línea 3365 queda reasignada.

Compara lo gastado en el mes auditado **hasta el día de corte** con lo gastado en
el mes anterior **hasta el mismo día**, no el total de ambos meses: así la
comparación es homogénea. Si el mes anterior natural no tiene datos, se usa el
último mes anterior con actividad.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..core.money import MoneyContext, fmt_money, js_number_or_zero, js_to_fixed
from .dates import AuditMonth, day_of_month, js_date, resolve_active_audit_month
from .runrate import _sum, month_key_of

__all__ = ["PaceIndicator", "compute_pace_indicator", "pace_indicator_view"]


@dataclass(frozen=True)
class PaceIndicator:
    """Comparativa de ritmo entre dos meses.

    >>> p = PaceIndicator(AuditMonth(2026, 2, True), "2026-03", "2026-02", 15,
    ...                   150.0, 0.0, 100.0, 0.0)
    >>> p.ratio, p.deviation
    (1.5, 50.0)
    """

    audit: AuditMonth
    current_key: str
    previous_key: str
    current_day: int
    current_usd: float
    current_bs: float
    previous_usd: float
    previous_bs: float

    @property
    def ratio(self) -> float:
        """``pUsd > 0 ? cUsd/pUsd : 1``."""
        return (self.current_usd / self.previous_usd) if self.previous_usd > 0 else 1.0

    @property
    def deviation(self) -> float:
        """``(ratio - 1) * 100``."""
        return (self.ratio - 1) * 100

    @property
    def has_base(self) -> bool:
        """``pUsd > 0``."""
        return self.previous_usd > 0


def compute_pace_indicator(
    txs: list[dict[str, Any]], *, fiscal_year: Any, now: datetime
) -> PaceIndicator:
    """Ritmo del mes auditado frente al mes anterior hasta el mismo día.

    >>> import datetime as dt
    >>> txs = [
    ...   {"date": "2026-03-02", "amountUsd": 100, "amountBs": 1},
    ...   {"date": "2026-03-20", "amountUsd": 900, "amountBs": 1},
    ...   {"date": "2026-02-05", "amountUsd": 300, "amountBs": 1},
    ...   {"date": "2026-02-25", "amountUsd": 600, "amountBs": 1}]
    >>> p = compute_pace_indicator(txs, fiscal_year=2026, now=dt.datetime(2026, 3, 15, 12))
    >>> p.current_key, p.previous_key, p.current_day
    ('2026-03', '2026-02', 15)
    >>> p.current_usd, p.previous_usd, p.ratio, p.deviation
    (100.0, 300.0, 0.3333333333333333, -66.66666666666667)

    Solo cuenta lo gastado hasta el día de corte (aquí el 15): la compra del 20
    de marzo y la del 25 de febrero quedan fuera de la comparación.
    """
    audit = resolve_active_audit_month(txs, fiscal_year=fiscal_year, now=now)
    current_txs = [
        tx
        for tx in txs
        if tx.get("date") and month_key_of(tx["date"]) == audit.key
    ]

    max_day = 1
    for tx in current_txs:
        max_day = max(max_day, day_of_month(tx.get("date")) or 1)

    if audit.is_live_month:
        current_day = now.day
    else:
        current_day = max_day if current_txs else 31

    previous_date = js_date(audit.year, audit.month - 1, 1)
    previous_key = f"{previous_date.year}-{previous_date.month:02d}"
    priors = sorted(
        {
            key
            for tx in txs
            if (key := month_key_of(tx.get("date"))) and key < audit.key
        }
    )
    if previous_key not in priors and priors:
        previous_key = priors[-1]

    within_cutoff = [tx for tx in current_txs if day_of_month(tx.get("date")) <= current_day]
    previous_txs = [
        tx
        for tx in txs
        if tx.get("date")
        and month_key_of(tx["date"]) == previous_key
        and day_of_month(tx.get("date")) <= current_day
    ]

    return PaceIndicator(
        audit=audit,
        current_key=audit.key,
        previous_key=previous_key,
        current_day=current_day,
        current_usd=_sum([js_number_or_zero(tx.get("amountUsd")) for tx in within_cutoff]),
        current_bs=_sum([js_number_or_zero(tx.get("amountBs")) for tx in within_cutoff]),
        previous_usd=_sum(
            [js_number_or_zero(tx.get("amountUsd")) for tx in previous_txs]
        ),
        previous_bs=_sum([js_number_or_zero(tx.get("amountBs")) for tx in previous_txs]),
    )


def pace_indicator_view(indicator: PaceIndicator, ctx: MoneyContext) -> dict[str, str]:
    """Lo que la versión de referencia escribe en los cinco nodos del indicador de ritmo.

    >>> ctx = MoneyContext("USD", 2, 40.0)
    >>> p = PaceIndicator(AuditMonth(2026, 2, True), "2026-03", "2026-02", 15,
    ...                   150.0, 0.0, 100.0, 0.0)
    >>> view = pace_indicator_view(p, ctx)
    >>> view["paceChip"], view["paceChipClass"], view["paceRatio"]
    ('Acelerado +50.0%', 'chip bad', '1.50×')
    >>> view["paceSub"]
    'Comparativa 2026-03 vs 2026-02 (día 1 al 15)'
    """
    if not indicator.has_base:
        chip_text, chip_class = "Sin base previa", "chip brand"
    else:
        deviation = indicator.deviation
        if deviation > 10:
            chip_text, chip_class = (
                f"Acelerado +{js_to_fixed(deviation, 1)}%",
                "chip bad",
            )
        elif deviation < -5:
            chip_text, chip_class = f"Ahorro {js_to_fixed(deviation, 1)}%", "chip ok"
        else:
            sign = "+" if deviation >= 0 else ""
            chip_text, chip_class = (
                f"Estable {sign}{js_to_fixed(deviation, 1)}%",
                "chip warn",
            )

    return {
        "paceChip": chip_text,
        "paceChipClass": chip_class,
        "paceRatio": (
            f"{js_to_fixed(indicator.ratio, 2)}×" if indicator.has_base else "—"
        ),
        "paceSub": (
            f"Comparativa {indicator.current_key} vs {indicator.previous_key} "
            f"(día 1 al {indicator.current_day})"
            if indicator.has_base
            else f"Período {indicator.current_key}"
        ),
        "paceCurrent": fmt_money(
            indicator.current_usd, indicator.current_bs, ctx
        ),
        "pacePrevious": fmt_money(
            indicator.previous_usd, indicator.previous_bs, ctx
        ),
    }
