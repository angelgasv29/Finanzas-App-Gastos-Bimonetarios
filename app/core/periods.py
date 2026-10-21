"""Rangos temporales del panel de análisis.

Implementación de ``getTemporalRange``, ``shiftTemporal`` y ``formatTemporalLabel``
(líneas 4906-4943 de la referencia).

Hay dos detalles de JavaScript que este módulo reproduce a propósito, porque
son la fuente más común de discrepancias al implementar fechas:

1. ``new Date(año, mes, 0)`` — con día ``0`` — significa *el último día del mes
   anterior*. Es el truco que usa la versión de referencia para obtener el fin de mes, y se
   reproduce con :func:`calendar.monthrange`.

2. ``setMonth`` / ``setFullYear`` **desbordan**, no recortan. El 31 de enero
   más un mes es el **3 de marzo** (31 de febrero no existe → 28 de febrero más
   3 días), no el 28 de febrero. Recortar con ``min(día, último_día)`` daría un
   resultado distinto al de la versión de referencia.

El rango es **inclusivo** en ambos extremos, con el fin a las ``23:59:59``.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal

__all__ = [
    "TemporalState",
    "get_temporal_range",
    "shift_temporal",
    "format_temporal_label",
    "date_to_iso",
    "today_iso",
    "filter_by_range",
]

TemporalMode = Literal[
    "week",
    "month",
    "bimester",
    "quarter",
    "quadrimester",
    "semester",
    "year",
    "custom",
]

_MODE_NAMES = {
    "week": "Semana",
    "month": "Mes",
    "bimester": "Bimestre",
    "quarter": "Trimestre",
    "quadrimester": "Cuatrimestre",
    "semester": "Semestre",
    "year": "Año",
    "custom": "Personalizado",
}


def date_to_iso(value: date | datetime | str) -> str:
    """Implementación de ``dateToISO``: ``YYYY-MM-DD`` en hora local.

    >>> date_to_iso(datetime(2026, 3, 7, 23, 59, 59))
    '2026-03-07'
    >>> date_to_iso('2026-03-07T10:00:00')
    '2026-03-07'
    """
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return datetime.fromisoformat(str(value)).date().isoformat()


def today_iso() -> str:
    """Implementación de ``todayISO``."""
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Aritmética de fechas con la semántica de JavaScript
# ---------------------------------------------------------------------------


def _js_make_date(
    year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0
) -> datetime:
    """Equivale a ``new Date(year, month-1, day, hour, minute, second)``.

    JavaScript **normaliza** los valores fuera de rango en lugar de fallar:
    ``new Date(2026, 1, 31)`` (31 de febrero) es el 3 de marzo. Se reproduce
    construyendo el día 1 y sumando ``day - 1`` días.

    :param month: mes 1-12 (la versión de referencia usa 0-11, aquí se normaliza).
    """
    month_total = year * 12 + (month - 1)
    normalized_year, month_index = divmod(month_total, 12)
    base = datetime(normalized_year, month_index + 1, 1, hour, minute, second)
    return base + timedelta(days=day - 1)


def _end_of_month(year: int, month: int) -> datetime:
    """``new Date(year, month, 0, 23, 59, 59)`` — último día del mes dado.

    :param month: mes 1-12.
    """
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, last_day, 23, 59, 59)


def _end_of_block(year: int, start_month: int, block: int) -> datetime:
    """Último día del bloque de ``block`` meses que empieza en ``start_month``.

    Equivale a ``new Date(year, startIndex0 + block, 0, 23, 59, 59)``.
    """
    total_month = start_month + block - 1
    year += (total_month - 1) // 12
    month = (total_month - 1) % 12 + 1
    return _end_of_month(year, month)


@dataclass
class TemporalState:
    """Estado del selector temporal. Reemplaza el objeto global ``TEMPORAL``.

    La versión de referencia muta ``TEMPORAL.refDate`` desde varias funciones; aquí el estado
    es explícito para que sea probable.
    """

    mode: TemporalMode = "month"
    ref_date: datetime | None = None
    custom_start: datetime | None = None
    custom_end: datetime | None = None

    def __post_init__(self) -> None:
        if self.ref_date is None:
            self.ref_date = datetime.now()

    @classmethod
    def from_mode(
        cls, mode: TemporalMode, ref: datetime | None = None
    ) -> "TemporalState":
        """Atajo para construir un estado con un modo y una fecha de referencia."""
        return cls(mode=mode, ref_date=ref or datetime.now())


def get_temporal_range(state: TemporalState) -> tuple[datetime, datetime]:
    """Implementación de ``getTemporalRange``.

    Devuelve ``(inicio, fin)``, ambos inclusivos, con el fin a las 23:59:59.

    >>> s = TemporalState.from_mode('year', datetime(2026, 6, 15))
    >>> get_temporal_range(s)
    (datetime.datetime(2026, 1, 1, 0, 0), datetime.datetime(2026, 12, 31, 23, 59, 59))
    >>> s = TemporalState.from_mode('bimester', datetime(2026, 3, 10))
    >>> get_temporal_range(s)
    (datetime.datetime(2026, 3, 1, 0, 0), datetime.datetime(2026, 4, 30, 23, 59, 59))
    """
    mode = state.mode
    ref = state.ref_date
    assert ref is not None  # garantizado por __post_init__

    if mode == "custom":
        if state.custom_start is None or state.custom_end is None:
            return datetime(ref.year, ref.month, 1), _end_of_month(ref.year, ref.month)
        return state.custom_start, state.custom_end

    if mode == "week":
        # ``getDay()`` de JS es 0=domingo..6=sábado; el desplazamiento hasta el
        # lunes es (getDay()+6)%7, que es exactamente ``weekday()`` en Python.
        offset = ref.weekday()
        monday = ref - timedelta(days=offset)
        start = datetime(monday.year, monday.month, monday.day)
        end = (start + timedelta(days=6)).replace(hour=23, minute=59, second=59)
        return start, end

    if mode == "month":
        return datetime(ref.year, ref.month, 1), _end_of_month(ref.year, ref.month)

    if mode == "bimester":
        # JS: Math.floor(getMonth()/2), con getMonth() 0-11 → (month-1)//2.
        b = (ref.month - 1) // 2
        start_month = b * 2 + 1
        return (
            datetime(ref.year, start_month, 1),
            _end_of_block(ref.year, start_month, 2),
        )

    if mode == "quarter":
        q = (ref.month - 1) // 3
        start_month = q * 3 + 1
        return (
            datetime(ref.year, start_month, 1),
            _end_of_block(ref.year, start_month, 3),
        )

    if mode == "quadrimester":
        q = (ref.month - 1) // 4
        start_month = q * 4 + 1
        return (
            datetime(ref.year, start_month, 1),
            _end_of_block(ref.year, start_month, 4),
        )

    if mode == "semester":
        s = (ref.month - 1) // 6
        start_month = s * 6 + 1
        return (
            datetime(ref.year, start_month, 1),
            _end_of_block(ref.year, start_month, 6),
        )

    if mode == "year":
        return datetime(ref.year, 1, 1), datetime(ref.year, 12, 31, 23, 59, 59)

    # Modo desconocido: la versión de referencia cae a "mes".
    return datetime(ref.year, ref.month, 1), _end_of_month(ref.year, ref.month)


def shift_temporal(state: TemporalState, direction: int) -> TemporalState:
    """Implementación de ``shiftTemporal``: desplaza el período.

    Devuelve un estado **nuevo** (la versión de referencia muta el global). En modo ``custom``
    no hace nada, igual que la versión de referencia.

    >>> s = TemporalState.from_mode('month', datetime(2026, 1, 15))
    >>> shift_temporal(s, 1).ref_date
    datetime.datetime(2026, 2, 15, 0, 0)

    El caso del 31 de enero revela el desbordamiento de JavaScript, que aquí se
    reproduce en lugar de recortar:

    >>> s = TemporalState.from_mode('month', datetime(2026, 1, 31))
    >>> shift_temporal(s, 1).ref_date
    datetime.datetime(2026, 3, 3, 0, 0)
    """
    if state.mode == "custom":
        return state

    ref = state.ref_date
    assert ref is not None
    mode = state.mode

    def add_months(base: datetime, months: int) -> datetime:
        """``setMonth(m + months)`` con normalización por desbordamiento."""
        total = base.year * 12 + (base.month - 1) + months
        year, month_index = divmod(total, 12)
        return _js_make_date(
            year,
            month_index + 1,
            base.day,
            base.hour,
            base.minute,
            base.second,
        )

    if mode == "week":
        ref = ref + timedelta(days=7 * direction)
    elif mode == "month":
        ref = add_months(ref, direction)
    elif mode == "bimester":
        ref = add_months(ref, 2 * direction)
    elif mode == "quarter":
        ref = add_months(ref, 3 * direction)
    elif mode == "quadrimester":
        ref = add_months(ref, 4 * direction)
    elif mode == "semester":
        ref = add_months(ref, 6 * direction)
    elif mode == "year":
        ref = _js_make_date(
            ref.year + direction,
            ref.month,
            ref.day,
            ref.hour,
            ref.minute,
            ref.second,
        )

    return TemporalState(
        mode=state.mode,
        ref_date=ref,
        custom_start=state.custom_start,
        custom_end=state.custom_end,
    )


def format_temporal_label(state: TemporalState) -> str:
    """Implementación de ``formatTemporalLabel``.

    >>> s = TemporalState.from_mode('month', datetime(2026, 3, 15))
    >>> format_temporal_label(s)
    'Mes: 2026-03-01 → 2026-03-31'
    """
    start, end = get_temporal_range(state)
    name = _MODE_NAMES.get(state.mode, "")
    return f"{name}: {date_to_iso(start)} → {date_to_iso(end)}"


def filter_by_range(
    transactions: list[dict[str, Any]], start: datetime, end: datetime
) -> list[dict[str, Any]]:
    """Implementación de ``getFilteredTx``, sin acceso a base de datos.

    La versión de referencia compara cadenas ISO (``t.date >= s``), lo cual es correcto
    lexicográficamente para ``YYYY-MM-DD``. Se conserva esa comparación exacta
    en lugar de convertir a ``date``, para no introducir diferencias.
    """
    s = date_to_iso(start)
    e = date_to_iso(end)
    return [
        t for t in transactions if t.get("date", "") >= s and t.get("date", "") <= e
    ]
