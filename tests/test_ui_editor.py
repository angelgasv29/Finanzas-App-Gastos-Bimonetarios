"""Pruebas de humo de «Registrar», sin navegador.

Usa el simulador de usuario de NiceGUI (``user_simulation``) para:

* abrir el modal de edición, teclear un monto nuevo y pulsar «Guardar cambios»;
* rellenar el formulario de alta y comprobar que los campos personalizados de la
  categoría se guardan en ``customValues``.

El primer caso verifica que el registro se recalcula con la misma lógica del motor
(``apply_edit``) y que se conservan los campos que el editor no toca (categoría,
``createdAt``).
"""

from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path

from nicegui.testing.user_simulation import user_simulation

from app.domain import transactions as domain_tx
from app.ui.panels import registrar
from app.ui.state import open_state


def _category_with_text_field(state, required: tuple[str, ...] = ()) -> tuple[dict, dict]:
    """La primera categoría con un campo personalizado de texto.

    El orden de las categorías sembradas es arbitrario (van ordenadas por su
    ``id``), así que no se puede asumir que la primera tenga texto. ``required``
    permite exigir que la categoría tenga habilitados los campos que la prueba
    va a comprobar (cantidad, unidad, marca…).
    """
    for category in state.categories:
        enabled = category.get("enabledFields") or {}
        if not all(enabled.get(field, True) for field in required):
            continue
        for field in category.get("customFields") or []:
            if field.get("type") == "text":
                return category, field
    raise AssertionError("Las categorías sembradas no tienen campos de texto")


def test_el_editor_recalcula_y_guarda(tmp_path: Path) -> None:
    asyncio.run(_editar(tmp_path))


async def _editar(tmp_path: Path) -> None:
    state = open_state(tmp_path / "app.sqlite3")
    state.repo.put(
        "rates", {"date": "2026-03-15", "value": 40.0, "source": "BCV", "ts": 0}
    )
    state.refresh()
    category, custom_field = _category_with_text_field(state)

    tx_id = state.repo.add(
        "transactions",
        domain_tx.build_transaction(
            workspace="personal",
            date="2026-03-15",
            category_id=category["id"],
            product_name="Harina",
            rate=state.active_rate,
            bs_amount=116,
            mode="incluido",
            timestamp=1,
        ),
    )
    tx = state.repo.get("transactions", tx_id)

    def root() -> None:
        registrar._open_editor(state, tx)

    async with user_simulation(root=root) as user:
        await user.open("/")
        await user.should_see("Editar compra")
        user.find(marker="edit-bs").clear().type("232")
        user.find(marker=f"cf-{custom_field['id']}").clear().type("1 kg")
        user.find(marker="edit-save").click()
        await asyncio.sleep(0.1)

    updated = state.repo.get("transactions", tx_id)
    state.close()

    # incluido: base = 232 / 1.16; iva = 232 - base; USD = total / 40
    assert updated["amountBs"] == 232.0
    assert updated["amountUsd"] == 5.8
    assert updated["baseImponible"] == 200.0
    assert updated["ivaMonto"] == 32.0
    assert updated["year"] == 2026
    # El editor no toca estos campos (``{...tx, ...overrides}``).
    assert updated["categoryId"] == category["id"]
    assert updated["createdAt"] == 1
    assert updated["customValues"][custom_field["id"]] == "1 kg"


def test_el_editor_permite_cambiar_categoria_y_tasa_iva(tmp_path: Path) -> None:
    asyncio.run(_editar_categoria_y_iva(tmp_path))


async def _editar_categoria_y_iva(tmp_path: Path) -> None:
    state = open_state(tmp_path / "app.sqlite3")
    state.repo.put(
        "rates", {"date": "2026-03-15", "value": 40.0, "source": "BCV", "ts": 0}
    )
    state.refresh()
    original_category = state.categories[0]
    target_category = state.categories[1]

    tx_id = state.repo.add(
        "transactions",
        domain_tx.build_transaction(
            workspace="personal",
            date="2026-03-15",
            category_id=original_category["id"],
            product_name="Harina",
            rate=state.active_rate,
            bs_amount=116,
            mode="incluido",
            timestamp=1,
        ),
    )
    tx = state.repo.get("transactions", tx_id)

    def root() -> None:
        registrar._open_editor(state, tx)

    async with user_simulation(root=root) as user:
        await user.open("/")
        await user.should_see("Editar compra")
        category_select = next(iter(user.find(marker="edit-category").elements))
        with user.client:
            category_select.value = target_category["id"]
        user.find(marker="edit-vat-rate").clear().type("8")
        user.find(marker="edit-bs").clear().type("108")
        user.find(marker="edit-save").click()
        await asyncio.sleep(0.1)

    updated = state.repo.get("transactions", tx_id)
    state.close()

    assert updated["categoryId"] == target_category["id"]
    assert updated["ivaRate"] == 0.08
    assert updated["baseImponible"] == 100.0
    assert updated["ivaMonto"] == 8.0
    assert updated["amountBs"] == 108.0


