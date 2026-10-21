"""Formato de fechas con la semántica de ``toLocaleString`` de JavaScript.

La versión de referencia usa dos llamadas dependientes del entorno:

======================  ========================================================
``toLocaleString('es-VE')``  Acta de cierre (fecha y hora).
``toLocaleDateString()``     Hoja «Catálogo» del Excel (sin localidad explícita,
                             es decir, la localidad por defecto del navegador).
======================  ========================================================

Replicar *la localidad del navegador* no es posible de forma determinista, así
que esta implementación fija ``DEFAULT_LOCALE`` (la localidad del entorno de referencia, que
es la misma que la versión de referencia muestra en este equipo) y documenta la decisión. El
verificación informa de la localidad real del proceso de referencia para poder detectar la
diferencia.

Formatos de ``es-VE`` (V8/ICU)::

    new Date('2026-03-15T12:30:45Z').toLocaleString('es-VE')
      -> '15/3/2026, 8:30:45 a. m.'      (huso UTC−4)
    new Date('2026-01-01T04:05:06Z').toLocaleString('es-VE')
      -> '1/1/2026, 12:05:06 a. m.'
    new Date('2026-01-01T04:05:06Z').toLocaleDateString('es-VE')
      -> '1/1/2026'

El día y el mes van sin ceros a la izquierda, la hora en formato de 12 horas sin
cero a la izquierda y el sufijo es ``a. m.`` / ``p. m.``.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

__all__ = [
    "DEFAULT_LOCALE",
    "SUPPORTED_LOCALES",
    "iso_string",
    "locale_date",
    "locale_datetime",
    "parse_date_ms",
]

#: Localidad por defecto del entorno de referencia (``Intl`` del entorno de referencia).
DEFAULT_LOCALE = "es-VE"
SUPPORTED_LOCALES = ("es-VE",)


def _local_datetime(ms: float) -> datetime:
    """``new Date(ms)`` leído con los getters locales."""
    return datetime.fromtimestamp(ms / 1000)


def _check(locale: str | None) -> str:
    resolved = locale or DEFAULT_LOCALE
    if resolved not in SUPPORTED_LOCALES:
        raise ValueError(
            f"localidad no soportada: {resolved!r} (soportadas: {SUPPORTED_LOCALES})"
        )
    return resolved


def locale_datetime(ms: float, locale: str | None = None) -> str:
    """``new Date(ms).toLocaleString(locale)`` para ``es-VE``.

    >>> locale_datetime(1773577845000)  # 2026-03-15T12:30:45Z
    '15/3/2026, 8:30:45 a. m.'
    >>> locale_datetime(1767240306000)  # 2026-01-01T04:05:06Z
    '1/1/2026, 12:05:06 a. m.'
    """
    _check(locale)
    moment = _local_datetime(ms)
    hour = moment.hour % 12 or 12
    period = "a. m." if moment.hour < 12 else "p. m."
    return (
        f"{moment.day}/{moment.month}/{moment.year}, "
        f"{hour}:{moment.minute:02d}:{moment.second:02d} {period}"
    )


def locale_date(ms: float, locale: str | None = None) -> str:
    """``new Date(ms).toLocaleDateString(locale)`` para ``es-VE``.

    >>> locale_date(1773577845000)  # 2026-03-15T12:30:45Z
    '15/3/2026'
    >>> locale_date(1767240306000)  # 2026-01-01T04:05:06Z
    '1/1/2026'
    """
    _check(locale)
    moment = _local_datetime(ms)
    return f"{moment.day}/{moment.month}/{moment.year}"


def iso_string(ms: float) -> str:
    """``new Date(ms).toISOString()`` (siempre en UTC, con milisegundos).

    >>> iso_string(1773577845123)
    '2026-03-15T12:30:45.123Z'
    """
    moment = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return (
        f"{moment.year:04d}-{moment.month:02d}-{moment.day:02d}T"
        f"{moment.hour:02d}:{moment.minute:02d}:{moment.second:02d}."
        f"{moment.microsecond // 1000:03d}Z"
    )


def parse_date_ms(value: Any) -> float:
    """``new Date(value).getTime()`` para los formatos que usa la aplicación.

    Acepta milisegundos, ``YYYY-MM-DD`` (medianoche **UTC**, como JavaScript),
    ``YYYY-MM-DDTHH:MM[:SS[.mmm]]`` (hora **local**, como JavaScript) y con el
    sufijo ``Z`` o desplazamiento (UTC).

    >>> parse_date_ms("2026-03-15T12:30:45.123Z")
    1773577845123.0
    >>> parse_date_ms("2026-03-15")
    1773532800000.0
    """
    if isinstance(value, bool):
        raise TypeError("booleano no es una fecha")
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    date_only = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if date_only:
        moment = datetime(
            int(date_only.group(1)),
            int(date_only.group(2)),
            int(date_only.group(3)),
            tzinfo=timezone.utc,
        )
        return moment.timestamp() * 1000
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    moment = datetime.fromisoformat(normalized)
    if moment.tzinfo is None:
        return moment.astimezone().timestamp() * 1000
    return moment.timestamp() * 1000
