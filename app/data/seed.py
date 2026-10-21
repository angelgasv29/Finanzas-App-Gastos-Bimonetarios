"""Semilla de categorías por defecto.

Implementación de ``seedCategoriesIfEmpty`` (líneas 3041-3087 de la referencia).

La versión de referencia crea categorías distintas para cada entorno de trabajo:

- **Personal** (4): Alimentación, Salud, Servicios, Transporte.
- **Profesional** (3): Insumos, Operaciones, Honorarios.

La siembra es **idempotente**: si un entorno ya tiene categorías, no se toca.
El ``id`` de cada campo personalizado es aleatorio, por lo que la función acepta
un generador inyectable para poder probarla de forma determinista.
"""

from __future__ import annotations

from typing import Any, Callable

from ..core.constants import CAT_COLORS
from ..core.ids import now_ms, uid
from .repo import Repository

__all__ = ["SEEDS", "seed_categories_if_empty"]

# Campos habilitados por tipo de categoría. La versión de referencia repite este objeto; aquí
# se nombra una vez. ``originPlatform`` se añade después si falta.
_FIELDS_FULL = {
    "quantity": True,
    "unit": True,
    "brand": True,
    "subcategory": True,
    "provider": True,
    "paymentMethod": True,
    "originPlatform": True,
    "nature": True,
    "tax": True,
}

_FIELDS_SIMPLE = {
    "quantity": False,
    "unit": False,
    "brand": False,
    "subcategory": True,
    "provider": True,
    "paymentMethod": True,
    "originPlatform": True,
    "nature": True,
    "tax": True,
}

SEEDS: dict[str, list[dict[str, Any]]] = {
    "personal": [
        {
            "name": "Alimentación y Abastecimiento",
            "color": CAT_COLORS["alimentacion"],
            "enabledFields": _FIELDS_FULL,
            "customFields": [
                {"label": "Presentación / Empaque", "type": "text", "required": False}
            ],
        },
        {
            "name": "Salud y Farmacia",
            "color": CAT_COLORS["salud"],
            "enabledFields": _FIELDS_FULL,
            "customFields": [
                {"label": "Componente / Dosis", "type": "text", "required": False}
            ],
        },
        {
            "name": "Servicios y Conectividad",
            "color": CAT_COLORS["servicios"],
            "enabledFields": _FIELDS_SIMPLE,
            "customFields": [
                {"label": "Nro. Contrato / Medidor", "type": "text", "required": False}
            ],
        },
        {
            "name": "Transporte y Movilidad",
            "color": CAT_COLORS["transporte"],
            "enabledFields": _FIELDS_FULL,
            "customFields": [
                {"label": "Kilometraje", "type": "number", "required": False}
            ],
        },
    ],
    "profesional": [
        {
            "name": "Insumos e Inventario",
            "color": CAT_COLORS["insumos"],
            "enabledFields": _FIELDS_FULL,
            "customFields": [
                {"label": "RIF Proveedor", "type": "text", "required": False},
                {"label": "Nro. Control Fiscal", "type": "text", "required": False},
            ],
        },
        {
            "name": "Operaciones y SaaS",
            "color": CAT_COLORS["operaciones"],
            "enabledFields": _FIELDS_SIMPLE,
            "customFields": [
                {"label": "Centro de Costo", "type": "text", "required": False}
            ],
        },
        {
            "name": "Honorarios y Logística",
            "color": CAT_COLORS["honorarios"],
            "enabledFields": _FIELDS_SIMPLE,
            "customFields": [
                {"label": "% Retención ISLR", "type": "number", "required": False}
            ],
        },
    ],
}

WORKSPACES = ("personal", "profesional")


def seed_categories_if_empty(
    repo: Repository,
    id_factory: Callable[[str], str] | None = None,
    workspaces: tuple[str, ...] = WORKSPACES,
) -> int:
    """Crea las categorías por defecto en los entornos que estén vacíos.

    Devuelve cuántas categorías se crearon. Es idempotente, igual que el
    de referencia.

    >>> import tempfile
    >>> from pathlib import Path
    >>> from app.data.db import Database
    >>> repo = Repository(Database(Path(tempfile.mkdtemp()) / 's.sqlite3').initialize())
    >>> seed_categories_if_empty(repo)
    7
    >>> seed_categories_if_empty(repo)   # segunda llamada: no hace nada
    0
    >>> len(repo.categories_for('personal')), len(repo.categories_for('profesional'))
    (4, 3)
    """
    make_id = id_factory or uid
    created = 0

    for workspace in workspaces:
        existing = repo.categories_for(workspace)
        if existing:
            continue

        for seed in SEEDS[workspace]:
            enabled = dict(seed["enabledFields"])
            # Línea 3074: si el campo no está declarado, se habilita.
            enabled.setdefault("originPlatform", True)

            custom_fields = [
                {
                    "id": make_id("cf"),
                    "label": field["label"],
                    "type": field["type"],
                    "required": field["required"],
                }
                for field in seed["customFields"]
            ]

            stamp = now_ms()
            repo.put(
                "categories",
                {
                    "id": make_id("cat"),
                    "workspace": workspace,
                    "name": seed["name"],
                    "color": seed["color"],
                    "enabledFields": enabled,
                    "customFields": custom_fields,
                    "createdAt": stamp,
                    "updatedAt": stamp,
                },
            )
            created += 1

    return created
