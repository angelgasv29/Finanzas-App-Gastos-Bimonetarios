"""Formato y redondeo de moneda con semántica **idéntica a JavaScript**.

Este módulo existe por el riesgo **R2** del análisis de implementación: JavaScript y Python
redondean de forma distinta y, en una aplicación contable, eso produce
diferencias de un céntimo que son inaceptables.

Cuatro comportamientos de la versión de referencia que Python no reproduce por defecto:

1. ``Math.round`` redondea los empates **hacia arriba**
   (``Math.round(2.5) === 3``, ``Math.round(-2.5) === -2``).
   El ``round()`` de Python usa redondeo bancario (``round(2.5) == 2``).

2. ``toLocaleString`` redondea los empates **alejándose de
   cero** (*half-expand*), que tampoco es el comportamiento de ``round()``.

3. El agrupamiento de miles difiere por idioma: ``es-VE`` usa ``1.234,56`` y
   ``en-US`` usa ``1,234.56``. El módulo ``locale`` de Python no trae
   ``es_VE`` de serie, así que se implementa a mano.

4. **Hay dos coercciones numéricas distintas en la versión de referencia** y no son
   intercambiables:

   - ``Number(n || 0)``  → se aplica el ``|| 0`` **antes** de convertir, así que
     una cadena no numérica como ``"abc"`` no está protegida y produce ``NaN``.
     Lo usan ``formatBs``, ``formatUsd`` y ``formatRate``.
   - ``Number(n) || 0``  → se aplica el ``|| 0`` **después**, así que protege
     contra ``NaN``. Lo usan ``round``, ``formatPct`` y ``fmtMoney``.

   :func:`js_number_guard` y :func:`js_number_or_zero` implementan cada una.

5. **``toLocaleString`` y ``toFixed`` redondean distinto en V8, y esto se
   comprobó empíricamente** ejecutando la versión de referencia con la versión de referencia (281 casos, 6
   discrepancias iniciales). El valor ``2.675`` es en binario
   ``2.6749999999999998...``:

   - ``toFixed(2)`` → ``"2.67"`` — redondea el **valor binario exacto**.
   - ``toLocaleString`` → ``"2.68"`` — redondea la **representación decimal
     más corta** (``"2.675"``), que es la que un humano escribiría.

   Como la versión de referencia usa ``toFixed`` en ``formatPct`` y ``toLocaleString`` en
   ``formatBs``/``formatUsd``/``formatRate``, aquí conviven las dos estrategias
   (:data:`ROUND_SHORTEST` y :data:`ROUND_EXACT`). Sin esta distinción, 6 de
   cada 281 valores difieren.

El módulo trabaja con ``float`` (IEEE-754 de doble precisión) igual que
JavaScript, y usa ``Decimal`` **solo** para redondear, que es lo que hacen
``Math.round`` y ``Intl.NumberFormat`` internamente.
"""

from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from typing import Any, Literal

__all__ = [
    "js_number_guard",
    "js_number_or_zero",
    "js_parse_float",
    "js_parse_int",
    "js_round",
    "js_to_fixed",
    "format_bs",
    "format_usd",
    "format_rate",
    "format_pct",
    "money_symbol",
    "fmt_money",
    "money_value",
    "MoneyContext",
]

# Estrategias de redondeo (ver nota 5 de la cabecera del módulo).
RoundingMode = Literal["shortest", "exact"]
ROUND_SHORTEST: RoundingMode = "shortest"  # toLocaleString
ROUND_EXACT: RoundingMode = "exact"  # toFixed


# ---------------------------------------------------------------------------
# Coercciones numéricas de JavaScript
# ---------------------------------------------------------------------------


