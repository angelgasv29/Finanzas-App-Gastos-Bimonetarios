"""Estadística descriptiva y regresión lineal.

Implementación de la sección 17 del JavaScript de referencia (líneas 4882-4905 de
la referencia).

**Precisión:** el orden de las operaciones se replica tal cual (sumas
secuenciales en lugar de ``sum()`` vectorizado) para que el error de coma
flotante sea el mismo que en JavaScript y los resultados coincidan bit a bit.
Es la condición para que la verificación cruzada contra la referencia sea exacta.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

from .money import js_number_or_zero as num_or_zero

__all__ = ["median", "mean", "stdev", "linear_regression", "cagr", "unit_price"]


def median(arr: Sequence[float]) -> float:
    """Implementación de ``median``.

    Lista vacía → ``0``. Con longitud par, media de los dos centrales.

    >>> median([3, 1, 2])
    2
    >>> median([1, 2, 3, 4])
    2.5
    >>> median([])
    0
    """
    if not len(arr):
        return 0
    ordered = sorted(arr)  # la versión de referencia ordena activamente, no asume orden
    m = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[m]
    return (ordered[m - 1] + ordered[m]) / 2


def mean(arr: Sequence[float]) -> float:
    """Implementación de ``mean``. Suma secuencial, como ``reduce``.

    >>> mean([1, 2, 3])
    2.0
    >>> mean([])
    0
    """
    if not len(arr):
        return 0
    total = 0.0
    for value in arr:
        total += value
    return total / len(arr)


def stdev(arr: Sequence[float]) -> float:
    """Implementación de ``stdev``: desviación estándar **muestral** (n−1).

    Menos de 2 elementos → ``0``.

    >>> stdev([2, 4, 4, 4, 5, 5, 7, 9])
    2.138089935299395
    """
    if len(arr) < 2:
        return 0
    m = mean(arr)
    acc = 0.0
    for value in arr:
        acc += (value - m) * (value - m)
    return math.sqrt(acc / (len(arr) - 1))


def linear_regression(
    xs: Sequence[float], ys: Sequence[float]
) -> dict[str, float]:
    """Implementación de ``linearRegression``: mínimos cuadrados ordinarios.

    Devuelve ``{'a': intercepto, 'b': pendiente, 'r2': coeficiente de
    determinación}``. Con menos de 2 puntos devuelve la pendiente 0 y el primer
    valor de ``ys`` como intercepto, igual que la versión de referencia.

    >>> r = linear_regression([0, 1, 2, 3], [1, 3, 5, 7])
    >>> r['b'], r['a'], r['r2']
    (2.0, 1.0, 1.0)
    """
    n = len(xs)
    if n < 2:
        return {"a": (ys[0] if ys else 0), "b": 0, "r2": 0}

    mx = mean(xs)
    my = mean(ys)

    num = 0.0
    den = 0.0
    for i in range(n):
        num += (xs[i] - mx) * (ys[i] - my)
        den += (xs[i] - mx) * (xs[i] - mx)

    b = num / den if den else 0
    a = my - b * mx

    ss_res = 0.0
    ss_tot = 0.0
    for i in range(n):
        predicted = a + b * xs[i]
        ss_res += (ys[i] - predicted) * (ys[i] - predicted)
        ss_tot += (ys[i] - my) * (ys[i] - my)

    return {"a": a, "b": b, "r2": 1 - ss_res / ss_tot if ss_tot else 0}


def cagr(first_val: Any, last_val: Any, days: Any) -> float:
    """Implementación de ``cagr``: tasa de crecimiento anual compuesta, en %.

    Devuelve ``0`` si falta algún valor, si ``first_val <= 0`` o si
    ``days <= 0``. El año se cuenta como 365 días.

    >>> cagr(100, 121, 365)
    20.999999999999996
    >>> cagr(0, 121, 365)
    0
    """
    first = num_or_zero(first_val)
    last = num_or_zero(last_val)
    d = num_or_zero(days)

    # La versión de referencia usa `!firstVal || !lastVal || firstVal<=0 || days<=0`
    if not first or not last or first <= 0 or d <= 0:
        return 0
    years = d / 365
    if years > 0:
        return (math.pow(last / first, 1 / years) - 1) * 100
    return 0


def unit_price(tx: dict[str, Any]) -> dict[str, Any]:
    """Implementación de ``unitPrice``: precio unitario de una transacción.

    Si la cantidad es mayor que cero, divide; si no, devuelve el importe total
    con cantidad 1. La unidad por defecto es ``'unidad'``.

    >>> unit_price({'quantity': 2, 'amountBs': 100, 'amountUsd': 20, 'unit': 'kg'})
    {'unitBs': 50.0, 'unitUsd': 10.0, 'qty': 2.0, 'unit': 'kg'}
    >>> unit_price({'amountBs': 100, 'amountUsd': 20})
    {'unitBs': 100.0, 'unitUsd': 20.0, 'qty': 1, 'unit': 'unidad'}
    """
    qty = num_or_zero(tx.get("quantity"))
    amount_bs = num_or_zero(tx.get("amountBs"))
    amount_usd = num_or_zero(tx.get("amountUsd"))
    unit = tx.get("unit") or "unidad"

    if qty > 0:
        return {
            "unitBs": amount_bs / qty,
            "unitUsd": amount_usd / qty,
            "qty": qty,
            "unit": unit,
        }
    return {"unitBs": amount_bs, "unitUsd": amount_usd, "qty": 1, "unit": unit}


def safe_div(numerator: float, denominator: float, fallback: float = 0.0) -> float:
    """División defendida. Auxiliar de los módulos de análisis.

    No existe en la versión de referencia (allí se repite la guarda ``den ? ... : 0``
    decenas de veces); se centraliza aquí para no arrastrar el mismo ajuste.
    """
    return numerator / denominator if denominator else fallback


def sum_by(items: Iterable[Any], key) -> float:
    """Suma secuencial de un campo. Replica el orden de ``reduce`` de JS."""
    total = 0.0
    for item in items:
        total += key(item)
    return total
