"""Conexión y esquema de SQLite.

Reemplaza ``openDB`` / ``idbOp`` / el objeto ``DB`` de la versión de referencia
(líneas 2774-2839 de la referencia).

Diferencias deliberadas frente a la versión de referencia:

- **No hay asincronía.** IndexedDB es asíncrono (de ahí los 169 ``await`` del
  archivo); SQLite es síncrono. Eso elimina una clase entera de complejidad:
  no hay transacciones que puedan abortar entre dos lecturas.
- **Hay transacciones explícitas.** IndexedDB las tiene implícitas por
  operación; aquí se ofrecen con :meth:`Database.tx` para agrupar escrituras.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

__all__ = ["Database", "default_db_path", "SCHEMA_PATH"]

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# Nombre del fichero de datos, análogo a DB_NAME = 'GastosBimonetariosDB'.
DB_FILENAME = "gastos-bimonetarios.sqlite3"


def default_db_path() -> Path:
    """Ruta por defecto de la base de datos: ``<raíz del proyecto>/data/``."""
    root = Path(__file__).resolve().parent.parent.parent
    return root / "data" / DB_FILENAME


class Database:
    """Envoltura de una conexión SQLite con el esquema ya aplicado.

    El objeto es seguro para usarse desde varios hilos: la interfaz de NiceGUI
    puede ejecutar callbacks en un hilo distinto al principal. El acceso se
    serializa con un cerrojo y ``check_same_thread=False``.

    >>> import tempfile
    >>> from pathlib import Path
    >>> tmp = tempfile.mkdtemp()
    >>> db = Database(Path(tmp) / 'prueba.sqlite3')
    >>> _ = db.initialize()
    >>> db.table_names()[:3]
    ['categories', 'closures', 'config']
    >>> db.close()
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_db_path()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(self.path),
            check_same_thread=False,
            isolation_level=None,  # control manual de transacciones
        )
        self._conn.row_factory = sqlite3.Row
        # Rendimiento y consistencia: WAL permite leer mientras se escribe.
        if str(self.path) != ":memory:":
            self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")

    # -- ciclo de vida -----------------------------------------------------

    def initialize(self) -> "Database":
        """Aplica ``schema.sql`` y las migraciones aditivas conocidas.

        ``CREATE TABLE IF NOT EXISTS`` no añade columnas a una base ya creada,
        así que las columnas nuevas se agregan aquí. Son migraciones mínimas y
        solo añaden campos con valor por defecto; nunca borran datos.
        """
        with self._lock:
            self._conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            self._migrate()
        return self

    def _migrate(self) -> None:
        """Añade columnas nuevas a bases creadas por versiones anteriores."""
        columns = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(transactions)")
        }
        if "ivaRate" not in columns:
            self._conn.execute(
                "ALTER TABLE transactions "
                "ADD COLUMN ivaRate REAL NOT NULL DEFAULT 0.16"
            )
            # Las bases antiguas no guardaban la alícuota. Se deduce de la
            # relación IVA/base para no etiquetar como 16 % una compra que
            # pudo haberse importado con otra tasa. Los exentos conservan el
            # valor por defecto, que la auditoría ignora.
            self._conn.execute(
                "UPDATE transactions SET ivaRate = ivaMonto / baseImponible "
                "WHERE taxMode <> 'exento' AND baseImponible > 0"
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "Database":
        return self.initialize()

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- acceso ------------------------------------------------------------

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def execute(self, sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def executemany(self, sql: str, seq: list[tuple]) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.executemany(sql, seq)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """Transacción explícita: o se aplica todo, o nada.

        >>> import tempfile
        >>> from pathlib import Path as _P
        >>> db = Database(_P(tempfile.mkdtemp()) / 't.sqlite3').initialize()
        >>> with db.tx() as conn:
        ...     _ = conn.execute("INSERT INTO config(key,value) VALUES('a','1')")
        >>> db.execute("SELECT COUNT(*) FROM config").fetchone()[0]
        1
        >>> try:
        ...     with db.tx() as conn:
        ...         _ = conn.execute("INSERT INTO config(key,value) VALUES('b','2')")
        ...         raise RuntimeError('fallo simulado')
        ... except RuntimeError:
        ...     pass
        >>> db.execute("SELECT COUNT(*) FROM config").fetchone()[0]
        1
        >>> db.close()
        """
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute("COMMIT")

    # -- introspección -----------------------------------------------------

    def table_names(self) -> list[str]:
        rows = self.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [row["name"] for row in rows]

    def index_names(self, table: str) -> list[str]:
        rows = self.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name = ? "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name",
            (table,),
        ).fetchall()
        return [row["name"] for row in rows]
