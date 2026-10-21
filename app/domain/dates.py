"""Fechas de las reglas de negocio.

Pequeño conjunto de utilidades que reproducen cómo la versión de referencia convierte entre
texto y fechas. La diferencia clave está en **qué constructor usa cada función**,
porque no se comportan igual:

- ``new Date('2026-03-15')``    → medianoche **UTC** (la forma sin hora se
  interpreta como UTC según el estándar).
- ``new Date('2026-03-15T00:00:00')`` → medianoche **local**.

Por eso ``renderRunRate`` (que usa la segunda forma) agrupa por mes local, y
``renderRecurringCommitments`` (que usa la primera) calcula diferencias en días
exactas. Se replica cada caso con la misma forma.
"""

from __future__ import annotations

import calendar
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ..core.money import _js_number_raw, js_parse_int

__all__ = [
    "parse_local_date",
    "parse_iso_date",
    "same_month",
    "days_in_month",
    "utc_midnight_ms",
    "local_midnight_ms",
    "local_date_at",
    "add_days",
    "AuditMonth",
    "resolve_active_audit_month",
    "js_number_text",
    "js_date",
]

MS_PER_DAY = 86_400_000


def parse_local_date(value: Any) -> date | None:
    """Interpreta un ``YYYY-MM-DD`` como fecha (equivale a añadirle la hora).

    ``new Date('2026-03-15T00:00:00')`` de la versión de referencia. Devuelve ``None`` si el
    valor no es utilizable, porque la versión de referencia descarta esas transacciones
    (``if (!t.date) return false`` y los constructores inválidos dan ``NaN``).

    >>> parse_local_date("2026-03-15")
    datetime.date(2026, 3, 15)
    >>> parse_local_date("") is None
    True
    >>> parse_local_date(None) is None
    True
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def parse_iso_date(value: Any) -> date | None:
    """Alias de :func:`parse_local_date` para los campos de fecha de tipo ISO.

    >>> parse_iso_date("2024-02-29")
    datetime.date(2024, 2, 29)
    """
    return parse_local_date(value)


def same_month(value: Any, reference: date) -> bool:
    """``d.getFullYear() === y && d.getMonth() === m``.

    >>> import datetime as dt
    >>> same_month("2026-03-01", dt.date(2026, 3, 31))
    True
    >>> same_month("2026-04-01", dt.date(2026, 3, 31))
    False
    >>> same_month("", dt.date(2026, 3, 31))
    False
    """
    parsed = parse_local_date(value)
    if parsed is None:
        return False
    return parsed.year == reference.year and parsed.month == reference.month


def days_in_month(year: int, month: int) -> int:
    """``new Date(y, m + 1, 0).getDate()``.

    >>> days_in_month(2026, 2), days_in_month(2024, 2)
    (28, 29)
    """
    return calendar.monthrange(year, month)[1]


def utc_midnight_ms(value: Any) -> int | None:
    """``new Date('2026-03-15').getTime()``: medianoche UTC en milisegundos.

    >>> utc_midnight_ms("1970-01-02")
    86400000
    """
    parsed = parse_local_date(value)
    if parsed is None:
        return None
    return int(
        datetime(parsed.year, parsed.month, parsed.day, tzinfo=timezone.utc).timestamp()
        * 1000
    )


def local_midnight_ms(value: Any) -> int | None:
    """``new Date('2026-03-15T00:00:00').getTime()``: medianoche local.

    >>> isinstance(local_midnight_ms("2026-03-15"), int)
    True
    """
    parsed = parse_local_date(value)
    if parsed is None:
        return None
    return int(datetime(parsed.year, parsed.month, parsed.day).timestamp() * 1000)


def local_date_at(ms: float) -> date:
    """``dateToISO(new Date(ms))``: la fecha **local** de un instante.

    >>> from datetime import datetime as dt
    >>> ms = int(dt(2026, 3, 15, 12, 0, 0).timestamp() * 1000)
    >>> local_date_at(ms)
    datetime.date(2026, 3, 15)
    """
    return datetime.fromtimestamp(ms / 1000).date()


def add_days(base: date, days: float) -> date:
    """Suma días (puede ser fraccionario) sobre una fecha local.

    >>> add_days(date(2026, 3, 15), 30)
    datetime.date(2026, 4, 14)
    """
    return base + timedelta(days=days)


def day_of_month(value: Any) -> int:
    """``parseInt((t.date||'').slice(8,10), 10) || 0``.

    >>> day_of_month("2026-03-15"), day_of_month(""), day_of_month("2026-03-00")
    (15, 0, 0)
    """
    parsed = js_parse_int(str(value or "")[8:10])
    return int(parsed) if parsed == parsed else 0


def js_number_text(value: float) -> str:
    """El número como lo escribiría una plantilla de JavaScript.

    >>> js_number_text(2026.0), js_number_text(2026.5)
    ('2026', '2026.5')
    """
    if value == int(value) and abs(value) < 1e21:
        return str(int(value))
    return repr(value)


def js_date(year: float, month: int, day: int) -> date:
    """``new Date(y, m, d)``: normaliza meses fuera de rango como JavaScript.

    >>> js_date(2026, -1, 1)
    datetime.date(2025, 12, 1)
    >>> js_date(2026, 12, 1)
    datetime.date(2027, 1, 1)
    """
    total = int(year) * 12 + month
    return date(total // 12, total % 12 + 1, day)


@dataclass(frozen=True)
class AuditMonth:
    """Mes que la versión de referencia decide auditar (``resolveActiveAuditMonth``, línea 7520).

    Cuando el año fiscal no es el año del reloj —o cuando el mes en curso no
    tiene datos— la aplicación audita el **último mes con actividad** del año
    fiscal, no el mes en curso. ``month`` es **0-based**, igual que
    ``Date#getMonth``.

    >>> AuditMonth(2026, 2, True).key
    '2026-03'
    >>> AuditMonth(2026, 11, False).last_day
    31
    """

    year: float
    month: int
    is_live_month: bool

    @property
    def key(self) -> str:
        """``${y}-${String(m+1).padStart(2,'0')}`` (el año no se rellena).

        >>> AuditMonth(2026, 0, True).key
        '2026-01'
        """
        return f"{js_number_text(self.year)}-{self.month + 1:02d}"

    @property
    def last_day(self) -> int:
        """``new Date(y, m+1, 0).getDate()``: días del mes auditado."""
        return days_in_month(int(self.year), self.month + 1)


def resolve_active_audit_month(
    txs: list[dict[str, Any]] | None,
    *,
    fiscal_year: Any,
    now: datetime,
) -> AuditMonth:
    """``resolveActiveAuditMonth(allTxs)``: qué mes auditan los paneles.

    >>> import datetime as dt
    >>> txs = [{"date": "2026-01-05"}, {"date": "2026-03-02"}]
    >>> resolve_active_audit_month(txs, fiscal_year=2026, now=dt.datetime(2026, 3, 15, 12)).key
    '2026-03'
    >>> resolve_active_audit_month(txs, fiscal_year=2026, now=dt.datetime(2026, 6, 20, 12)).key
    '2026-03'
    >>> resolve_active_audit_month([], fiscal_year=2025, now=dt.datetime(2026, 6, 20, 12)).key
    '2025-12'

    ``Number(APP.fiscalYear) || nowD.getFullYear()``: un año fiscal 0, vacío o
    no numérico cae al año del reloj (como haría JavaScript con ``||``).
    """
    value = _js_number_raw(fiscal_year)
    year = value if (value == value and value != 0) else float(now.year)
    is_current_year = year == now.year
    current_month = now.month - 1  # ``Date#getMonth`` es 0-based
    year_txs = [
        tx
        for tx in (txs or [])
        if tx.get("date") and js_parse_int(str(tx["date"])[:4]) == year
    ]

    if is_current_year and (
        any(js_parse_int(str(tx["date"])[5:7]) - 1 == current_month for tx in year_txs)
        or not year_txs
    ):
        return AuditMonth(year, current_month, True)

    if year_txs:
        last = max(str(tx["date"]) for tx in year_txs)
        last_month = int(js_parse_int(last[5:7]) - 1)
        return AuditMonth(year, last_month, is_current_year and last_month == current_month)

    return AuditMonth(year, current_month if is_current_year else 11, False)
