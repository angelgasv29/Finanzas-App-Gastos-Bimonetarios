"""Metadatos de los almacenes.

Describe cada tabla para poder generar las consultas de inserción y lectura sin
repetir la lista de columnas. Las claves son **las mismas que en el JavaScript**
(``camelCase``), de forma que el resto de esta implementación trabaja con diccionarios
idénticos a los objetos de la versión de referencia.
"""

from __future__ import annotations

from typing import Any, Final

__all__ = [
    "STORE_FIELDS",
    "JSON_FIELDS",
    "FIELD_DEFAULTS",
    "PRIMARY_KEY",
    "AUTO_INCREMENT_STORES",
    "TIMESTAMP_FIELDS",
    "INDEX_MAP",
    "STORES",
]

STORES: Final[tuple[str, ...]] = (
    "transactions",
    "products",
    "categories",
    "rates",
    "closures",
)

# Columnas en el mismo orden que en schema.sql.
STORE_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    "transactions": (
        "id",
        "workspace",
        "year",
        "date",
        "productId",
        "productName",
        "categoryId",
        "quantity",
        "unit",
        "brand",
        "subcategory",
        "provider",
        "paymentMethod",
        "originPlatform",
        "nature",
        "taxMode",
        "baseImponible",
        "ivaMonto",
        "amountBs",
        "amountUsd",
        "rate",
        "rateDate",
        "rateSource",
        "customValues",
        "notes",
        "createdAt",
        "updatedAt",
    ),
    "products": (
        "id",
        "workspace",
        "name",
        "name_lower",
        "categoryId",
        "brand",
        "unit",
        "subcategory",
        "provider",
        "createdAt",
        "updatedAt",
    ),
    "categories": (
        "id",
        "workspace",
        "name",
        "color",
        "enabledFields",
        "customFields",
        "createdAt",
        "updatedAt",
    ),
    "rates": ("date", "value", "source", "ts"),
    "closures": (
        "id",
        "workspace",
        "year",
        "closedAt",
        "totalBs",
        "totalUsd",
        "ivaTotal",
        "baseTotal",
        "txCount",
        "topCategories",
        "topExpenses",
        "rateStart",
        "rateEnd",
        "rateStartDate",
        "rateEndDate",
        "rateDelta",
        "inflationAvg",
        "notes",
    ),
}

# Campos que en la versión de referencia son objetos o arrays y aquí se guardan como JSON.
JSON_FIELDS: Final[dict[str, frozenset[str]]] = {
    "transactions": frozenset({"customValues"}),
    "products": frozenset(),
    "categories": frozenset({"enabledFields", "customFields"}),
    "rates": frozenset(),
    "closures": frozenset({"topCategories", "topExpenses"}),
}

# Valores que toma cada columna cuando el registro no la trae.
#
# Es necesario porque ``put`` **reemplaza** el registro entero, igual que
# ``IndexedDB.put``: en la versión de referencia, escribir un objeto sin una propiedad equivale
# a dejar esa propiedad en ``undefined``, no a conservar el valor anterior. Estos
# valores reproducen los ``DEFAULT`` de ``schema.sql`` para poder reemplazar sin
# dejar columnas ``NOT NULL`` en blanco.
FIELD_DEFAULTS: Final[dict[str, dict[str, Any]]] = {
    "transactions": {
        "workspace": "",
        "year": 0,
        "date": "",
        "productId": None,
        "productName": "",
        "categoryId": None,
        "quantity": None,
        "unit": "",
        "brand": "",
        "subcategory": "",
        "provider": "",
        "paymentMethod": "",
        "originPlatform": "",
        "nature": "",
        "taxMode": "",
        "baseImponible": 0.0,
        "ivaMonto": 0.0,
        "amountBs": 0.0,
        "amountUsd": 0.0,
        "rate": None,
        "rateDate": None,
        "rateSource": "",
        "customValues": {},
        "notes": "",
    },
    "products": {
        "workspace": "",
        "name": "",
        "name_lower": "",
        "categoryId": None,
        "brand": "",
        "unit": "",
        "subcategory": "",
        "provider": "",
    },
    "categories": {
        "workspace": "",
        "name": "",
        "color": "#2563EB",
        "enabledFields": {},
        "customFields": [],
    },
    "rates": {"value": 0.0, "source": "manual"},
    "closures": {
        "workspace": "",
        "year": 0,
        "totalBs": 0.0,
        "totalUsd": 0.0,
        "ivaTotal": 0.0,
        "baseTotal": 0.0,
        "txCount": 0,
        "topCategories": [],
        "topExpenses": [],
        "rateStart": None,
        "rateEnd": None,
        "rateStartDate": None,
        "rateEndDate": None,
        "rateDelta": 0.0,
        "inflationAvg": 0.0,
        "notes": "",
    },
}

PRIMARY_KEY: Final[dict[str, str]] = {
    "transactions": "id",
    "products": "id",
    "categories": "id",
    "rates": "date",
    "closures": "id",
}

# ``transactions`` usa keyPath 'id' con autoIncrement en la versión de referencia: su id lo
# asigna la base de datos, no el cliente.
AUTO_INCREMENT_STORES: Final[frozenset[str]] = frozenset({"transactions"})

# Campos de tiempo que la versión de referencia rellena siempre; si faltan, se completan.
TIMESTAMP_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    "transactions": ("createdAt", "updatedAt"),
    "products": ("createdAt", "updatedAt"),
    "categories": ("createdAt", "updatedAt"),
    "rates": ("ts",),
    "closures": ("closedAt",),
}

# Traducción de los índices de IndexedDB a condiciones SQL.
# La clave puede ser un escalar o una tupla, según el índice.
INDEX_MAP: Final[dict[tuple[str, str], tuple[str, object]]] = {
    ("transactions", "workspace"): ("workspace = ?", lambda k: (k,)),
    ("transactions", "date"): ("date = ?", lambda k: (k,)),
    ("transactions", "workspace_date"): (
        "workspace = ? AND date = ?",
        lambda k: (k[0], k[1]),
    ),
    ("transactions", "productId"): ("productId = ?", lambda k: (k,)),
    ("transactions", "year"): ("year = ?", lambda k: (k,)),
    ("transactions", "workspace_year"): (
        "workspace = ? AND year = ?",
        lambda k: (k[0], k[1]),
    ),
    ("products", "workspace"): ("workspace = ?", lambda k: (k,)),
    ("products", "name_lower"): ("name_lower = ?", lambda k: (k,)),
    ("categories", "workspace"): ("workspace = ?", lambda k: (k,)),
    ("rates", "date"): ("date = ?", lambda k: (k,)),
    ("closures", "workspace_year"): (
        "workspace = ? AND year = ?",
        lambda k: (k[0], k[1]),
    ),
}