def js_number_guard(n: Any) -> float:
    """Equivalente a ``Number(n || 0)`` — el ``|| 0`` actúa **antes**.

    Solo protege los valores *falsy* de JavaScript (``0``, ``""``, ``null``,
    ``undefined``, ``NaN``, ``false``). Una cadena no numérica **no** está
    protegida y devuelve ``NaN``, igual que en la versión de referencia.

    >>> js_number_guard(None)
    0.0
    >>> js_number_guard("")
    0.0
    >>> js_number_guard("12.5")
    12.5
    >>> js_number_guard("abc")
    nan
    """
    if n is None or n is False or n == "":
        return 0.0
    if n is True:
        return 1.0
    if isinstance(n, float) and math.isnan(n):
        return 0.0
    if n == 0:
        return 0.0
    try:
        return float(n)
    except (TypeError, ValueError):
        # JavaScript no lanza: devuelve NaN.
        return float("nan")


def js_number_or_zero(n: Any) -> float:
    """Equivalente a ``Number(n) || 0`` — el ``|| 0`` actúa **después**.

    Protege también contra ``NaN``, porque ``NaN`` es *falsy*. Es la coercción
    que usan ``round``, ``formatPct`` y ``fmtMoney``.

    >>> js_number_or_zero("abc")
    0.0
    >>> js_number_or_zero("12.5")
    12.5
    >>> js_number_or_zero(None)
    0.0
    """
    if n is None:
        return 0.0
    if isinstance(n, bool):
        return 1.0 if n else 0.0
    try:
        value = float(n)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(value):
        return 0.0
    return value


def _js_number_raw(n: Any) -> float:
    """Equivalente a ``Number(n)`` **sin** el ``|| 0``: conserva ``NaN``.

    Es la única coercción de JavaScript que devuelve ``NaN`` para una cadena no
    numérica y para ``undefined``. Solo la necesita :func:`js_to_fixed`, porque
    ``(NaN).toFixed(2)`` es ``"NaN"`` y no ``"0.00"``.

    >>> _js_number_raw("abc")
    nan
    >>> _js_number_raw("")    # Number("") es 0, no NaN
    0.0
    >>> _js_number_raw(None)
    0.0
    """
    if n is None or n == "":
        return 0.0
    if isinstance(n, bool):
        return 1.0 if n else 0.0
    try:
        return float(n)
    except (TypeError, ValueError):
        return float("nan")


# ---------------------------------------------------------------------------
# parseFloat / parseInt — no son lo mismo que float() ni que int()
# ---------------------------------------------------------------------------

# Prefijo decimal de ``parseFloat``: signo opcional, luego ``Infinity`` o un
# número decimal con parte entera y/o fraccionaria y exponente opcional.
# Se usa [0-9] y no \d: ``\d`` de Python incluiría dígitos de otros alfabetos
# (por ejemplo árabes), que JavaScript **no** acepta.
_PARSE_FLOAT_RE = re.compile(
    r"[+-]?(?:Infinity|(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)"
)
# Prefijo entero de ``parseInt(x, 10)``.
_PARSE_INT_RE = re.compile(r"[+-]?[0-9]+")


def js_parse_float(value: Any) -> float:
    """Implementación exacto de ``parseFloat``: parsea el **prefijo** numérico.

    No es ``float()`` de Python:

    - ``parseFloat`` acepta lo que pueda al principio y **ignora el resto**
      (``"12.5kg"`` → ``12.5``), mientras que ``float()`` falla.
    - Sin ningún prefijo válido devuelve ``NaN`` (no lanza).
    - Acepta ``"Infinity"`` y ``"-Infinity"``, pero **no** notación hexadecimal.

    La versión de referencia lo usa en todos los campos numéricos del formulario.

    >>> js_parse_float("12.5")
    12.5
    >>> js_parse_float("12.5kg")
    12.5
    >>> js_parse_float("  40.505  ")
    40.505
    >>> js_parse_float("1e3")
    1000.0
    >>> js_parse_float("0x10")     # hexadecimal no está soportado
    0.0
    >>> js_parse_float("abc")
    nan
    >>> js_parse_float("")
    nan
    >>> js_parse_float(None)
    nan
    >>> js_parse_float("١٢٣")   # dígitos árabes: no son [0-9]
    nan
    """
    if value is None or isinstance(value, bool):
        return float("nan")
    text = str(value).lstrip()
    match = _PARSE_FLOAT_RE.match(text)
    if not match:
        return float("nan")
    return float(match.group(0))  # float() sí entiende "Infinity"


