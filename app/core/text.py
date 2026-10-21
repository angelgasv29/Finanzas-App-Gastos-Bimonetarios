"""Utilidades de texto.

Implementación de ``escapeHtml`` (línea 2715 de la referencia) y de la
conversión ``String(x)`` de JavaScript, que hace falta para reproducir las
búsquedas y las concatenaciones de la versión de referencia.
"""

from __future__ import annotations

import math
import re
from typing import Any

__all__ = ["escape_html", "js_to_string"]

_ESCAPE_MAP = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
}

_ESCAPE_RE = re.compile(r"[&<>\"']")


def escape_html(value: Any) -> str:
    """Implementación de ``escapeHtml``.

    Referencia::

        const escapeHtml = str => String(str??'').replace(/[&<>"']/g, m => ({...}[m]));

    El operador ``??`` (nullish coalescing) solo sustituye ``null`` y
    ``undefined``; un valor ``0`` o ``""`` se conservan, a diferencia de ``||``.

    >>> escape_html('<b> & "x" </b>')
    '&lt;b&gt; &amp; &quot;x&quot; &lt;/b&gt;'
    >>> escape_html(None)
    ''
    >>> escape_html("O'Neill")
    'O&#39;Neill'
    """
    if value is None:
        return ""
    return _ESCAPE_RE.sub(lambda m: _ESCAPE_MAP[m.group()], str(value))


_EXPONENT_RE = re.compile(r"e([+-])0*(\d+)")


def js_to_string(value: Any, nullish: str = "") -> str:
    """Implementación de ``String(x)`` para los valores que maneja la aplicación.

    Diferencias con ``str()`` de Python que importan de verdad:

    - ``None`` (``null``/``undefined``) → ``""`` por defecto. En JavaScript
      ``String(null)`` sería ``"null"``, pero la versión de referencia casi siempre usa estos
      valores dentro de un ``Array.join(' ')``, donde ``null`` y ``undefined``
      se convierten en cadena vacía. Por eso el parámetro ``nullish``.
    - Los booleanos se escriben ``true``/``false``, no ``True``/``False``.
    - Los números se escriben con el **exponente de JavaScript**: ``1e-7`` y no
      ``1e-07``.
    - Un *float* entero se escribe sin decimales (``232``, no ``232.0``).

    >>> js_to_string(232.0)
    '232'
    >>> js_to_string(True), js_to_string(False)
    ('true', 'false')
    >>> js_to_string(1e-7)
    '1e-7'
    >>> js_to_string(0.1 + 0.2)
    '0.30000000000000004'
    >>> js_to_string(None), js_to_string(None, "null")
    ('', 'null')
    >>> js_to_string(float("nan")), js_to_string(float("inf"))
    ('NaN', 'Infinity')
    """
    if value is None:
        return nullish
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        if value.is_integer() and abs(value) < 1e21:
            return str(int(value))
        return _EXPONENT_RE.sub(
            lambda m: f"e{m.group(1)}{int(m.group(2))}", repr(value)
        )
    return str(value)
