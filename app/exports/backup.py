"""Respaldo y restauración JSON (``exportJSONBackup`` / ``importJSONBackup``).

El respaldo es un único JSON con los cinco almacenes y la configuración del
``localStorage``. La restauración decide qué hacer con cada registro igual que el
de referencia:

* las **transacciones** siempre se añaden y se les quita el ``id`` (lo asigna la
  base de datos);
* productos, categorías y cierres solo se escriben **si no existen**;
* las **tasas** se escriben siempre (``put``).

Además se porta la importación desde Excel, que crea el producto que falte y
convierte cada fila del libro mayor en una transacción.
"""

from __future__ import annotations

import json
import math
from typing import Any, Callable

from ..core.ids import new_sku
from ..core.js_locale import iso_string
from ..core.money import js_number_or_zero, js_parse_float, js_parse_int
from ..core.text import js_to_string

__all__ = [
    "BACKUP_APP",
    "BACKUP_VERSION",
    "LS_CONFIG_KEYS",
    "build_backup",
    "backup_filename",
    "backup_text",
    "is_valid_backup",
    "import_prompt",
    "import_plan",
    "import_signature",
    "dedupe_imported",
    "plan_excel_import",
]

BACKUP_APP = "GastosBimonetarios"
BACKUP_VERSION = 1

#: Claves de ``localStorage`` que viajan en el respaldo (``LS_KEYS``, 2657).
LS_CONFIG_KEYS = (
    "theme",
    "workspace",
    "fiscalYear",
    "decimals",
    "currency",
)


