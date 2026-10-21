"""Repositorio: acceso a datos con la misma API que el objeto ``DB`` de referencia.

Reemplaza ``DB`` (líneas 2824-2839 de la referencia). Mantener los
mismos nombres de método (``add``, ``put``, ``get``, ``all``, ``count``,
``delete``, ``clear``, ``queryByIndex``) hace que el implementación del resto del
archivo —que llama a ``DB.queryByIndex(...)`` constantemente— sea casi mecánico.

**Orden de resultados.** IndexedDB devuelve los registros ordenados por la clave
(o por la clave del índice). Se replica: ``all`` ordena por la clave primaria y
``query_by_index`` por las columnas del índice y después por la clave primaria.
Es importante porque algunas funciones de la versión de referencia dependen del orden para
desempatar.
"""

from __future__ import annotations

import json
import math
import sqlite3
from typing import Any, Iterable

from ..core.ids import now_ms
from .db import Database
from .models import (
    AUTO_INCREMENT_STORES,
    FIELD_DEFAULTS,
    INDEX_MAP,
    JSON_FIELDS,
    PRIMARY_KEY,
    STORE_FIELDS,
    STORES,
    TIMESTAMP_FIELDS,
)

__all__ = ["Repository"]

# Valor por defecto de cada campo JSON cuando el registro no lo trae.
JSON_DEFAULTS: dict[tuple[str, str], Any] = {
    (store, field): FIELD_DEFAULTS[store].get(field)
    for store in FIELD_DEFAULTS
    for field in JSON_FIELDS[store]
}


def _clean_number(value: Any) -> Any:
    """Convierte ``NaN`` en ``NULL`` y deja el resto igual.

    IndexedDB conserva ``NaN``; SQLite lo guarda como ``NULL``. Se hace explícito
    para que el comportamiento no dependa del controlador.
    """
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _dump(store: str, record: dict[str, Any], full: bool = False) -> dict[str, Any]:
    """Convierte un registro de la versión de referencia en una fila de SQLite.

    Con ``full=False`` solo se incluyen las columnas presentes en el registro, de
    modo que las ausentes tomen los ``DEFAULT`` del esquema (es el caso de una
    inserción). Con ``full=True`` se rellenan todas las columnas: es lo que
    necesita :meth:`Repository.put` para **reemplazar** el registro entero, igual
    que ``IndexedDB.put``.
    """
    fields = STORE_FIELDS[store]
    json_fields = JSON_FIELDS[store]
    defaults = FIELD_DEFAULTS[store]

    row: dict[str, Any] = {}
    for field in fields:
        if field in record:
            value = record[field]
        elif full and field in defaults:
            value = defaults[field]
        else:
            continue

        if field in json_fields:
            if value is None:
                value = JSON_DEFAULTS.get((store, field))
            row[field] = json.dumps(value, ensure_ascii=False)
        else:
            row[field] = _clean_number(value)

    for field in TIMESTAMP_FIELDS[store]:
        row.setdefault(field, now_ms())

    return row


def _load(store: str, row: sqlite3.Row) -> dict[str, Any]:
    """Convierte una fila de SQLite en un registro igual a los de la versión de referencia."""
    json_fields = JSON_FIELDS[store]
    result: dict[str, Any] = {}
    for key in row.keys():
        value = row[key]
        if key in json_fields and value is not None:
            try:
                value = json.loads(value)
            except (TypeError, ValueError):
                value = None
        result[key] = value
    return result


