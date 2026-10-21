"""Prueba del editor de campos personalizados de una categoría.

Verifica el camino completo: abrir el diálogo, añadir un campo, marcarlo como
obligatorio y guardar. Es el mismo ``customFields`` que luego leen el formulario
de alta y el editor de compras.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from nicegui.testing.user_simulation import user_simulation

from app.ui.panels import categorias
from app.ui.state import open_state


def test_la_categoria_guarda_campos_personalizados(tmp_path: Path) -> None:
    asyncio.run(_categoria(tmp_path))


async def _categoria(tmp_path: Path) -> None:
    state = open_state(tmp_path / "app.sqlite3")
    state.refresh()
    category = state.categories[0]
    before = len(category.get("customFields") or [])

    def root() -> None:
        categorias._edit_dialog(state, category, lambda: None)

    async with user_simulation(root=root) as user:
        await user.open("/")
        await user.should_see("Editar categoría")
        user.find(marker="cf-add").click()
        user.find(marker=f"cf-label-{before}").type("Lote")
        user.find(marker=f"cf-required-{before}").click()
        user.find(marker="cat-save").click()
        await asyncio.sleep(0.1)

    updated = state.repo.get("categories", category["id"])
    state.close()

    fields = updated["customFields"]
    assert len(fields) == before + 1
    assert fields[-1]["label"] == "Lote"
    assert fields[-1]["required"] is True
