"""Filtros y orden de la lista de movimientos.

Implementación del filtrado de ``renderTxList``.

La versión de referencia construye una cadena con todos los campos buscables de cada
transacción, la pasa a minúsculas y comprueba ``includes(q)``. Se replica tal
cual, **incluido el orden de los campos**, porque el resultado de una búsqueda
puede depender de él en casos raros (por ejemplo, una consulta que cruce dos
campos).
"""

from __future__ import annotations

from typing import Any

from ..core.text import js_to_string

__all__ = ["filter_transactions", "sort_transactions_desc", "search_haystack"]

# Campos que la versión de referencia concatena para la búsqueda, en su orden.
_SEARCH_FIELDS = (
    "productName",
    "brand",
    "provider",
    "subcategory",
    "paymentMethod",
    "originPlatform",
    "notes",
)


def search_haystack(tx: dict[str, Any], category_name: str = "") -> str:
    """Texto sobre el que busca el cuadro de búsqueda, en minúsculas.

    >>> tx = {"productName": "Harina PAN", "brand": "PAN", "date": "2026-03-15",
    ...       "customValues": {"presentacion": "1kg", "peso": 1}}
    >>> search_haystack(tx, "Alimentación")
    'harina pan pan      alimentación 1kg 1 2026-03-15'

    Los espacios de más son los de los campos vacíos: la versión de referencia los une con
    ``join(' ')`` sin filtrar, y se conservan para que una búsqueda con espacios
    internos se comporte igual.
    """
    values: list[str] = [js_to_string(tx.get(field)) for field in _SEARCH_FIELDS]

    values.append(category_name)

    custom = tx.get("customValues")
    if custom:
        # ``Object.values(...).join(' ')``: mismos valores, mismo orden de
        # inserción y ``null``/``undefined`` como cadena vacía.
        values.append(" ".join(js_to_string(value) for value in custom.values()))

    values.append(js_to_string(tx.get("date")))
    return " ".join(values).lower()


def filter_transactions(
    txs: list[dict[str, Any]],
    *,
    query: str = "",
    nature: str = "",
    tax: str = "",
    categories: Any = None,
) -> list[dict[str, Any]]:
    """Aplica los filtros de la lista de movimientos.

    :param query: texto libre (se busca en :func:`search_haystack`).
    :param nature: ``'Recurrente'``/``'Extraordinario'``, o ``''``.
    :param tax: ``'exento'`` (solo exentos), ``'incluido'`` (todos menos los
        exentos) o ``''``. La versión de referencia usa esa nomenclatura aunque signifique
        "con IVA", no "IVA incluido".
    :param categories: iterable de categorías o ``{id: categoría}``.

    >>> txs = [
    ...     {"id": 1, "productName": "Harina", "taxMode": "exento", "nature": "Recurrente",
    ...      "date": "2026-03-15", "categoryId": "c1"},
    ...     {"id": 2, "productName": "Arroz", "taxMode": "incluido", "nature": "Extraordinario",
    ...      "date": "2026-03-16", "categoryId": "c1"},
    ... ]
    >>> [t["id"] for t in filter_transactions(txs, tax="exento")]
    [1]
    >>> [t["id"] for t in filter_transactions(txs, tax="incluido")]
    [2]
    >>> [t["id"] for t in filter_transactions(txs, nature="Recurrente")]
    [1]
    >>> [t["id"] for t in filter_transactions(txs, query="arr")]
    [2]
    >>> cats = [{"id": "c1", "name": "Alimentación"}]
    >>> [t["id"] for t in filter_transactions(txs, query="ALIMENT", categories=cats)]
    [1, 2]
    """
    if isinstance(categories, dict):
        cat_map = categories
    else:
        cat_map = {cat["id"]: cat for cat in (categories or [])}

    needle = (query or "").lower().strip()
    result: list[dict[str, Any]] = []

    for tx in txs:
        if nature and tx.get("nature") != nature:
            continue
        if tax == "exento" and tx.get("taxMode") != "exento":
            continue
        if tax == "incluido" and tx.get("taxMode") == "exento":
            continue
        if needle:
            category = cat_map.get(tx.get("categoryId"))
            haystack = search_haystack(tx, (category or {}).get("name") or "")
            if needle not in haystack:
                continue
        result.append(tx)

    return result


def sort_transactions_desc(txs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Orden de la lista: fecha descendente y, a igual fecha, ``id`` descendente.

    Referencia::

        filtered.sort((a,b) => (b.date||'').localeCompare(a.date||'') || (b.id-a.id));

    Con fechas ISO, ``localeCompare`` coincide con la comparación de caracteres.

    >>> txs = [{"id": 1, "date": "2026-03-15"}, {"id": 9, "date": "2026-03-15"},
    ...        {"id": 3, "date": "2026-04-01"}, {"id": 4}]
    >>> [(t["id"], t.get("date")) for t in sort_transactions_desc(txs)]
    [(3, '2026-04-01'), (9, '2026-03-15'), (1, '2026-03-15'), (4, None)]
    """
    return sorted(
        txs,
        key=lambda tx: ((tx.get("date") or ""), tx.get("id") or 0),
        reverse=True,
    )
