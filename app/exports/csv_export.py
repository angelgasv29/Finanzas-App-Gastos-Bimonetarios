"""Exportación a CSV (``toCSV`` y ``exportCSV``, 6672-6723).

La versión de referencia genera tres CSV: transacciones, catálogo y tasas. El escapado es el
suyo: solo entrecomilla si el valor contiene coma, comilla o salto de línea, y
duplica las comillas interiores.
"""

from __future__ import annotations

from typing import Any

from ..core.text import js_to_string

__all__ = [
    "to_csv",
    "transactions_rows",
    "products_rows",
    "rates_rows",
    "transaction_headers",
    "csv_filename",
    "CSV_FILENAME_PREFIX",
    "TRANSACTION_HEADERS",
    "PRODUCT_HEADERS",
    "RATE_HEADERS",
]

TRANSACTION_HEADERS = [
    "id",
    "workspace",
    "fecha",
    "producto",
    "sku",
    "categoria",
    "cantidad",
    "unidad",
    "marca",
    "comercio",
    "metodoPago",
    "plataformaOrigen",
    "naturaleza",
    "ivaMode",
    "base",
    "iva",
    "totalBs",
    "totalUsd",
    "tasa",
    "notas",
]

PRODUCT_HEADERS = [
    "sku",
    "nombre",
    "categoriaId",
    "marca",
    "unidad",
    "subcategoria",
    "proveedor",
]

RATE_HEADERS = ["date", "value", "source"]

#: ``kind`` de ``exportCSV`` → prefijo del fichero (6709-6717).
CSV_FILENAME_PREFIX = {
    "tx": "transacciones",
    "prod": "catalogo",
    "rates": "tasas",
}


def csv_filename(kind: str, now_ms: float) -> str:
    """``<prefijo>_<YYYY-MM-DD>.csv`` con la fecha local del navegador.

    >>> csv_filename("tx", 1773577845000)
    'transacciones_2026-03-15.csv'
    """
    from ..core.periods import date_to_iso
    from ..domain.dates import local_date_at

    return f"{CSV_FILENAME_PREFIX[kind]}_{date_to_iso(local_date_at(now_ms))}.csv"


def transaction_headers(rows: list[dict[str, Any]]) -> list[str]:
    """Cabeceras del CSV de transacciones, incluidos los campos personalizados.

    La versión de referencia recoge los ``Var_*`` con un ``Set`` que conserva el orden de
    aparición (6706-6708).

    >>> transaction_headers([{"id": 1, "Var_Lote": "x"}, {"Var_Serie": "y"}])[-2:]
    ['Var_Lote', 'Var_Serie']
    """
    extra: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key.startswith("Var_") and key not in seen:
                seen.add(key)
                extra.append(key)
    return list(TRANSACTION_HEADERS) + extra


def _esc(value: Any) -> str:
    """``String(v ?? '')`` y comillas solo si hace falta."""
    text = js_to_string(value, "")
    if "," in text or '"' in text or "\n" in text:
        return '"' + text.replace('"', '""') + '"'
    return text


def to_csv(rows: list[dict[str, Any]], headers: list[str]) -> str:
    """CSV con el escapado de la versión de referencia.

    >>> to_csv([{"a": "x,y", "b": "simple"}], ["a", "b"])
    'a,b\\n"x,y",simple'
    >>> to_csv([], ["a", "b"])
    'a,b\\n'
    """
    if not rows:
        return ",".join(headers) + "\n"
    lines = [",".join(headers)]
    for row in rows:
        lines.append(",".join(_esc(row.get(header)) for header in headers))
    return "\n".join(lines)


def transactions_rows(
    txs: list[dict[str, Any]], categories: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Filas de ``exportCSV('tx')``, con las columnas de campos personalizados."""
    category_map = {category.get("id"): category for category in categories}
    rows: list[dict[str, Any]] = []
    for tx in txs:
        category = category_map.get(tx.get("categoryId"))
        row: dict[str, Any] = {
            "id": tx.get("id"),
            "workspace": tx.get("workspace"),
            "fecha": tx.get("date"),
            "producto": tx.get("productName"),
            "sku": tx.get("productId"),
            "categoria": category.get("name") if category else "",
            "cantidad": tx.get("quantity") if tx.get("quantity") is not None else "",
            "unidad": tx.get("unit") or "",
            "marca": tx.get("brand") or "",
            "comercio": tx.get("provider") or "",
            "metodoPago": tx.get("paymentMethod") or "",
            "plataformaOrigen": tx.get("originPlatform") or "",
            "naturaleza": tx.get("nature") or "",
            "ivaMode": tx.get("taxMode"),
            "base": tx.get("baseImponible"),
            "iva": tx.get("ivaMonto"),
            "totalBs": tx.get("amountBs"),
            "totalUsd": tx.get("amountUsd"),
            "tasa": tx.get("rate"),
            "notas": tx.get("notes") or "",
        }
        custom_fields = (category or {}).get("customFields") or []
        for field in custom_fields:
            values = tx.get("customValues") or {}
            value = values.get(field.get("id"), "")
            row[f"Var_{field.get('label')}"] = (
                ("Sí" if value else "No") if field.get("type") == "boolean" else value
            )
        rows.append(row)
    return rows


def products_rows(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filas de ``exportCSV('prod')``."""
    return [
        {
            "sku": product.get("id"),
            "nombre": product.get("name"),
            "categoriaId": product.get("categoryId"),
            "marca": product.get("brand") or "",
            "unidad": product.get("unit") or "",
            "subcategoria": product.get("subcategory") or "",
            "proveedor": product.get("provider") or "",
        }
        for product in products
    ]


def rates_rows(rates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filas de ``exportCSV('rates')``: todas las tasas ordenadas por fecha."""
    return [
        {
            "date": rate.get("date"),
            "value": rate.get("value"),
            "source": rate.get("source") or "",
        }
        for rate in sorted(rates, key=lambda rate: rate.get("date") or "")
    ]
