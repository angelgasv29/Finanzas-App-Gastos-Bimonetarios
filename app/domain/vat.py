"""IVA: los tres modos del formulario de registro.

Implementación del bloque de cálculo que la versión de referencia **repite** cuatro veces con el mismo
código (líneas 3938-3941 al guardar, 3823-3826 en la vista previa, 4368-4371 al
editar y 3249-3250 en el desglose):

.. code-block:: javascript

   if (mode==='exento')        { base=bs; iva=0;            total=bs; }
   else if (mode==='incluido') { total=bs; base=total/(1+IVA_RATE); iva=total-base; }
   else                        { base=bs; iva=base*IVA_RATE; total=base+iva; }

Tres detalles que se respetan a propósito:

1. **Cualquier modo que no sea ``exento`` ni ``incluido`` cae en la tercera rama**
   (``else``), no solo ``mas_iva``.
2. En ``incluido`` la base se deriva del total, así que ``iva`` es una
   **resta**, no una multiplicación: el redondeo no es el mismo.
3. El editor de transacciones usa los literales ``1.16`` y ``0.16`` en lugar de
   ``1 + IVA_RATE`` y ``IVA_RATE``. Se comprobó en el motor de la versión de referencia que
   ``1 + 0.16 === 1.16`` como *double* IEEE754, así que ambas formas son
   idénticas y aquí se usa siempre :data:`~app.core.constants.IVA_RATE`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..core.constants import IVA_RATE
from ..core.money import (
    MoneyContext,
    format_bs,
    format_usd,
    js_number_or_zero,
    js_parse_float_or_zero,
    js_round,
)

__all__ = ["VatAmounts", "compute_vat", "DEFAULT_VAT_MODE", "vat_preview"]

# ``getVatMode`` devuelve 'incluido' si no hay ninguna opción marcada.
DEFAULT_VAT_MODE = "incluido"


@dataclass(frozen=True)
class VatAmounts:
    """Base imponible, IVA y total de un monto en bolívares.

    >>> VatAmounts(100.0, 16.0, 116.0).total
    116.0
    """

    base: float
    iva: float
    total: float


def compute_vat(bs: Any, mode: str = DEFAULT_VAT_MODE) -> VatAmounts:
    """Desglose del IVA de un monto en bolívares.

    :param bs: monto tecleado en el formulario (en Bs).
    :param mode: ``'exento'``, ``'incluido'`` o cualquier otra cosa (``'mas_iva'``).

    >>> compute_vat(116, "exento")
    VatAmounts(base=116.0, iva=0, total=116.0)
    >>> compute_vat(116, "incluido").base
    100.0
    >>> compute_vat(100, "mas_iva").total
    116.0
    >>> compute_vat(100, "lo-que-sea").total   # el else es 'mas_iva'
    116.0
    """
    amount = js_parse_float_or_zero(bs)  # parseFloat(...) || 0

    if mode == "exento":
        return VatAmounts(base=amount, iva=0, total=amount)
    if mode == "incluido":
        base = amount / (1 + IVA_RATE)
        return VatAmounts(base=base, iva=amount - base, total=amount)
    iva = amount * IVA_RATE
    return VatAmounts(base=amount, iva=iva, total=amount + iva)


def rounded_vat(bs: Any, mode: str = DEFAULT_VAT_MODE) -> VatAmounts:
    """Desglose con el redondeo que aplica ``saveTransaction``.

    >>> rounded_vat(116, "incluido")
    VatAmounts(base=100.0, iva=16.0, total=116.0)
    >>> rounded_vat(100, "mas_iva")
    VatAmounts(base=100.0, iva=16.0, total=116.0)
    >>> rounded_vat(100.05, "incluido").base
    86.25
    """
    amounts = compute_vat(bs, mode)
    return VatAmounts(
        base=js_round(amounts.base, 2),
        iva=js_round(amounts.iva, 2),
        total=js_round(amounts.total, 2),
    )


def vat_preview(
    bs: Any, mode: str, rate_value: Any, ctx: MoneyContext
) -> dict[str, str]:
    """Vista previa del IVA (``updateVatPreview``, líneas 3818-3832).

    Devuelve lo que la versión de referencia escribe en cuatro nodos del formulario.

    >>> ctx = MoneyContext("VES", 2, 40.0)
    >>> vat_preview(116, "incluido", 40.0, ctx)
    {'vpBaseBs': 'Bs. 100,00', 'vpIvaBs': 'Bs. 16,00', 'vpTotalBs': 'Bs. 116,00', 'vpTotalUsd': '$ 2.90'}
    """
    amounts = compute_vat(bs, mode)
    rate = js_number_or_zero(rate_value) if rate_value else 0.0
    return {
        "vpBaseBs": format_bs(amounts.base),
        "vpIvaBs": format_bs(amounts.iva),
        "vpTotalBs": format_bs(amounts.total),
        "vpTotalUsd": format_usd(amounts.total / rate if rate else 0, ctx.decimals),
    }