def test_el_formulario_guarda_campos_personalizados(tmp_path: Path) -> None:
    asyncio.run(_registrar(tmp_path))


def test_la_etiqueta_del_buscador_incluye_los_identificadores() -> None:
    label = registrar._product_label(
        {
            "id": "PROD-P-CAFE",
            "name": "Café",
            "brand": "Marca X",
            "provider": "Mercado A",
            "unit": "kg",
        },
        "Alimentos",
    )
    assert "Café" in label
    assert "PROD-P-CAFE" in label
    assert "Alimentos" in label
    assert "Marca X" in label
    assert "Mercado A" in label
    assert "kg" in label


def test_el_formulario_autocompleta_desde_el_catalogo(tmp_path: Path) -> None:
    asyncio.run(_autocompletar(tmp_path))


def test_el_formulario_reutiliza_valores_con_errata(tmp_path: Path) -> None:
    asyncio.run(_reutilizar_con_errata(tmp_path))


async def _reutilizar_con_errata(tmp_path: Path) -> None:
    state = open_state(tmp_path / "app.sqlite3")
    state.repo.put(
        "rates", {"date": "2026-03-15", "value": 40.0, "source": "BCV", "ts": 0}
    )
    state.refresh()
    category, _custom_field = _category_with_text_field(state)
    state.categories.sort(key=lambda item: item.get("id") != category.get("id"))

    product = {
        "id": "PROD-P-CAFE",
        "workspace": "personal",
        "name": "Café",
        "name_lower": "café",
        "categoryId": category["id"],
        "brand": "Marca X",
        "unit": "kg",
        "subcategory": "Bebidas",
        "provider": "Central Madeirense",
        "createdAt": 1,
        "updatedAt": 1,
    }
    state.repo.put("products", product)
    state.refresh()

    def root() -> None:
        registrar.render(state)

    async with user_simulation(root=root) as user:
        await user.open("/")
        await user.should_see("Registrar compra")
        user.find(marker="reg-product").type("Cafe")
        user.find(marker="reg-provider").type("Central Madeirenze")
        await user.should_see("Comercio existente")
        user.find(marker="reg-bs").clear().type("116")
        user.find(marker="reg-save").click()
        await asyncio.sleep(0.1)

    txs = state.transactions()
    products = list(state.products)
    state.close()

    assert len(txs) == 1
    assert txs[0]["productId"] == product["id"]
    assert txs[0]["productName"] == "Café"
    assert txs[0]["provider"] == "Central Madeirense"
    assert len(products) == 1


async def _autocompletar(tmp_path: Path) -> None:
    state = open_state(tmp_path / "app.sqlite3")
    state.repo.put(
        "rates", {"date": "2026-03-15", "value": 40.0, "source": "BCV", "ts": 0}
    )
    state.refresh()
    category, custom_field = _category_with_text_field(
        state, ("quantity", "unit", "brand")
    )
    state.categories.sort(key=lambda item: item.get("id") != category.get("id"))

    product = {
        "id": "PROD-P-CAFE",
        "workspace": "personal",
        "name": "Café",
        "name_lower": "café",
        "categoryId": category["id"],
        "brand": "Marca X",
        "unit": "kg",
        "subcategory": "Bebidas",
        "provider": "Mercado A",
        "createdAt": 1,
        "updatedAt": 1,
    }
    state.repo.put("products", product)
    state.repo.add(
        "transactions",
        domain_tx.build_transaction(
            workspace="personal",
            date="2026-03-01",
            category_id=category["id"],
            product_name="Café",
            rate=state.active_rate,
            bs_amount=116,
            mode="incluido",
            product_id=product["id"],
            quantity=2,
            unit="kg",
            brand="Marca X",
            subcategory="Bebidas",
            provider="Mercado A",
            payment_method="Efectivo Bs",
            origin_platform="Binance P2P",
            nature="Recurrente",
            custom_values={custom_field["id"]: "Paquete 500 g"},
            timestamp=1,
        ),
    )
    state.refresh()

    def root() -> None:
        registrar.render(state)

    async with user_simulation(root=root) as user:
        await user.open("/")
        await user.should_see("Registrar compra")
        picker = next(iter(user.find(marker="reg-product-picker").elements))
        with user.client:
            picker.value = product["id"]
        await user.should_see("Autocompletado desde la última compra")
        user.find(marker="reg-bs").clear().type("116")
        user.find(marker="reg-save").click()
        await asyncio.sleep(0.1)

    txs = state.transactions()
    state.close()

    assert len(txs) == 2
    latest = max(txs, key=lambda tx: tx.get("id") or 0)
    assert latest["productId"] == product["id"]
    assert latest["productName"] == "Café"
    assert latest["amountBs"] == 116.0
    assert latest["quantity"] == 2
    assert latest["unit"] == "kg"
    assert latest["brand"] == "Marca X"
    assert latest["subcategory"] == "Bebidas"
    assert latest["provider"] == "Mercado A"
    assert latest["paymentMethod"] == "Efectivo Bs"
    assert latest["originPlatform"] == "Binance P2P"
    assert latest["customValues"][custom_field["id"]] == "Paquete 500 g"
    assert len(state.products) == 1


