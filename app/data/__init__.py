"""Capa de datos: SQLite en lugar de IndexedDB.

- :mod:`db`      Conexión y esquema.
- :mod:`models`  Metadatos de los almacenes.
- :mod:`repo`    Repositorio con la API del objeto ``DB`` de referencia.
- :mod:`seed`    Categorías por defecto.

La configuración que la versión de referencia guardaba en ``localStorage`` (claves ``gb_*``)
se guarda aquí en la tabla ``config``.
"""

from .db import Database, default_db_path
from .repo import Repository
from .seed import seed_categories_if_empty

__all__ = [
    "Database",
    "Repository",
    "default_db_path",
    "seed_categories_if_empty",
]