def js_parse_int(value: Any, radix: int = 10) -> float:
    """Implementación de ``parseInt(x, 10)``: prefijo entero, o ``NaN``.

    >>> js_parse_int("2026-03-15")
    2026.0
    >>> js_parse_int("  [-12] ")
    nan
    >>> js_parse_int("-12px")
    -12.0
    """
    if value is None or isinstance(value, bool):
        return float("nan")
    text = str(value).lstrip()
    if radix == 10:
        match = _PARSE_INT_RE.match(text)
        if not match:
            return float("nan")
        return float(match.group(0))
    raise NotImplementedError("solo se usa parseInt(x, 10)")


def js_parse_float_or_zero(value: Any) -> float:
    """``parseFloat(x) || 0`` — el patrón de todos los campos numéricos.

    En JavaScript ``NaN`` y ``0`` son *falsy*, así que ambos se convierten en
    ``0``. Es distinto de :func:`js_number_guard`, que usa ``Number`` en lugar de
    ``parseFloat`` y por tanto **no** acepta prefijos (``"12kg"`` sería ``NaN``).

    >>> js_parse_float_or_zero("2.5")
    2.5
    >>> js_parse_float_or_zero("12.5kg")
    12.5
    >>> js_parse_float_or_zero("abc"), js_parse_float_or_zero(""), js_parse_float_or_zero(None)
    (0.0, 0.0, 0.0)
    >>> js_parse_float_or_zero(-3)
    -3.0
    """
    parsed = js_parse_float(value)
    if parsed != parsed or parsed == 0:  # NaN o 0 son falsy
        return 0.0
    return parsed


def js_round(n: Any, d: int = 2) -> float:
    """Implementación exacto de ``const round = (n,d=2) => ...``.

    Referencia::

        const round = (n,d=2) => Math.round((Number(n)||0)*Math.pow(10,d))/Math.pow(10,d);

    ``Math.round(x)`` está definido como ``floor(x + 0.5)``, y eso es lo que se
    reproduce aquí. Se opera en el mismo orden que JavaScript para que el error
    de coma flotante sea idéntico.

    Ojo: el valor por defecto de ``d`` es 2, igual que en la versión de referencia, así que
    con decimales enteros hay que pasar ``d=0`` para ver el redondeo.

    >>> js_round(2.5, 0)
    3.0
    >>> js_round(-2.5, 0)
    -2.0
    >>> js_round(2.675)      # el producto 2.675*100 da 267.5 exacto en IEEE-754
    2.68
    """
    value = js_number_or_zero(n)
    if not math.isfinite(value):
        return value
    power = 10 ** d
    return math.floor(value * power + 0.5) / power


# ---------------------------------------------------------------------------
# Redondeo y agrupamiento
# ---------------------------------------------------------------------------


def _quantize_half_up(
    value: float, decimals: int, mode: RoundingMode = ROUND_SHORTEST
) -> Decimal:
    """Redondea *half-expand* (empate alejándose de cero).

    Dos estrategias, porque V8 usa dos (ver nota 5 de la cabecera):

    - ``ROUND_SHORTEST`` (``toLocaleString``): redondea sobre la representación
      decimal más corta que reconstruye el mismo ``double``.
    - ``ROUND_EXACT`` (``toFixed``): redondea sobre el valor binario exacto.
    """
    if mode == ROUND_EXACT:
        source = Decimal(value)
    else:
        # ``repr`` de un float en Python devuelve la cadena decimal más corta
        # que vuelve al mismo double: el equivalente a Number::toString de JS.
        source = Decimal(repr(float(value)))

    quant = Decimal(1).scaleb(-decimals)
    with localcontext() as ctx:
        ctx.prec = 80
        try:
            return source.quantize(quant, rounding=ROUND_HALF_UP)
        except InvalidOperation:  # pragma: no cover - valores no finitos
            return Decimal(0)


def _group(digits: str, group_sep: str) -> str:
    """Inserta el separador de miles en una cadena de dígitos enteros."""
    sign = ""
    if digits.startswith("-"):
        sign, digits = "-", digits[1:]
    chunks: list[str] = []
    while len(digits) > 3:
        chunks.insert(0, digits[-3:])
        digits = digits[:-3]
    chunks.insert(0, digits)
    return sign + group_sep.join(chunks)