def test_el_formulario_conserva_fecha_categoria_y_iva(tmp_path: Path) -> None:
    asyncio.run(_conservar_contexto(tmp_path))


async def _conservar_contexto(tmp_path: Path) -> None:
    state = open_state(tmp_path / "app.sqlite3")
    state.repo.put(
        "rates", {"date": "2026-03-15", "value": 40.0, "source": "BCV", "ts": 0}
    )
    state.refresh()
    category = state.categories[1]

    def root() -> None:
        registrar.render(state)

    async with user_simulation(root=root) as user:
        await user.open("/")
        await user.should_see("Registrar compra")
        date_input = next(iter(user.find(marker="reg-date").elements))
        category_select = next(iter(user.find(marker="reg-category").elements))
        with user.client:
            date_input.set_value("2026-03-01")
            category_select.set_value(category["id"])
        user.find(marker="reg-vat-rate").clear().type("8")
        await user.should_see("Fecha fijada")
        user.find(marker="reg-product").type("Café")
        user.find(marker="reg-bs").clear().type("108")
        user.find(marker="reg-save").click()
        await asyncio.sleep(0.1)

        # Tras guardar, los tres datos de contexto siguen puestos.
        assert next(iter(user.find(marker="reg-date").elements)).value == "2026-03-01"
        assert (
            next(iter(user.find(marker="reg-category").elements)).value
            == category["id"]
        )
        assert float(
            next(iter(user.find(marker="reg-vat-rate").elements)).value
        ) == 8.0

        user.find(marker="reg-product").type("Azúcar")
        user.find(marker="reg-bs").clear().type("54")
        user.find(marker="reg-save").click()
        await asyncio.sleep(0.1)

    txs = sorted(state.transactions(), key=lambda tx: tx.get("id") or 0)
    state.close()

    assert len(txs) == 2
    for tx in txs:
        assert tx["date"] == "2026-03-01"
        assert tx["categoryId"] == category["id"]
        assert tx["ivaRate"] == 0.08


def test_el_formulario_puede_no_conservar_el_contexto(tmp_path: Path) -> None:
    asyncio.run(_no_conservar_contexto(tmp_path))


async def _no_conservar_contexto(tmp_path: Path) -> None:
    state = open_state(tmp_path / "app.sqlite3")
    state.repo.put(
        "rates", {"date": "2026-03-15", "value": 40.0, "source": "BCV", "ts": 0}
    )
    state.refresh()

    def root() -> None:
        registrar.render(state)

    async with user_simulation(root=root) as user:
        await user.open("/")
        await user.should_see("Registrar compra")
        date_input = next(iter(user.find(marker="reg-date").elements))
        category_select = next(iter(user.find(marker="reg-category").elements))
        with user.client:
            date_input.set_value("2026-03-01")
            category_select.set_value(state.categories[1]["id"])
        user.find(marker="reg-vat-rate").clear().type("8")
        user.find(marker="reg-keep-context").click()
        user.find(marker="reg-product").type("Café")
        user.find(marker="reg-bs").clear().type("108")
        user.find(marker="reg-save").click()
        await asyncio.sleep(0.1)

        assert (
            next(iter(user.find(marker="reg-date").elements)).value
            == dt.date.today().isoformat()
        )
        assert (
            next(iter(user.find(marker="reg-category").elements)).value
            == state.categories[0]["id"]
        )
        assert not next(iter(user.find(marker="reg-keep-context").elements)).value

    state.close()


async def _registrar(tmp_path: Path) -> None:
    state = open_state(tmp_path / "app.sqlite3")
    state.repo.put(
        "rates", {"date": "2026-03-15", "value": 40.0, "source": "BCV", "ts": 0}
    )
    state.refresh()
    category, custom_field = _category_with_text_field(state)
    # El formulario arranca con la primera categoría de la lista.
    state.categories.sort(key=lambda item: item.get("id") != category.get("id"))

    def root() -> None:
        registrar.render(state)

    async with user_simulation(root=root) as user:
        await user.open("/")
        await user.should_see("Registrar compra")
        user.find(marker="reg-product").type("Café")
        user.find(marker="reg-bs").clear().type("116")
        user.find(marker=f"cf-{custom_field['id']}").type("Paquete 500 g")
        user.find(marker="reg-save").click()
        await asyncio.sleep(0.1)

    txs = state.transactions()
    state.close()

    assert len(txs) == 1
    assert txs[0]["productName"] == "Café"
    assert txs[0]["amountBs"] == 116.0
    assert txs[0]["customValues"][custom_field["id"]] == "Paquete 500 g"
