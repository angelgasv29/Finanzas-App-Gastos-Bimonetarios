"""Reglas de las transacciones: alta, edición y recálculo bidireccional.

Implementación del formulario de registro (líneas 3800-3832 y 3927-3994) y del editor.

Aquí no hay DOM. Cada función recibe los valores ya leídos de los campos y
devuelve datos; la interfaz se limita a escribirlos. Las dos funciones que en el
de referencia escriben directamente en un ``<input>`` (``recalcBsUsd`` y el
``wireEditRecalc`` del editor) devuelven un diccionario ``id del campo → valor``
para que el resultado sea verificable sin navegador.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from ..core.ids import new_sku, now_ms
from ..core.money import (
    js_number_or_zero,
    js_parse_float,
    js_parse_int,
    js_round,
    js_to_fixed,
)
from .errors import MissingRateError, ValidationError
from .rates import rate_value_of
from .vat import DEFAULT_VAT_MODE, compute_vat

__all__ = [
    "validate",
    "require_rate",
    "resolve_product",
    "build_transaction",
    "apply_edit",
    "resolve_edited_bs",
    "recalc_bs_usd",
    "editor_recalc",
    "repeat_transaction",
    "DEFAULT_UNIT",
]

# ``unit: $('#txUnit')?.value || 'unidad'``.
DEFAULT_UNIT = "unidad"


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------


def validate(
    category_id: Any, date: Any, product_name: Any, bs_amount: Any
) -> None:
    """Comprueba los cuatro campos obligatorios.

    Referencia::

        if (!catId || !date || !productName || bs <= 0) {
          toast('Completa los campos obligatorios.', 'warn'); return; }

    >>> validate("cat_1", "2026-03-15", "Harina", 116)
    >>> validate("", "2026-03-15", "Harina", 116)
    Traceback (most recent call last):
    app.domain.errors.ValidationError: Completa los campos obligatorios.
    >>> validate("cat_1", "2026-03-15", "Harina", 0)
    Traceback (most recent call last):
    app.domain.errors.ValidationError: Completa los campos obligatorios.
    """
    amount = js_number_or_zero(bs_amount)
    if not category_id or not date or not product_name or amount <= 0:
        raise ValidationError(
            "Completa los campos obligatorios.", level="warn"
        )


def require_rate(rate: dict[str, Any] | None) -> None:
    """Exige una tasa utilizable.

    >>> require_rate({"value": 36.64})
    >>> require_rate({"value": 0})
    Traceback (most recent call last):
    app.domain.errors.MissingRateError: No hay tasa disponible. Añádela en Tasas.
    >>> require_rate(None)
    Traceback (most recent call last):
    app.domain.errors.MissingRateError: No hay tasa disponible. Añádela en Tasas.
    """
    if not rate or not rate.get("value"):
        raise MissingRateError(
            "No hay tasa disponible. Añádela en Tasas.", level="err"
        )


# ---------------------------------------------------------------------------
# Catálogo de productos
# ---------------------------------------------------------------------------


def resolve_product(
    products: list[dict[str, Any]],
    workspace: str,
    name: str,
    *,
    category_id: str | None = None,
    brand: str = "",
    unit: str = "",
    subcategory: str = "",
    provider: str = "",
    product_id: str | None = None,
    id_factory: Callable[[str], str] | None = None,
    sku_factory: Callable[[str], str] | None = None,
    timestamp: int | None = None,
) -> tuple[str | None, dict[str, Any] | None]:
    """Decide el ``productId`` y, si hace falta, crea el producto.

    Devuelve ``(product_id, producto_nuevo)``. El producto nuevo también se
    devuelve para que quien llama lo guarde (la versión de referencia hace ``DB.put`` y
    ``APP.products.push``).

    Referencia::

        let productId = $('#txProductId').value.trim();
        const existing = APP.products.find(p => p.name.toLowerCase() === productName.toLowerCase());
        if (!existing && !productId) { ...crear... }
        else if (existing) { productId = existing.id; }

    >>> productos = [{"id": "PROD-P-A", "name": "Harina PAN"}]
    >>> resolve_product(productos, "personal", "harina pan")
    ('PROD-P-A', None)
    >>> nuevo_id, nuevo = resolve_product(productos, "personal", "Arroz",
    ...     category_id="cat_1", sku_factory=lambda ws: "PROD-P-XXX", timestamp=7)
    >>> nuevo_id, nuevo["name_lower"], nuevo["unit"], nuevo["createdAt"]
    ('PROD-P-XXX', 'arroz', 'unidad', 7)
    >>> resolve_product(productos, "personal", "Otro", product_id="PROD-P-B")
    ('PROD-P-B', None)
    """
    make_sku = sku_factory or new_sku
    stamp = timestamp if timestamp is not None else now_ms()
    wanted = (name or "").lower()

    existing = None
    for product in products:
        if (product.get("name") or "").lower() == wanted:
            existing = product
            break

    if existing is None and not product_id:
        created = {
            "id": make_sku(workspace),
            "workspace": workspace,
            "name": name,
            "name_lower": wanted,
            "categoryId": category_id,
            "brand": brand or "",
            "unit": unit or DEFAULT_UNIT,
            "subcategory": subcategory or "",
            "provider": provider or "",
            "createdAt": stamp,
            "updatedAt": stamp,
        }
        return created["id"], created

    if existing is not None:
        return existing["id"], None

    return product_id, None


# ---------------------------------------------------------------------------
# Alta
# ---------------------------------------------------------------------------


def _text(value: Any) -> str:
    """``(x || '').trim()`` — texto sin espacios, nunca ``None``."""
    return str(value).strip() if value is not None else ""


def _parse_float_or_null(value: Any) -> float | None:
    """``parseFloat(x) || null``: el ``0`` y el ``NaN`` se guardan como ``null``.

    >>> _parse_float_or_null("2.5")
    2.5
    >>> _parse_float_or_null("0") is None
    True
    >>> _parse_float_or_null("") is None
    True
    """
    parsed = js_parse_float(value)
    if math.isnan(parsed) or not parsed:
        return None
    return parsed


def build_transaction(
    *,
    workspace: str,
    date: str,
    category_id: str,
    product_name: str,
    rate: dict[str, Any],
    bs_amount: Any,
    mode: str = DEFAULT_VAT_MODE,
    product_id: str | None = None,
    quantity: Any = None,
    unit: Any = None,
    brand: Any = None,
    subcategory: Any = None,
    provider: Any = None,
    payment_method: Any = None,
    origin_platform: Any = None,
    nature: Any = None,
    custom_values: dict[str, Any] | None = None,
    notes: Any = None,
    timestamp: int | None = None,
) -> dict[str, Any]:
    """Construye el registro que se escribirá en ``transactions``.

    Mismas claves y mismo orden que el objeto ``tx`` de la versión de referencia, para que el
    repositorio lo acepte sin traducción.

    >>> tx = build_transaction(workspace="personal", date="2026-03-15",
    ...     category_id="cat_1", product_name="Harina", rate={"value": 36.64,
    ...     "date": "2026-03-15", "source": "BCV"}, bs_amount=116, timestamp=1)
    >>> tx["year"], tx["baseImponible"], tx["ivaMonto"], tx["amountBs"]
    (2026, 100.0, 16.0, 116.0)
    >>> tx["amountUsd"], tx["rateSource"], tx["unit"], tx["quantity"]
    (3.1659, 'BCV', '', None)

    El USD se calcula con el total **sin redondear**, como ``const usd = total /
    rateVal`` de la versión de referencia; el Bs guardado sí va redondeado a 2.

    >>> otro = build_transaction(workspace="personal", date="2026-03-15",
    ...     category_id="cat_1", product_name="Harina",
    ...     rate={"value": 1, "date": "2026-03-15", "source": "BCV"},
    ...     bs_amount=100.01, mode="mas_iva", timestamp=1)
    >>> otro["amountBs"], otro["amountUsd"]
    (116.01, 116.0116)
    """
    require_rate(rate)
    stamp = timestamp if timestamp is not None else now_ms()

    amounts = compute_vat(bs_amount, mode)
    rate_val = rate_value_of(rate)
    usd = amounts.total / rate_val

    return {
        "workspace": workspace,
        "year": _year_of(date),
        "date": date,
        "productId": product_id,
        "productName": product_name,
        "categoryId": category_id,
        # ``parseFloat(...)||null``: 0 y NaN se guardan como null.
        "quantity": _parse_float_or_null(quantity),
        "unit": _text(unit),
        "brand": _text(brand),
        "subcategory": _text(subcategory),
        "provider": _text(provider),
        "paymentMethod": _text(payment_method),
        "originPlatform": _text(origin_platform),
        "nature": _text(nature),
        "taxMode": mode,
        "baseImponible": js_round(amounts.base, 2),
        "ivaMonto": js_round(amounts.iva, 2),
        "amountBs": js_round(amounts.total, 2),
        "amountUsd": js_round(usd, 4),
        "rate": rate_val,
        "rateDate": rate.get("date") or date,
        "rateSource": rate.get("source") or "",
        "customValues": custom_values if custom_values is not None else {},
        "notes": _text(notes),
        "createdAt": stamp,
        "updatedAt": stamp,
    }


def _year_of(date: str) -> int:
    """``parseInt(date.slice(0,4), 10)``.

    >>> _year_of("2026-03-15")
    2026
    >>> _year_of("sin-fecha")   # la versión de referencia guardaría NaN aquí
    0
    """
    year = js_parse_int(date[:4] if date else "", 10)
    if math.isnan(year) or not math.isfinite(year):
        return 0  # defensivo: `year` es NOT NULL en el esquema
    return int(year)


# ---------------------------------------------------------------------------
# Edición — Bug #2
# ---------------------------------------------------------------------------


def resolve_edited_bs(bs: Any, usd: Any, rate_value: Any) -> float:
    """Reconstruye el Bs editado desde el USD (Bug #2, líneas 4361-4366).

    Referencia::

        let bs = parseFloat($('#etxBs').value) || 0;
        if (rateVal > 0 && usdEdited > 0) {
          const bsFromUsd = usdEdited * rateVal;
          if (Math.abs(bs - bsFromUsd) > 0.01) bs = bsFromUsd;
        }

    El USD es la "verdad editada" si difiere del Bs en más de un céntimo.

    >>> resolve_edited_bs(116, 3.1659, 36.64)
    116.0
    >>> round(resolve_edited_bs(116, 10, 36.64), 2)
    366.4
    >>> resolve_edited_bs(116, 0, 36.64)
    116.0
    """
    amount_bs = js_number_or_zero(bs)
    usd_edited = js_number_or_zero(usd)
    rate = js_number_or_zero(rate_value)
    if rate > 0 and usd_edited > 0:
        from_usd = usd_edited * rate
        if abs(amount_bs - from_usd) > 0.01:
            return from_usd
    return amount_bs


def apply_edit(
    tx: dict[str, Any],
    *,
    date: str,
    product_name: str,
    bs_amount: Any,
    usd_amount: Any,
    mode: str,
    rate_value: Any,
    quantity: Any = None,
    unit: Any = None,
    brand: Any = None,
    provider: Any = None,
    origin_platform: Any = None,
    notes: Any = None,
    custom_values: dict[str, Any] | None = None,
    timestamp: int | None = None,
) -> dict[str, Any]:
    """Aplica los cambios del editor sobre una transacción existente.

    La versión de referencia hace ``{...tx, ...overrides}``: se conserva todo lo que no se
    toca (``createdAt``, ``categoryId``, ``subcategory``…).

    >>> base = {"id": 7, "createdAt": 1, "categoryId": "cat_1", "subcategory": "x",
    ...         "amountBs": 100.0, "amountUsd": 2.5}
    >>> out = apply_edit(base, date="2026-04-01", product_name="Arroz",
    ...     bs_amount=232, usd_amount=232/40, mode="incluido", rate_value=40,
    ...     timestamp=99)
    >>> out["id"], out["createdAt"], out["categoryId"], out["subcategory"]
    (7, 1, 'cat_1', 'x')
    >>> out["amountBs"], out["baseImponible"], out["ivaMonto"], out["amountUsd"]
    (232.0, 200.0, 32.0, 5.8)

    Igual que la versión de referencia, el USD sale del total sin redondear:

    >>> otro = apply_edit(base, date="2026-04-01", product_name="Arroz",
    ...     bs_amount=100.01, usd_amount=0, mode="mas_iva", rate_value=1)
    >>> otro["amountBs"], otro["amountUsd"]
    (116.01, 116.0116)
    """
    stamp = timestamp if timestamp is not None else now_ms()
    rate = js_number_or_zero(rate_value) or js_number_or_zero(tx.get("rate"))
    bs = resolve_edited_bs(bs_amount, usd_amount, rate)

    amounts = compute_vat(bs, mode)

    updated = dict(tx)
    updated.update(
        {
            "date": date,
            "year": _year_of(date),
            "productName": _text(product_name),
            "amountBs": js_round(amounts.total, 2),
            "amountUsd": js_round(amounts.total / rate if rate else 0, 4),
            "baseImponible": js_round(amounts.base, 2),
            "ivaMonto": js_round(amounts.iva, 2),
            "taxMode": mode,
            "rate": rate,
            "quantity": _parse_float_or_null(quantity),
            "unit": _text(unit) or tx.get("unit"),
            "brand": _text(brand) or tx.get("brand"),
            "provider": _text(provider) or tx.get("provider"),
            "originPlatform": (
                _text(origin_platform)
                if origin_platform is not None
                else (tx.get("originPlatform") or "")
            ),
            "notes": _text(notes),
            "customValues": custom_values if custom_values is not None else {},
            "updatedAt": stamp,
        }
    )
    return updated


# ---------------------------------------------------------------------------
# Conversión bidireccional (líneas 3800-3812 y 4330-4354)
# ---------------------------------------------------------------------------


def recalc_bs_usd(
    source: str, bs_value: Any, usd_value: Any, rate_value: Any
) -> dict[str, str | None]:
    """``recalcBsUsd(source)``: recalcula el campo contrario.

    Devuelve ``{'txAmountBs': …, 'txAmountUsd': …}`` con el valor nuevo de cada
    campo, o ``None`` en el que no cambia. Es una **cadena**: la versión de referencia escribe
    ``toFixed(4)`` en USD y ``toFixed(2)`` en Bs.

    >>> recalc_bs_usd("bs", "116", "", 36.64)
    {'txAmountBs': None, 'txAmountUsd': '3.1659'}
    >>> recalc_bs_usd("usd", "", "10", 36.64)
    {'txAmountBs': '366.40', 'txAmountUsd': None}
    >>> recalc_bs_usd("bs", "abc", "", 36.64)   # NaN ⇒ campo vacío
    {'txAmountBs': None, 'txAmountUsd': ''}
    >>> recalc_bs_usd("bs", "116", "", 0)       # sin tasa no se toca nada
    {'txAmountBs': None, 'txAmountUsd': None}
    """
    rate = js_number_or_zero(rate_value)
    if not rate:
        return {"txAmountBs": None, "txAmountUsd": None}

    if source == "bs":
        parsed = js_parse_float(bs_value)
        if math.isnan(parsed):
            return {"txAmountBs": None, "txAmountUsd": ""}
        return {"txAmountBs": None, "txAmountUsd": js_to_fixed(parsed / rate, 4)}

    if source == "usd":
        parsed = js_parse_float(usd_value)
        if math.isnan(parsed):
            return {"txAmountBs": "", "txAmountUsd": None}
        return {"txAmountBs": js_to_fixed(parsed * rate, 2), "txAmountUsd": None}

    return {"txAmountBs": None, "txAmountUsd": None}


def editor_recalc(
    field: str, bs_value: Any, usd_value: Any, rate_value: Any
) -> dict[str, str | None]:
    """Recálculo bidireccional del modal de edición.

    El editor tiene **tres** campos y se recalcula al editar cualquiera:

    - ``bs``   → recalcula el USD con ``toFixed(4)``.
    - ``usd``  → recalcula el Bs con ``toFixed(2)``.
    - ``rate`` → mantiene el **USD** como verdad y recalcula el Bs.

    A diferencia del formulario, aquí el guardia es ``r > 0``: si la tasa es 0 o
    negativa no se escribe nada.

    >>> editor_recalc("bs", "116", "", 36.64)
    {'txAmountBs': None, 'txAmountUsd': '3.1659'}
    >>> editor_recalc("rate", "", "10", 40)
    {'txAmountBs': '400.00', 'txAmountUsd': None}
    >>> editor_recalc("usd", "", "10", -1)
    {'txAmountBs': None, 'txAmountUsd': None}
    """
    rate = js_number_or_zero(rate_value)
    if rate <= 0:
        return {"txAmountBs": None, "txAmountUsd": None}

    if field == "bs":
        parsed = js_parse_float(bs_value)
        if math.isnan(parsed):
            return {"txAmountBs": None, "txAmountUsd": None}
        return {"txAmountBs": None, "txAmountUsd": js_to_fixed(parsed / rate, 4)}

    if field == "rate":
        # "Al cambiar la tasa mantenemos el USD como verdad y recalculamos Bs".
        parsed = js_parse_float(usd_value)
        if math.isnan(parsed):
            return {"txAmountBs": None, "txAmountUsd": None}
        return {"txAmountBs": js_to_fixed(parsed * rate, 2), "txAmountUsd": None}

    if field == "usd":
        parsed = js_parse_float(usd_value)
        if math.isnan(parsed):
            return {"txAmountBs": None, "txAmountUsd": None}
        return {"txAmountBs": js_to_fixed(parsed * rate, 2), "txAmountUsd": None}

    return {"txAmountBs": None, "txAmountUsd": None}


# ---------------------------------------------------------------------------
# Repetir compra
# ---------------------------------------------------------------------------


def repeat_transaction(
    tx: dict[str, Any], today: str, unit_options: tuple[str, ...] = ()
) -> dict[str, Any]:
    """Clona los metadatos de una compra para volver a registrarla.

    Deja la fecha en **hoy** y vacía los montos: en la versión de referencia el formulario se
    rellena pero el usuario debe teclear el importe.

    Devuelve los valores del formulario y el aviso de unidad normalizada.

    >>> tx = {"id": 3, "productId": "PROD-P-A", "productName": "Harina",
    ...       "categoryId": "cat_1", "quantity": 2, "unit": "kg", "brand": "PAN"}
    >>> r = repeat_transaction(tx, "2026-10-17", ("unidad", "kg"))
    >>> r["date"], r["productName"], r["productId"], r["quantity"]
    ('2026-10-17', 'Harina', 'PROD-P-A', 2)
    >>> r["hint"]
    'Compra clonada de #3 · SKU <span class="mono">PROD-P-A</span>'
    """
    unit = tx.get("unit")
    warning = None
    if unit and unit_options and unit not in unit_options:
        warning = unit
        unit = unit_options[0]

    quantity = tx.get("quantity")
    return {
        "date": today,
        "productName": tx.get("productName") or "",
        "productId": tx.get("productId") or "",
        "categoryId": tx.get("categoryId"),
        "quantity": quantity if quantity not in (None, "") else "",
        "unit": unit or "",
        "brand": tx.get("brand") or "",
        "provider": tx.get("provider") or "",
        "subcategory": tx.get("subcategory") or "",
        "originPlatform": tx.get("originPlatform") or "",
        "paymentMethod": tx.get("paymentMethod") or "",
        "nature": tx.get("nature") or "",
        "notes": tx.get("notes") or "",
        "taxMode": tx.get("taxMode") or DEFAULT_VAT_MODE,
        "unitWarning": warning,
        "hint": (
            f'Compra clonada de #{tx.get("id")} · SKU '
            f'<span class="mono">{tx.get("productId") or "—"}</span>'
        ),
    }