def _format_locale(
    n: Any,
    decimals: int,
    group_sep: str,
    decimal_sep: str,
    min_decimals: int | None = None,
    coerce=js_number_guard,
    mode: RoundingMode = ROUND_SHORTEST,
) -> str:
    """Formatea un número imitando ``toLocaleString``.

    :param decimals: máximo de decimales.
    :param min_decimals: mínimo de decimales; por defecto, igual a ``decimals``.
    :param coerce: coercción numérica a aplicar (la versión de referencia usa dos distintas).
    :param mode: estrategia de redondeo (``toLocaleString`` o ``toFixed``).
    """
    value = coerce(n)

    # JavaScript imprimiría "NaN", "∞" o "-∞" en lugar de fallar.
    if isinstance(value, float) and math.isnan(value):
        return "NaN"
    if isinstance(value, float) and math.isinf(value):
        return "∞" if value > 0 else "-∞"

    minimum = decimals if min_decimals is None else min_decimals

    rounded = _quantize_half_up(value, decimals, mode)
    text = f"{rounded:f}"
    if "." in text:
        int_part, frac_part = text.split(".", 1)
    else:
        int_part, frac_part = text, ""

    # Recorta ceros sobrantes por encima del mínimo exigido.
    while len(frac_part) > minimum and frac_part.endswith("0"):
        frac_part = frac_part[:-1]
    frac_part = frac_part.ljust(minimum, "0")

    grouped = _group(int_part, group_sep)
    if frac_part:
        return f"{grouped}{decimal_sep}{frac_part}"
    return grouped


# ---------------------------------------------------------------------------
# Formateadores de la versión de referencia
# ---------------------------------------------------------------------------


def js_to_fixed(n: Any, digits: int = 0) -> str:
    """``Number.prototype.toFixed`` — el redondeo *exacto* del binario.

    La versión de referencia lo usa para los valores que se escriben dentro de un ``<input>``:
    ``(bs/rateVal).toFixed(4)`` y ``(usd*rateVal).toFixed(2)`` en
    ``recalcBsUsd``. A diferencia de ``toLocaleString``, no
    agrupa miles y no recorta ceros: ``toFixed`` siempre deja los decimales
    pedidos.

    Casos especiales: ``toFixed`` imprime ``NaN``, ``Infinity`` y ``-Infinity``
    en inglés y sin símbolo.

    >>> js_to_fixed(1234.5, 2)
    '1234.50'
    >>> js_to_fixed(2.675, 2)   # 2.675 es 2.67499999... en binario
    '2.67'
    >>> js_to_fixed(1.005, 2)
    '1.00'
    >>> js_to_fixed(float('nan'), 2)
    'NaN'
    >>> js_to_fixed(3, 4)
    '3.0000'
    >>> js_to_fixed(3, 0)
    '3'
    """
    value = _js_number_raw(n)
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        if abs(value) >= 1e21:
            # La especificación de ``toFixed`` corta aquí: a partir de 10^21
            # devuelve ``ToString(x)`` (notación exponencial). El ``repr`` de
            # Python usa el mismo algoritmo de "representación más corta" que
            # V8, así que coinciden.
            return repr(value)
    return _format_locale(
        value,
        digits,
        group_sep="",
        decimal_sep=".",
        coerce=_js_number_raw,
        mode=ROUND_EXACT,
    )


def format_bs(n: Any) -> str:
    """``formatBs`` — ``'Bs. ' + Number(n||0).toLocaleString('es-VE', 2, 2)``.

    >>> format_bs(1234.5)
    'Bs. 1.234,50'
    """
    return "Bs. " + _format_locale(n, 2, group_sep=".", decimal_sep=",")


def format_usd(n: Any, dec: int = 2) -> str:
    """``formatUsd`` — ``'$ ' + Number(n||0).toLocaleString('en-US', dec, dec)``.

    >>> format_usd(1234.5)
    '$ 1,234.50'
    >>> format_usd(1234.5, 4)
    '$ 1,234.5000'
    """
    return "$ " + _format_locale(n, dec, group_sep=",", decimal_sep=".")


