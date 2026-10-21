"""Propagación del nombre de un producto a sus compras.

Implementación de la parte con lógica del ajuste de ``openProductEditor``.

Al guardar la edición de un SKU, la versión de referencia actualiza además todas las compras
de ese producto para que el nombre (y, si se cambió, la categoría) quede
coherente en el histórico. El ajuste **no** toca nada si el nombre nuevo viene
vacío, así que la guarda ``if (nName)`` es de quien llama.
"""

from __future__ import annotations

from typing import Any

__all__ = ["rename_product_transactions"]


def rename_product_transactions(
    transactions: list[dict[str, Any]],
    product_id: Any,
    new_name: str,
    new_category_id: str = "",
) -> list[dict[str, Any]]:
    """Compras del producto con el nombre (y categoría) nuevos.

    Devuelve solo los registros que la versión de referencia volvería a escribir. Es una
    función pura: no toca la base de datos.

    >>> txs = [
    ...   {"id": 1, "productId": "p1", "productName": "Harina", "categoryId": "c1"},
    ...   {"id": 2, "productId": "p2", "productName": "Arroz", "categoryId": "c1"},
    ...   {"id": 3, "productId": "p1", "productName": "Harina", "categoryId": "c1"},
    ... ]
    >>> [tx["productName"] for tx in rename_product_transactions(txs, "p1", "Harina PAN")]
    ['Harina PAN', 'Harina PAN']
    >>> [tx["categoryId"] for tx in rename_product_transactions(txs, "p1", "Harina PAN", "c9")]
    ['c9', 'c9']
    >>> rename_product_transactions(txs, "p1", "Harina PAN")[0]["id"]
    1

    Sin categoría nueva la categoría de cada compra se respeta:

    >>> rename_product_transactions(txs, "p1", "Harina PAN")[0]["categoryId"]
    'c1'
    """
    updates: list[dict[str, Any]] = []
    for tx in transactions:
        if tx.get("productId") != product_id:
            continue
        updated = dict(tx)
        updated["productName"] = new_name
        if new_category_id:
            updated["categoryId"] = new_category_id
        updates.append(updated)
    return updates
