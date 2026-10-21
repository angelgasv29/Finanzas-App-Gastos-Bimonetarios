"""Tasas de cambio (Bs/USD).

Implementación de la caché de tasas y de su selección por fecha.

La versión de referencia guarda las tasas en ``APP.rates`` **ordenadas de más reciente a más
antigua** (``refreshRatesCache`` reordena al cargar). El orden importa: de él
depende cuál es la "última tasa" y, por tanto, la tasa activa de la aplicación.
"""

from __future__ import annotations

from typing import Any

from ..core.money import js_number_or_zero

__all__ = [
    "HISTORICAL_SUFFIX",
    "rate_value_of",
    "sort_rates_desc",
    "get_rate_for_date",
    "pick_active_rate",
]

# Sufijo que la versión de referencia añade a la fuente cuando la tasa no es exacta
#. Se conserva tal cual porque se muestra en la interfaz.
HISTORICAL_SUFFIX = " (histórico)"


def rate_value_of(rate: dict[str, Any] | None) -> float:
    """``r && r.value ? Number(r.value) : 0`` — el valor numérico de una tasa.

    >>> rate_value_of({"value": 36.64})
    36.64
    >>> rate_value_of({"value": "40.5"})
    40.5
    >>> rate_value_of({"value": 0})
    0.0
    >>> rate_value_of(None)
    0.0
    """
    if not rate:
        return 0.0
    value = rate.get("value")
    if not value:
        return 0.0
    return js_number_or_zero(value)


def sort_rates_desc(rates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ordena las tasas de más reciente a más antigua.

    La versión de referencia usa ``sort((a,b) => (a.date < b.date ? 1 : -1))``, un comparador
    **incoherente**: nunca devuelve 0, así que para dos fechas iguales dice a la
    vez "a va después" y "a va antes". Su resultado depende del motor. En la
    práctica no se nota porque ``date`` es la clave primaria del almacén y no hay
    duplicados; aquí se ordena de verdad, descendente.

    >>> [r["date"] for r in sort_rates_desc([{"date": "2026-01-10"}, {"date": "2026-03-15"}])]
    ['2026-03-15', '2026-01-10']
    """
    return sorted(rates, key=lambda rate: rate.get("date") or "", reverse=True)


def get_rate_for_date(
    rates: list[dict[str, Any]],
    date_str: str | None,
    fallback: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Tasa aplicable a una fecha (``getRateForDate``, líneas 2970-2978).

    Prioridad:

    1. Sin fecha → la tasa activa (``fallback``).
    2. Tasa exacta de esa fecha.
    3. La tasa más reciente **anterior o igual** a esa fecha, marcada como
       histórica (``fuente + ' (histórico)'``).
    4. La tasa activa.

    >>> rates = [{"date": "2026-03-15", "value": 36.64, "source": "BCV"},
    ...          {"date": "2026-01-10", "value": 36.05, "source": "manual"}]
    >>> get_rate_for_date(rates, "2026-03-15")
    {'value': 36.64, 'date': '2026-03-15', 'source': 'BCV'}
    >>> get_rate_for_date(rates, "2026-02-01")
    {'value': 36.05, 'date': '2026-01-10', 'source': 'manual (histórico)'}
    >>> get_rate_for_date(rates, "2025-12-31") is None
    True
    >>> get_rate_for_date(rates, None, {"value": 1.0, "date": "d", "source": "s"})
    {'value': 1.0, 'date': 'd', 'source': 's'}
    """
    if not date_str:
        return fallback

    for rate in rates:
        if rate.get("date") == date_str:
            return {
                "value": rate.get("value"),
                "date": rate.get("date"),
                "source": rate.get("source"),
            }

    for rate in sort_rates_desc(rates):
        if (rate.get("date") or "") <= date_str:
            return {
                "value": rate.get("value"),
                "date": rate.get("date"),
                "source": (rate.get("source") or "") + HISTORICAL_SUFFIX,
            }

    return fallback


def pick_active_rate(
    rates_desc: list[dict[str, Any]],
    current: dict[str, Any] | None,
    session_locked: bool = False,
) -> dict[str, Any] | None:
    """Decide la tasa activa al recargar la caché (``refreshRatesCache``).

    La versión de referencia solo adopta la tasa más reciente si el usuario no ha fijado una
    tasa de sesión y si la activa no es ya la más reciente::

        if (!sessionRate && all[0] && (!APP.rate || APP.rate.date !== all[0].date))
          APP.rate = { value: all[0].value, date: all[0].date, source: all[0].source };

    Devuelve la tasa activa nueva, o ``current`` si no hay que cambiarla.

    >>> newest = {"value": 36.64, "date": "2026-03-15", "source": "BCV"}
    >>> pick_active_rate([newest], None) == newest
    True
    >>> pick_active_rate([newest], newest) is newest
    True
    >>> pick_active_rate([], None) is None
    True
    >>> vieja = {"value": 1.0, "date": "2020-01-01", "source": "x"}
    >>> pick_active_rate([newest], vieja, session_locked=True) is vieja
    True
    """
    if session_locked or not rates_desc:
        return current

    newest = rates_desc[0]
    if current is None or current.get("date") != newest.get("date"):
        return {
            "value": newest.get("value"),
            "date": newest.get("date"),
            "source": newest.get("source"),
        }
    return current
