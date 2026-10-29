"""Pruebas de humo del panel Análisis: agrupaciones de Variantes y Frecuencia."""

from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path

from nicegui.testing.user_simulation import user_simulation

from app.domain import transactions as domain_tx
from app.ui.panels import analisis
from app.ui.state import open_state


def test_variantes_y_frecuencia_cambian_de_agrupacion(tmp_path: Path) -> None:
    asyncio.run(_agrupaciones(tmp_path))


async def _agrupaciones(tmp_path: Path) -> None:
    state = open_state(tmp_path / "app.sqlite3")
    today = dt.date.today()
    state.repo.put(
        "rates",
        {"date": today.isoformat(), "value": 40.0, "source": "BCV", "ts": 0},
    )
    state.refresh()
    category = state.categories[0]

    for index, (date, provider, brand, product, amount) in enumerate(
        [
            (today.replace(day=1).isoformat(), "Central Madeirense", "Marca A", "Harina", 10.0),
            (today.isoformat(), "Central Madeirense", "Marca A", "Harina", 12.0),
            (today.isoformat(), "Mercado B", "Marca B", "Arroz", 20.0),
        ],
        start=1,
    ):
        state.repo.add(
            "transactions",
            domain_tx.build_transaction(
                workspace="personal",
                date=date,
                category_id=category["id"],
                product_name=product,
                rate=state.active_rate,
                bs_amount=amount * 40,
                mode="incluido",
                quantity=1,
                unit="kg",
                brand=brand,
                provider=provider,
                payment_method="Efectivo Bs",
                origin_platform="Binance P2P",
                nature="Recurrente",
                timestamp=index,
            ),
        )
    state.refresh()

    def root() -> None:
        analisis.render(state)

    async with user_simulation(root=root) as user:
        await user.open("/")
        await user.should_see("Período de análisis")

        user.find("Variantes").click()
        await user.should_see("Variantes · Unidad")
        variant_group = next(
            iter(user.find(marker="analysis-variants-group").elements)
        )
        with user.client:
            variant_group.value = "provider"
        await user.should_see("Variantes · Comercio")
        await user.should_see("Central Madeirense")
        await user.should_see("Mercado B")

        user.find("Frecuencia").click()
        await user.should_see("Frecuencia · Comercio")
        frequency_group = next(
            iter(user.find(marker="analysis-frequency-group").elements)
        )
        with user.client:
            frequency_group.value = "brand"
        await user.should_see("Frecuencia · Marca")
        await user.should_see("Marca A")
        await user.should_see("Marca B")

        user.find("Proyecciones").click()
        await user.should_see("Proyección de la tasa de cambio")
        await user.should_see("Se necesitan al menos 2 tasas históricas registradas.")

    state.close()
