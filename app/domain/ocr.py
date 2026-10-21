"""Metadatos de SKU que hereda una importación por OCR.

Implementación de la parte con lógica del ajuste de ``batchImportOcrRows``.

Tras importar un lote de tickets por OCR, la versión de referencia **sincroniza** las
compras recién creadas con los datos del SKU al que quedaron ligadas: si la
compra no trae marca (``brand === ''``) o viene marcada como
``subcategory === 'Importado OCR'``, hereda categoría, unidad, marca,
subcategoría y comercio del catálogo. Así el lote no ensucia el histórico con
SKUs a medias.

El reconocimiento de texto es tarea del OCR; aquí sólo vive la regla de
enriquecimiento, que es pura y verificable.
"""

from __future__ import annotations

from typing import Any

__all__ = ["OCR_RATE_SOURCE", "OCR_SUBCATEGORY", "sync_ocr_sku_metadata"]

#: ``rateSource`` con el que el lote OCR marca sus transacciones.
OCR_RATE_SOURCE = "OCR·lote"

#: Subcategoría provisional que también dispara la sincronización.
OCR_SUBCATEGORY = "Importado OCR"


def sync_ocr_sku_metadata(
    transactions: list[dict[str, Any]], products: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Compras OCR enriquecidas con los datos de su SKU.

    Devuelve únicamente los registros que la versión de referencia volvería a escribir; el
    resto se deja igual. Si un campo del SKU viene vacío, se conserva el valor
    que ya tenía la transacción (``p.unit || t.unit``).

    >>> txs = [
    ...   {"id": 1, "rateSource": "OCR·lote", "productId": "p1", "brand": "",
    ...    "subcategory": "Despensa", "categoryId": "c0", "unit": "kg",
    ...    "provider": "Tienda X"},
    ...   {"id": 2, "rateSource": "OCR·lote", "productId": "p1", "brand": "PAN",
    ...    "subcategory": "Despensa"},
    ...   {"id": 3, "rateSource": "manual", "productId": "p1", "brand": ""},
    ... ]
    >>> products = [
    ...   {"id": "p1", "categoryId": "c1", "unit": "kg", "brand": "PAN",
    ...    "subcategory": "Despensa", "provider": "Excelsior Gama"},
    ... ]
    >>> updates = sync_ocr_sku_metadata(txs, products)
    >>> [tx["id"] for tx in updates]
    [1]
    >>> updates[0]["categoryId"], updates[0]["provider"]
    ('c1', 'Excelsior Gama')

    Una compra marcada como «Importado OCR» también hereda aunque ya tenga
    marca, y los campos vacíos del SKU no borran los de la compra:

    >>> txs = [{"id": 5, "rateSource": "OCR·lote", "productId": "p2",
    ...         "brand": "Otra", "subcategory": "Importado OCR",
    ...         "unit": "docena", "provider": "Abasto"}]
    >>> products = [{"id": "p2", "categoryId": "c2", "brand": "Dove",
    ...              "subcategory": "", "unit": "", "provider": ""}]
    >>> updates = sync_ocr_sku_metadata(txs, products)
    >>> updates[0]["brand"], updates[0]["subcategory"]
    ('Dove', 'Importado OCR')
    >>> updates[0]["unit"], updates[0]["provider"]
    ('docena', 'Abasto')
    """
    by_id = {product.get("id"): product for product in products}
    updates: list[dict[str, Any]] = []
    for tx in transactions:
        if tx.get("rateSource") != OCR_RATE_SOURCE or not tx.get("productId"):
            continue
        product = by_id.get(tx.get("productId"))
        if not product:
            continue
        # ``t.brand === ''`` es igualdad estricta: una marca ausente (undefined)
        # no dispara la sincronización, sólo la cadena vacía.
        if tx.get("brand") != "" and tx.get("subcategory") != OCR_SUBCATEGORY:
            continue
        updated = dict(tx)
        updated["categoryId"] = product.get("categoryId") or tx.get("categoryId")
        updated["unit"] = product.get("unit") or tx.get("unit")
        updated["brand"] = product.get("brand") or tx.get("brand")
        updated["subcategory"] = product.get("subcategory") or tx.get("subcategory")
        updated["provider"] = product.get("provider") or tx.get("provider")
        updates.append(updated)
    return updates
