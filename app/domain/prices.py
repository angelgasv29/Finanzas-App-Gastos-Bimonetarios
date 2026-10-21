"""Alerta de sobreprecio frente al histórico del producto.

Implementación de la versión **efectiva** de ``updatePriceAlert`` (capa de compatibilidad, línea
7534). Frente a la declaración de la línea 3839 cambia bastante:

- Si no hay SKU seleccionado, se busca el producto por el **nombre tecleado**
  (``name_lower``), así el aviso funciona sin elegir de la lista.
- La cantidad por defecto es **1** cuando el campo está vacío o no es válido (ya
  no se oculta el aviso).
- Se consideran las compras del SKU, sin mínimo de compras previas.
- El umbral de aviso amarillo es ``> 2 %`` (antes ``> 0``).
- El total tiene en cuenta la modalidad de IVA: con ``mas_iva`` se multiplica por
  ``1 + IVA_RATE`` antes de comparar.

El precio unitario se sigue midiendo en **dólares**.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ..core.constants import IVA_RATE
from ..core.money import (
    format_usd,
    js_number_or_zero,
    js_parse_float,
    js_parse_float_or_zero,
    js_to_fixed,
)
from ..core.stats import mean, unit_price

__all__ = [
    "PriceAlert",
    "LEVEL_BAD",
    "LEVEL_WARN",
    "LEVEL_OK",
    "TITLES",
    "resolve_product_id",
    "compute_price_alert",
    "price_alert_for_form",
    "price_alert_view",
]

LEVEL_OK = "ok"
LEVEL_WARN = "warn"
LEVEL_BAD = "bad"

# ``pct > 15`` → rojo; ``pct > 2`` → amarillo.
BAD_THRESHOLD = 15
WARN_THRESHOLD = 2

# ``titleMap`` del ajuste.
TITLES = {
    LEVEL_OK: "Precio competitivo en rango histórico",
    LEVEL_WARN: "Precio sobre tu promedio histórico",
    LEVEL_BAD: "Sobreprecio detectado (>15% sobre media)",
}

# ``low.tx.provider || '—'``.
NO_PROVIDER = "—"


@dataclass(frozen=True)
class PriceAlert:
    """Resultado de la comparación con el histórico.

    >>> a = PriceAlert(LEVEL_BAD, 32.5, 3.0, 3.975, 2.5, "Mercado", "2026-01-10", "kg", 3)
    >>> a.title
    'Sobreprecio detectado (>15% sobre media)'
    >>> a.pct_label
    '+32.5%'
    >>> a.low_where
    'Mercado · 2026-01-10'
    """

    level: str
    pct: float
    avg: float
    current_unit_usd: float
    lowest_value: float | None
    lowest_provider: str
    lowest_date: str
    unit: str
    history_count: int

    @property
    def title(self) -> str:
        return TITLES[self.level]

    @property
    def pct_label(self) -> str:
        """``${sign}${pct.toFixed(1)}%`` — el signo solo se añade si no es negativo.

        >>> PriceAlert(LEVEL_OK, -4.25, 1, 1, None, "", "", "", 0).pct_label
        '-4.3%'
        >>> PriceAlert(LEVEL_OK, 0.04, 1, 1, None, "", "", "", 0).pct_label
        '+0.0%'
        """
        sign = "+" if self.pct >= 0 else ""
        return f"{sign}{js_to_fixed(self.pct, 1)}%"

    @property
    def low_where(self) -> str:
        if self.lowest_value is None:
            return "—"
        return f"{self.lowest_provider or NO_PROVIDER} · {self.lowest_date}"


def resolve_product_id(
    product_id: Any, product_name: Any, products: Iterable[dict[str, Any]]
) -> str:
    """``pid || APP.products.find(p => p.name_lower === typed)?.id || ''``.

    >>> prods = [{"id": "P1", "name_lower": "café molido"}]
    >>> resolve_product_id("", "  Café Molido ", prods)
    'P1'
    >>> resolve_product_id("P9", "café molido", prods)
    'P9'
    >>> resolve_product_id("", "otro", prods)
    ''
    """
    pid = str(product_id or "").strip()
    if pid:
        return pid
    typed = str(product_name or "").strip().lower()
    if not typed:
        return ""
    for product in products:
        if product.get("name_lower") == typed:
            return str(product.get("id") or "")
    return ""


def compute_price_alert(
    history: list[dict[str, Any]], current_unit_usd: Any, unit: str = "unidad"
) -> PriceAlert | None:
    """Compara el precio unitario actual con el histórico del SKU.

    :param history: compras anteriores **del mismo producto**, ya filtradas.
    :param current_unit_usd: ``(totalBs / tasa) / cantidad`` de la compra en curso.
    :param unit: unidad de medida, solo para mostrarla.

    Devuelve ``None`` cuando la versión de referencia oculta el aviso: sin compras previas o
    sin ningún precio unitario positivo con el que comparar.

    >>> hist = [
    ...   {"date": "2026-01-10", "quantity": 2, "amountUsd": 5, "provider": "Mercado"},
    ...   {"date": "2026-02-10", "quantity": 2, "amountUsd": 7, "provider": "Bodega"},
    ... ]
    >>> compute_price_alert(hist, 3.0, "kg").avg, compute_price_alert(hist, 3.0, "kg").pct
    (3.0, 0.0)
    >>> compute_price_alert(hist, 3.0, "kg").level
    'ok'
    >>> compute_price_alert(hist[:1], 3.0, "kg").level   # ya avisa con 1 compra
    'bad'
    >>> compute_price_alert(hist, 3.1, "kg").level       # +3.3 % sobre el promedio
    'warn'
    >>> compute_price_alert(hist, 4.5, "kg").level       # +50 % → sobreprecio
    'bad'
    """
    ordered = sorted(history, key=lambda tx: tx.get("date") or "")
    current = js_number_or_zero(current_unit_usd)

    unit_prices = [
        unit_price(tx)["unitUsd"] for tx in ordered if unit_price(tx)["unitUsd"] > 0
    ]
    if not unit_prices:
        return None

    average = mean(unit_prices)
    pct = ((current - average) / average) * 100 if average > 0 else 0.0

    lowest_value: float | None = None
    lowest_tx: dict[str, Any] | None = None
    for tx in ordered:
        value = unit_price(tx)["unitUsd"]
        if value > 0 and (lowest_value is None or value < lowest_value):
            lowest_value = value
            lowest_tx = tx

    if pct > BAD_THRESHOLD:
        level = LEVEL_BAD
    elif pct > WARN_THRESHOLD:
        level = LEVEL_WARN
    else:
        level = LEVEL_OK

    return PriceAlert(
        level=level,
        pct=pct,
        avg=average,
        current_unit_usd=current,
        lowest_value=lowest_value,
        lowest_provider=(lowest_tx or {}).get("provider") or "",
        lowest_date=(lowest_tx or {}).get("date") or "",
        unit=unit,
        history_count=len(ordered),
    )


def price_alert_for_form(
    *,
    product_id: Any = "",
    product_name: Any = "",
    products: Iterable[dict[str, Any]] = (),
    history: list[dict[str, Any]],
    quantity: Any,
    bs_amount: Any,
    rate_value: Any,
    unit: Any = "unidad",
    vat_mode: str = "incluido",
) -> PriceAlert | None:
    """Cadena completa de guardas de ``updatePriceAlert``.

    La versión de referencia oculta el aviso (``box.style.display = 'none'``) si no hay SKU,
    si el monto o la tasa no son positivos, si no hay historial o si el historial
    no tiene ningún precio unitario positivo. Devolver ``None`` es el equivalente.

    >>> hist = [{"date": "2026-01-10", "quantity": 2, "amountUsd": 5},
    ...         {"date": "2026-02-10", "quantity": 2, "amountUsd": 7}]
    >>> price_alert_for_form(product_id="P1", history=hist, quantity="2",
    ...     bs_amount="220", rate_value=36.64, unit="kg").level
    'ok'
    >>> price_alert_for_form(product_id="", product_name="Café", products=[],
    ...     history=hist, quantity="2", bs_amount="220", rate_value=36.64) is None
    True
    >>> price_alert_for_form(product_id="P1", history=hist, quantity="0",
    ...     bs_amount="220", rate_value=36.64).level   # cantidad 0 → 1
    'bad'
    >>> price_alert_for_form(product_id="P1", history=hist, quantity="2",
    ...     bs_amount="", rate_value=36.64) is None
    True
    """
    pid = resolve_product_id(product_id, product_name, products)
    if not pid:
        return None

    parsed_qty = js_parse_float(quantity)
    qty = parsed_qty if (parsed_qty == parsed_qty and parsed_qty > 0) else 1.0
    bs_raw = js_parse_float_or_zero(bs_amount)
    rate = js_number_or_zero(rate_value)

    if bs_raw <= 0 or rate <= 0:
        return None

    total_bs = bs_raw * (1 + IVA_RATE) if vat_mode == "mas_iva" else bs_raw
    current_unit_usd = (total_bs / rate) / qty

    last_unit = history[-1].get("unit") if history else None
    raw_unit = unit if unit else (last_unit if last_unit else "unidad")
    return compute_price_alert(history, current_unit_usd, str(raw_unit).strip())


def price_alert_view(alert: PriceAlert) -> dict[str, str]:
    """Textos que la versión de referencia muestra en el aviso.

    La versión de referencia los envuelve en HTML; aquí se devuelven como valores sueltos
    porque la interfaz se reconstruye.

    >>> alerta = PriceAlert(LEVEL_WARN, 12.5, 2.0, 2.25, 1.5, "Mercado", "2026-01-10", "kg", 4)
    >>> view = price_alert_view(alerta)
    >>> list(view) == ["title", "current", "pct", "avg", "history", "lowest", "lowWhere", "unit"]
    True
    >>> view["current"], view["avg"], view["lowest"], view["pct"], view["history"]
    ('$ 2.2500', '$ 2.0000', '$ 1.5000', '+12.5%', '4')
    """
    return {
        "title": alert.title,
        "current": format_usd(alert.current_unit_usd, 4),
        "pct": alert.pct_label,
        "avg": format_usd(alert.avg, 4),
        "history": str(alert.history_count),
        "lowest": (
            format_usd(alert.lowest_value, 4) if alert.lowest_value is not None else "—"
        ),
        "lowWhere": alert.low_where,
        "unit": alert.unit,
    }
