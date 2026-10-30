"""Búsqueda, cascada y desplazamiento en la lista de movimientos.

La tabla de «Movimientos recientes» debe seguir siendo usable con cientos de
compras: búsqueda por texto, filtro por categoría, vista en cascada por mes y
una barra de desplazamiento con cabecera fija.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from nicegui.testing.user_simulation import user_simulation

from app.domain import transactions as domain_tx
from app.ui.panels import registrar
from app.ui.state import open_state


def _add_tx(
    state,
    product_name: str,
    *,
    date: str,
    provider: str = "",
    category_id: str | None = None,
) -> int:
    return state.repo.add(
        "transactions",
        domain_tx.build_transaction(
            workspace="personal",
            date=date,
            category_id=category_id or state.categories[0]["id"],
            product_name=product_name,
            rate=state.active_rate,
            bs_amount=116,
            mode="incluido",
            provider=provider,
            timestamp=1,
        ),
    )


def test_movimientos_busca_y_cambia_a_cascada(tmp_path: Path) -> None:
    asyncio.run(_buscar_y_cascada(tmp_path))


async def _buscar_y_cascada(tmp_path: Path) -> None:
    state = open_state(tmp_path / "app.sqlite3")
    state.repo.put(
        "rates", {"date": "2026-03-15", "value": 40.0, "source": "BCV", "ts": 0}
    )
    state.refresh()
    category = state.categories[0]
    _add_tx(
        state,
        "Harina",
        date="2026-03-15",
        provider="Central Madeirense",
        category_id=category["id"],
    )
    _add_tx(
        state,
        "Arroz",
        date="2026-04-02",
        provider="Central Madeirense",
        category_id=category["id"],
    )
    state.refresh()

    def root() -> None:
        registrar.render(state)

    async with user_simulation(root=root) as user:
        await user.open("/")
        await user.should_see("Movimientos recientes")
        await user.should_see("Harina")
        await user.should_see("Arroz")

        list_table = next(iter(user.find(marker="tx-list").elements))
        assert "data-scroll" in list_table.content
        assert "460px" in list_table.content

        user.find(marker="tx-search").type("Arroz")
        await asyncio.sleep(0.1)
        await user.should_see("Arroz")
        await user.should_not_see("Harina")

        user.find(marker="tx-clear").click()
        await asyncio.sleep(0.1)
        await user.should_see("Harina")

        with user.client:
            next(iter(user.find(marker="tx-view").elements)).set_value(
                "cascada"
            )
        await asyncio.sleep(0.1)
        await user.should_see("Abril 2026")
        await user.should_see("Marzo 2026")
        assert len(user.find(marker="tx-month-2026-04").elements) == 1
        assert len(user.find(marker="tx-month-2026-03").elements) == 1

    state.close()


def test_el_corrector_incluye_mas_de_cien_movimientos(tmp_path: Path) -> None:
    asyncio.run(_corrector_con_muchos(tmp_path))


async def _corrector_con_muchos(tmp_path: Path) -> None:
    state = open_state(tmp_path / "app.sqlite3")
    state.repo.put(
        "rates", {"date": "2026-03-15", "value": 40.0, "source": "BCV", "ts": 0}
    )
    state.refresh()
    for index in range(101):
        _add_tx(
            state,
            f"Producto {index:03d}",
            date="2026-03-15",
            provider="Proveedor de prueba",
        )
    state.refresh()

    def root() -> None:
        registrar.render(state)

    async with user_simulation(root=root) as user:
        await user.open("/")
        await user.should_see("Corregir un movimiento")
        picker = next(iter(user.find(marker="tx-edit-picker").elements))
        assert len(picker.options) == 101

    state.close()