class Repository:
    """Acceso a los 5 almacenes y a la configuración.

    >>> import tempfile
    >>> from pathlib import Path
    >>> from app.data.db import Database
    >>> repo = Repository(Database(Path(tempfile.mkdtemp()) / 'r.sqlite3').initialize())
    >>> _ = repo.put('categories', {'id': 'cat_1', 'workspace': 'personal', 'name': 'Comida'})
    >>> repo.get('categories', 'cat_1')['name']
    'Comida'
    >>> len(repo.query_by_index('categories', 'workspace', 'personal'))
    1
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------

    def add(self, store: str, record: dict[str, Any]) -> Any:
        """Inserta un registro nuevo. Devuelve su clave.

        Equivale a ``DB.add``. En ``transactions`` la clave la asigna la base de
        datos (autoincrement), igual que en la versión de referencia.
        """
        data = _dump(store, record)
        key_field = PRIMARY_KEY[store]

        if store in AUTO_INCREMENT_STORES:
            data.pop("id", None)  # la base de datos asigna el id

        columns = list(data)
        placeholders = ", ".join("?" for _ in columns)
        sql = (
            f"INSERT INTO {store} ({', '.join(columns)}) VALUES ({placeholders})"
        )
        cursor = self.db.execute(sql, [data[c] for c in columns])

        if store in AUTO_INCREMENT_STORES:
            return cursor.lastrowid
        return data.get(key_field)

    def put(self, store: str, record: dict[str, Any]) -> Any:
        """Inserta o **reemplaza** por clave primaria. Equivale a ``DB.put``.

        Igual que ``IndexedDB.put``, el registro sustituye al anterior por
        completo: las propiedades que no vengan vuelven a su valor por defecto.
        La versión de referencia nunca guarda registros parciales, y esta semántica obliga a
        que esta implementación tampoco lo haga.

        >>> import tempfile
        >>> from pathlib import Path
        >>> from app.data.db import Database as _DB
        >>> repo = Repository(_DB(Path(tempfile.mkdtemp()) / 'p.sqlite3').initialize())
        >>> _ = repo.put('categories', {'id': 'cat_1', 'workspace': 'personal',
        ...     'name': 'Comida', 'color': '#FF0000'})
        >>> repo.get('categories', 'cat_1')['color']
        '#FF0000'
        >>> _ = repo.put('categories', {'id': 'cat_1', 'workspace': 'personal', 'name': 'Otra'})
        >>> repo.get('categories', 'cat_1')['color']   # vuelve al valor por defecto
        '#2563EB'
        """
        data = _dump(store, record, full=True)
        key_field = PRIMARY_KEY[store]

        if store in AUTO_INCREMENT_STORES and not data.get("id"):
            data.pop("id", None)
            return self.add(store, record)

        columns = list(data)
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(
            f"{c} = excluded.{c}" for c in columns if c != key_field
        )
        sql = (
            f"INSERT INTO {store} ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT({key_field}) DO UPDATE SET {updates}"
        )
        self.db.execute(sql, [data[c] for c in columns])
        return data.get(key_field)

    def add_many(self, store: str, records: Iterable[dict[str, Any]]) -> int:
        """Inserta varios registros en una sola transacción. Devuelve el total.

        La versión de referencia recorre con ``await`` uno a uno (y así se comporta
        ``saveTransaction`` en el bucle del dataset demo); aquí se agrupa, que es
        equivalente pero mucho más rápido.
        """
        count = 0
        with self.db.tx() as conn:
            for record in records:
                data = _dump(store, record)
                if store in AUTO_INCREMENT_STORES:
                    data.pop("id", None)
                columns = list(data)
                placeholders = ", ".join("?" for _ in columns)
                conn.execute(
                    f"INSERT INTO {store} ({', '.join(columns)}) VALUES ({placeholders})",
                    [data[c] for c in columns],
                )
                count += 1
        return count

    def delete(self, store: str, key: Any) -> None:
        """Elimina por clave primaria. Equivale a ``DB.delete``."""
        key_field = PRIMARY_KEY[store]
        self.db.execute(f"DELETE FROM {store} WHERE {key_field} = ?", (key,))

    def clear(self, store: str) -> None:
        """Vacía un almacén. Equivale a ``DB.clear``."""
        self.db.execute(f"DELETE FROM {store}")

    def clear_all(self) -> None:
        """Vacía los 5 almacenes (para el borrado seguro, línea 7213)."""
        with self.db.tx() as conn:
            for store in STORES:
                conn.execute(f"DELETE FROM {store}")

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------

    def get(self, store: str, key: Any) -> dict[str, Any] | None:
        """Un registro por clave primaria. Equivale a ``DB.get``."""
        key_field = PRIMARY_KEY[store]
        row = self.db.execute(
            f"SELECT * FROM {store} WHERE {key_field} = ?", (key,)
        ).fetchone()
        return _load(store, row) if row else None

    def all(self, store: str) -> list[dict[str, Any]]:
        """Todos los registros, ordenados por clave primaria.

        Es el orden que devuelve ``getAll`` en IndexedDB, y del que dependen
        algunas funciones de la versión de referencia.
        """
        key_field = PRIMARY_KEY[store]
        rows = self.db.execute(
            f"SELECT * FROM {store} ORDER BY {key_field}"
        ).fetchall()
        return [_load(store, row) for row in rows]

    def count(self, store: str) -> int:
        """Número de registros. Equivale a ``DB.count``."""
        return int(self.db.execute(f"SELECT COUNT(*) AS n FROM {store}").fetchone()["n"])

    def query_by_index(self, store: str, index: str, key: Any) -> list[dict[str, Any]]:
        """Consulta por índice. Equivale a ``DB.queryByIndex``.

        ``key`` es un escalar o una tupla, según el índice (``workspace_year``
        espera ``(workspace, year)``).

        >>> import tempfile
        >>> from pathlib import Path
        >>> from app.data.db import Database
        >>> repo = Repository(Database(Path(tempfile.mkdtemp()) / 'q.sqlite3').initialize())
        >>> _ = repo.add('transactions', {'workspace': 'personal', 'year': 2026,
        ...     'date': '2026-01-01', 'productName': 'A', 'amountBs': 10, 'amountUsd': 1})
        >>> len(repo.query_by_index('transactions', 'workspace_year', ('personal', 2026)))
        1
        >>> len(repo.query_by_index('transactions', 'workspace_year', ('personal', 2025)))
        0
        """
        try:
            where, build_params = INDEX_MAP[(store, index)]
        except KeyError:
            raise ValueError(
                f"No existe el indice '{index}' en '{store}'"
            ) from None

        order = [column.split()[0] for column in where.split(" AND ")]
        key_field = PRIMARY_KEY[store]
        if key_field not in order:
            order.append(key_field)

        sql = (
            f"SELECT * FROM {store} WHERE {where} ORDER BY {', '.join(order)}"
        )
        rows = self.db.execute(sql, build_params(key)).fetchall()
        return [_load(store, row) for row in rows]

    # ------------------------------------------------------------------
    # Consultas de conveniencia (las que la versión de referencia escribe a mano)
    # ------------------------------------------------------------------

    def categories_for(self, workspace: str) -> list[dict[str, Any]]:
        """``loadWorkspaceData``."""
        return self.query_by_index("categories", "workspace", workspace)

    def products_for(self, workspace: str) -> list[dict[str, Any]]:
        """``loadWorkspaceData``."""
        return self.query_by_index("products", "workspace", workspace)

    def transactions_for_year(self, workspace: str, year: int) -> list[dict[str, Any]]:
        """``queryByIndex(transactions,'workspace_year',[ws,year])``."""
        return self.query_by_index("transactions", "workspace_year", (workspace, year))

    def transactions_for_workspace(self, workspace: str) -> list[dict[str, Any]]:
        """``getFilteredTx`` (línea 3946 en adelante): todo el workspace."""
        return self.query_by_index("transactions", "workspace", workspace)

    def find_product_by_name(
        self, workspace: str, name: str
    ) -> dict[str, Any] | None:
        """Busca un producto por nombre exacto, sin distinguir mayúsculas.

        La versión de referencia hace ``APP.products.find(p => p.name.toLowerCase() === ...)``
        (líneas 3945 y 4096). Se resuelve con el índice ``name_lower``.
        """
        rows = self.query_by_index("products", "name_lower", name.lower())
        for row in rows:
            if row.get("workspace") == workspace:
                return row
        return None

    def rates_desc(self) -> list[dict[str, Any]]:
        """Tasas ordenadas de más reciente a más antigua (``refreshRatesCache``)."""
        rows = self.db.execute("SELECT * FROM rates ORDER BY date DESC").fetchall()
        return [_load("rates", row) for row in rows]

    def rates_asc(self) -> list[dict[str, Any]]:
        """Tasas ordenadas de más antigua a más reciente."""
        rows = self.db.execute("SELECT * FROM rates ORDER BY date ASC").fetchall()
        return [_load("rates", row) for row in rows]

    def rates_for_year(self, year: int) -> list[dict[str, Any]]:
        """``APP.rates.filter(r => r.date.startsWith(String(year)))``."""
        rows = self.db.execute(
            "SELECT * FROM rates WHERE date LIKE ? ORDER BY date ASC",
            (f"{year}-%",),
        ).fetchall()
        return [_load("rates", row) for row in rows]

    def closures_for(self, workspace: str) -> list[dict[str, Any]]:
        """``viewClosuresModal``."""
        rows = self.db.execute(
            "SELECT * FROM closures WHERE workspace = ? ORDER BY year DESC", (workspace,)
        ).fetchall()
        return [_load("closures", row) for row in rows]

    def storage_stats(self) -> dict[str, int]:
        """``refreshStorageStats``: recuento por almacén."""
        stats = {store: self.count(store) for store in STORES}
        stats["configKeys"] = int(
            self.db.execute("SELECT COUNT(*) AS n FROM config").fetchone()["n"]
        )
        return stats

    # ------------------------------------------------------------------
    # Configuración (reemplaza localStorage, líneas 2898-2900)
    # ------------------------------------------------------------------

    def get_config(self, key: str, default: str | None = None) -> str | None:
        """``lsGet``: devuelve el valor o el sustituto si no existe."""
        row = self.db.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_config(self, key: str, value: Any) -> None:
        """``lsSet``: guarda siempre como texto, igual que ``String(v)``."""
        text = "null" if value is None else str(value)
        self.db.execute(
            "INSERT INTO config (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, text),
        )

    def remove_config(self, key: str) -> None:
        """``lsRemove``."""
        self.db.execute("DELETE FROM config WHERE key = ?", (key,))

    def config_keys(self) -> list[str]:
        rows = self.db.execute("SELECT key FROM config ORDER BY key").fetchall()
        return [row["key"] for row in rows]

    def clear_config(self) -> None:
        self.db.execute("DELETE FROM config")
