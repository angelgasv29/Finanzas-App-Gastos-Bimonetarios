"""Generación de identificadores.

Los identificadores aparecen en la interfaz y en las exportaciones, así que
conservan un formato estable y legible: ``PROD-P-A1B2XY34`` para los SKU y
``prefijo_xxxxxxxxxxxx`` para las entidades.

El generador aleatorio y el reloj se pueden inyectar para obtener resultados
reproducibles en las pruebas.
"""

from __future__ import annotations

import random
import time
from typing import Callable

__all__ = ["now_ms", "uid", "new_sku", "BASE36_ALPHABET"]

# Alfabeto de ``Number.prototype.toString(36)``: minúsculas.
BASE36_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"


def now_ms() -> int:
    """Milisegundos desde epoch."""
    return int(time.time() * 1000)


def _fraction_base36(value: float, digits: int) -> str:
    """Genera ``digits`` cifras base-36 de la parte fraccionaria de ``value``.

    Replica ``Math.random().toString(36).slice(2, 2 + digits)``, que es como el
    de referencia extrae caracteres aleatorios.
    """
    out: list[str] = []
    for _ in range(digits):
        value *= 36
        digit = int(value)
        # Protección: random() devuelve [0, 1), así que digit está en 0..35,
        # pero un 1.0 exacto por error de coma flotante daría 36.
        if digit > 35:
            digit = 35
        value -= digit
        out.append(BASE36_ALPHABET[digit])
    return "".join(out)


def _int_base36(value: int) -> str:
    """``Number.prototype.toString(36)`` para enteros no negativos."""
    if value <= 0:
        return "0"
    digits: list[str] = []
    while value:
        value, remainder = divmod(value, 36)
        digits.append(BASE36_ALPHABET[remainder])
    return "".join(reversed(digits))


def uid(
    prefix: str = "id",
    rng: Callable[[], float] | None = None,
    clock: Callable[[], int] | None = None,
) -> str:
    """Genera un identificador con el formato de la aplicación.

    ``prefijo + '_' + 8 caracteres aleatorios + 4 del reloj``. El reloj y el
    generador aleatorio se pueden inyectar para obtener resultados
    reproducibles en las pruebas.

    >>> value = uid('cat', rng=lambda: 0.5, clock=lambda: 1_773_577_845_000)
    >>> value.startswith('cat_'), len(value)
    (True, 16)
    """
    draw = (rng or random.random)()
    suffix = _fraction_base36(draw, 8)
    stamp = _int_base36((clock or now_ms)())[-4:]
    return f"{prefix}_{suffix}{stamp}"


def new_sku(
    workspace: str,
    rng: Callable[[], float] | None = None,
    clock: Callable[[], int] | None = None,
) -> str:
    """Genera un SKU visible con el formato ``PROD-P-XXXX`` / ``PROD-W-XXXX``.

    >>> sku = new_sku('personal', rng=lambda: 0.5, clock=lambda: 1_773_577_845_000)
    >>> sku.startswith('PROD-P-') and sku.isupper(), len(sku)
    (True, 15)
    >>> new_sku('profesional', rng=lambda: 0.5).startswith('PROD-W-')
    True
    """
    prefix = "PROD-P" if workspace == "personal" else "PROD-W"
    draw = (rng or random.random)()
    random_part = _fraction_base36(draw, 4).upper()
    stamp = _int_base36((clock or now_ms)())[-4:].upper()
    return f"{prefix}-{random_part}{stamp}"