def _sanitize(value: Any) -> Any:
    """``JSON.stringify`` escribe ``null`` donde Python escribiría ``NaN``."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    return value


def build_backup(
    *,
    transactions: list[dict[str, Any]],
    products: list[dict[str, Any]],
    categories: list[dict[str, Any]],
    rates: list[dict[str, Any]],
    closures: list[dict[str, Any]],
    workspace: str,
    fiscal_year: Any,
    ls_config: dict[str, Any],
    now_ms: float,
) -> dict[str, Any]:
    """Estructura del respaldo (``data`` de ``exportJSONBackup``).

    >>> data = build_backup(transactions=[{"id": 1}], products=[], categories=[],
    ...                     rates=[], closures=[], workspace="personal",
    ...                     fiscal_year=2026, ls_config={"theme": "dark"},
    ...                     now_ms=1773577845123)
    >>> data["meta"]
    {'app': 'GastosBimonetarios', 'version': 1, 'exportedAt': '2026-03-15T12:30:45.123Z', 'workspace': 'personal', 'fiscalYear': 2026}
    >>> data["lsConfig"]
    {'theme': 'dark', 'workspace': None, 'fiscalYear': None, 'decimals': None, 'currency': None}
    """
    return {
        "meta": {
            "app": BACKUP_APP,
            "version": BACKUP_VERSION,
            "exportedAt": iso_string(now_ms),
            "workspace": workspace,
            "fiscalYear": fiscal_year,
        },
        "transactions": list(transactions),
        "products": list(products),
        "categories": list(categories),
        "rates": list(rates),
        "closures": list(closures),
        "lsConfig": {
            key: ls_config.get(key) for key in LS_CONFIG_KEYS
        },
    }


def backup_filename(now_ms: float) -> str:
    """``backup_gastos_<YYYY-MM-DD>.json``."""
    from ..domain.dates import local_date_at
    from ..core.periods import date_to_iso

    return f"backup_gastos_{date_to_iso(local_date_at(now_ms))}.json"


def backup_text(data: dict[str, Any]) -> str:
    """``JSON.stringify(data, null, 2)``.

    >>> backup_text({"a": [1.0, float("nan")]})
    '{\\n  "a": [\\n    1.0,\\n    null\\n  ]\\n}'
    """
    return json.dumps(_sanitize(data), indent=2, ensure_ascii=False)


def is_valid_backup(data: Any) -> bool:
    """``data.meta && data.meta.app === 'GastosBimonetarios'``.

    >>> is_valid_backup({"meta": {"app": "GastosBimonetarios"}})
    True
    >>> is_valid_backup({"meta": {"app": "otra"}})
    False
    >>> is_valid_backup(None)
    False
    """
    if not isinstance(data, dict):
        return False
    meta = data.get("meta")
    return bool(meta) and meta.get("app") == BACKUP_APP


def import_prompt(data: dict[str, Any]) -> str:
    """Texto del ``confirm`` de ``importJSONBackup``.

    >>> import_prompt({"transactions": [1, 2], "products": [], "categories": [1],
    ...                "rates": [], "closures": []})
    'Importación de respaldo\\n\\nTransacciones: 2\\nProductos: 0\\nCategorías: 1\\nTasas: 0\\nCierres: 0\\n\\n¿Continuar?'
    """
    return (
        "Importación de respaldo\n\n"
        f"Transacciones: {len(data.get('transactions') or [])}\n"
        f"Productos: {len(data.get('products') or [])}\n"
        f"Categorías: {len(data.get('categories') or [])}\n"
        f"Tasas: {len(data.get('rates') or [])}\n"
        f"Cierres: {len(data.get('closures') or [])}\n\n"
        "¿Continuar?"
    )


def import_plan(
    data: dict[str, Any],
    *,
    existing_product_ids: set[Any] | None = None,
    existing_category_ids: set[Any] | None = None,
    existing_closure_ids: set[Any] | None = None,
) -> dict[str, Any]:
    """Qué escribiría ``importJSONBackup`` (sin tocar la base de datos)."""
    products = set(existing_product_ids or ())
    categories = set(existing_category_ids or ())
    closures = set(existing_closure_ids or ())

    transactions: list[dict[str, Any]] = []
    for tx in data.get("transactions") or []:
        record = dict(tx)
        record.pop("id", None)
        transactions.append(record)

    new_products = [
        product
        for product in (data.get("products") or [])
        if product.get("id") not in products
    ]
    new_categories = [
        category
        for category in (data.get("categories") or [])
        if category.get("id") not in categories
    ]
    new_rates = list(data.get("rates") or [])
    new_closures = [
        closure
        for closure in (data.get("closures") or [])
        if closure.get("id") not in closures
    ]

    return {
        "transactions": transactions,
        "products": new_products,
        "categories": new_categories,
        "rates": new_rates,
        "closures": new_closures,
        "count": len(transactions),
    }


#: Campos que forman la firma anti-duplicados del ajuste.
SIGNATURE_KEYS = ("workspace", "date", "productName", "amountBs")


def import_signature(tx: dict[str, Any]) -> str:
    """``${x.workspace}|${x.date}|${x.productName}|${x.amountBs}``.

    La plantilla de JavaScript escribe ``undefined`` para un campo ausente y
    ``null`` para un campo nulo; aquí se replica el caso ausente.

    >>> import_signature({"workspace": "personal", "date": "2026-01-01",
    ...                   "productName": "Harina", "amountBs": 100})
    'personal|2026-01-01|Harina|100'
    >>> import_signature({})
    'undefined|undefined|undefined|undefined'
    """
    return "|".join(js_to_string(tx.get(key), "undefined") for key in SIGNATURE_KEYS)


def dedupe_imported(
    existing: list[dict[str, Any]], after: list[dict[str, Any]]
) -> list[Any]:
    """Identificadores que el ajuste borra tras importar.

    Una vez importado el respaldo, la versión de referencia elimina toda transacción **nueva**
    cuya firma coincida con una ya vista. La primera aparición de cada firma se
    conserva (sea previa o recién importada).

    >>> existing = [{"id": 55, "workspace": "personal", "date": "2026-01-01",
    ...              "productName": "Harina", "amountBs": 100}]
    >>> after = existing + [
    ...   {"id": 1001, "workspace": "personal", "date": "2026-01-01", "productName": "Harina", "amountBs": 100},
    ...   {"id": 1002, "workspace": "personal", "date": "2026-01-02", "productName": "Arroz", "amountBs": 200},
    ...   {"id": 1003, "workspace": "personal", "date": "2026-01-02", "productName": "Arroz", "amountBs": 200},
    ... ]
    >>> dedupe_imported(existing, after)
    [1001, 1003]
    """
    seen = {import_signature(tx) for tx in existing}
    existing_ids = {tx.get("id") for tx in existing}
    to_delete: list[Any] = []
    for tx in after:
        signature = import_signature(tx)
        if signature in seen and tx.get("id") not in existing_ids:
            to_delete.append(tx.get("id"))
        else:
            seen.add(signature)
    return to_delete


def _sheet_value(row: dict[str, Any], *keys: str) -> Any:
    """``r['Clave'] || r.Clave`` (SheetJS entrega el nombre con acentos o con ``_``)."""
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def plan_excel_import(
    rows: list[dict[str, Any]],
    *,
    products: list[dict[str, Any]],
    categories: list[dict[str, Any]],
    workspace: str,
    fiscal_year: Any,
    now_ms: float,
    app_rate_value: float | None = None,
    sku_factory: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Convierte las filas del «Libro Mayor» en productos y transacciones.

    Reglas de la versión de referencia: se descartan las filas sin fecha, sin producto o con
    ``Total Bs <= 0``; el producto se busca por nombre (sin distinguir
    mayúsculas) y, si no existe, se crea con un SKU nuevo y la primera categoría
    como categoría por defecto.
    """
    make_sku = sku_factory or (lambda: new_sku(workspace))
    known = list(products)
    default_category = (categories[0] or {}).get("id", "") if categories else ""

    new_products: list[dict[str, Any]] = []
    transactions: list[dict[str, Any]] = []

    for row in rows:
        fecha = _sheet_value(row, "Fecha", "fecha")
        prod = _sheet_value(row, "Producto", "producto")
        total_bs = js_number_or_zero(
            _sheet_value(row, "Total Bs", "Total_Bs", "totalBs")
        )
        if not fecha or not prod or total_bs <= 0:
            continue
        date_str = js_to_string(fecha, "")[:10]
        raw_rate = _sheet_value(row, "Tasa Bs/USD", "tasa", "Tasa_Bs_USD")
        if raw_rate:
            rate = js_parse_float(raw_rate)
        else:
            rate = js_parse_float(app_rate_value) if app_rate_value else 1

        product_id = ""
        name = js_to_string(prod, "")
        for candidate in known:
            if (candidate.get("name") or "").lower() == name.lower():
                product_id = candidate.get("id")
                break
        if not product_id:
            product_id = make_sku()
            created = {
                "id": product_id,
                "workspace": workspace,
                "name": name,
                "name_lower": name.lower(),
                "categoryId": default_category,
                "brand": _sheet_value(row, "Marca", "marca") or "",
                "unit": _sheet_value(row, "Unidad", "unidad") or "unidad",
                "subcategory": _sheet_value(row, "Subcategoría", "subcategoria") or "",
                "provider": _sheet_value(row, "Comercio", "comercio") or "",
                "createdAt": now_ms,
                "updatedAt": now_ms,
            }
            new_products.append(created)
            known.append(created)

        total_usd = js_number_or_zero(
            _sheet_value(row, "Total USD", "totalUsd", "Total_USD")
        ) or (total_bs / rate if rate else 0)

        transactions.append(
            {
                "workspace": workspace,
                "year": js_parse_int(date_str[:4]) or fiscal_year,
                "date": date_str,
                "productId": product_id,
                "productName": name,
                "categoryId": default_category,
                "quantity": _number_or_none(_sheet_value(row, "Cantidad", "cantidad")),
                "unit": _sheet_value(row, "Unidad", "unidad") or "",
                "brand": _sheet_value(row, "Marca", "marca") or "",
                "subcategory": _sheet_value(row, "Subcategoría", "subcategoria") or "",
                "provider": _sheet_value(row, "Comercio", "comercio") or "",
                "paymentMethod": _sheet_value(
                    row, "Método de Pago", "metodoPago", "Método_de_Pago"
                )
                or "",
                "originPlatform": _sheet_value(
                    row, "Plataforma Origen", "plataformaOrigen", "Plataforma_Origen"
                )
                or "",
                "nature": _sheet_value(row, "Naturaleza", "naturaleza") or "",
                "taxMode": (
                    "exento"
                    if (js_to_string(_sheet_value(row, "Modalidad IVA", "ivaMode"), "")
                        .lower()
                        == "exento")
                    else "incluido"
                ),
                "baseImponible": js_number_or_zero(
                    _sheet_value(row, "Base Imponible Bs", "base")
                ),
                "ivaMonto": js_number_or_zero(
                    _sheet_value(row, "IVA Bs", "iva", "IVA_Bs")
                ),
                "amountBs": total_bs,
                "amountUsd": total_usd,
                "rate": rate,
                "rateDate": date_str,
                "rateSource": "import",
                "customValues": {},
                "notes": _sheet_value(row, "Notas", "notas") or "",
                "createdAt": now_ms,
                "updatedAt": now_ms,
            }
        )

    return {
        "products": new_products,
        "transactions": transactions,
        "count": len(transactions),
    }


def _number_or_none(value: Any) -> Any:
    """``Number(v) || null`` (``NaN`` y ``0`` se convierten en ``None``)."""
    number = js_parse_float(value)
    if number == 0 or math.isnan(number):
        return None
    return number