def format_rate(n: Any) -> str:
    """``formatRate`` — ``es-VE`` con mínimo 2 y máximo 4 decimales.

    >>> format_rate(40.5)
    '40,50'
    >>> format_rate(40.505)
    '40,505'
    """
    return _format_locale(n, 4, group_sep=".", decimal_sep=",", min_decimals=2)


def format_pct(n: Any) -> str:
    """``formatPct`` — ``(Number(n)||0).toFixed(2) + '%'``.

    Usa ``ROUND_EXACT`` porque ``toFixed`` redondea el valor binario exacto,
    a diferencia de ``toLocaleString``. Los dos ejemplos siguientes son el
    contraejemplo que distingue ambas estrategias: ``2.675`` es en binario
    ``2.6749999999999998...``, así que aquí baja a ``2.67`` mientras que
    :func:`format_bs` sube a ``2,68``.

    >>> format_pct(2.675)
    '2.67%'
    >>> format_pct(12.345)
    '12.35%'
    """
    return (
        _format_locale(
            n,
            2,
            group_sep="",
            decimal_sep=".",
            coerce=js_number_or_zero,
            mode=ROUND_EXACT,
        )
        + "%"
    )


# ---------------------------------------------------------------------------
# Contexto monetario (reemplaza el estado global ``APP`` de las líneas 2844-2879)
# ---------------------------------------------------------------------------


class MoneyContext:
    """Estado necesario para el formateo: moneda activa, decimales y tasa.

    Reemplaza al objeto global ``APP`` de la versión de referencia, del que estas funciones
    dependían implícitamente (``APP.currencyView``, ``APP.decimals``,
    ``APP.rate.value``). Hacerlo explícito permite probar sin estado global.
    """

    __slots__ = ("currency_view", "decimals", "rate_value")

    def __init__(
        self,
        currency_view: str = "USD",
        decimals: int = 2,
        rate_value: float | None = None,
    ) -> None:
        self.currency_view = currency_view
        self.decimals = decimals
        self.rate_value = rate_value

    def symbol(self) -> str:
        """``moneySymbol`` — ``'Bs'`` si la vista es VES, si no ``'USD'``."""
        return "Bs" if self.currency_view == "VES" else "USD"


def fmt_money(
    usd_val: Any,
    bs_val: Any,
    ctx: MoneyContext,
    decimals_override: int | None = None,
) -> str:
    """Implementación de ``fmtMoney``.

    Formatea el par (USD, Bs) eligiendo el activo según la moneda activa.
    Si el valor pedido no está disponible, cae al otro usando la tasa.
    Nunca lanza excepción.

    >>> ctx = MoneyContext("VES", 2, 40.5)
    >>> fmt_money(10, 405, ctx)
    'Bs. 405,00'
    >>> fmt_money(10, 0, ctx)
    'Bs. 405,00'
    """
    dec = decimals_override if isinstance(decimals_override, int) else ctx.decimals
    usd = js_number_or_zero(usd_val)
    bs = js_number_or_zero(bs_val)
    rate = ctx.rate_value or 0.0

    if ctx.currency_view == "VES":
        if bs:
            return format_bs(bs)
        if usd and rate:
            return format_bs(usd * rate)
        return format_bs(0)

    if usd:
        return format_usd(usd, dec)
    if bs and rate:
        return format_usd(bs / rate, dec)
    return format_usd(0, dec)


def money_value(usd_val: Any, bs_val: Any, ctx: MoneyContext) -> float:
    """Implementación de ``moneyValue``: valor numérico en la moneda activa.

    >>> money_value(10, 405, MoneyContext("VES"))
    405.0
    >>> money_value(10, 405, MoneyContext("USD"))
    10.0
    """
    if ctx.currency_view == "VES":
        return js_number_or_zero(bs_val)
    return js_number_or_zero(usd_val)


def money_symbol(ctx: MoneyContext) -> str:
    """Alias funcional de :meth:`MoneyContext.symbol` (compatibilidad)."""
    return ctx.symbol()
