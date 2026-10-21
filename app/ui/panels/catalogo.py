"""Panel 3 · Catálogo de SKU: alta, edición y borrado de productos.

Renombrar un SKU **propaga** el nombre y la categoría a todas sus compras
(capa de compatibilidad de ``openProductEditor``), lo que se apoya en
:func:`app.domain.products.rename_product_transactions`.
"""

from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

from ...core.constants import UNIT_OPTIONS
from ...core.ids import now_ms
from ...core.text import escape_html
from ...domain import prices as domain_prices
from ...domain import products as domain_products
from .. import components as c
from ..state import AppState

__all__ = ["render"]


def _build(state: AppState) -> None:
    with ui.column().classes("w-full gap-4 p-4"):
        with c.card():
            c.section_title("Catálogo de SKU", c.chip_html(f"{len(state.products)} productos"))
            search = ui.input("Buscar por nombre, marca o SKU").classes("w-full")
            body = ui.column().classes("w-full gap-1")

            def refresh_table() -> None:
                body.clear()
                query = (search.value or "").strip().lower()
                listing = state.products
                if query:
                    listing = [
                        product
                        for product in listing
                        if query in (product.get("name") or "").lower()
                        or query in (product.get("id") or "").lower()
                        or query in (product.get("brand") or "").lower()
                    ]
                listing = sorted(
                    listing,
                    key=lambda product: product.get("updatedAt") or 0,
                    reverse=True,
                )
                with body:
                    if not listing:
                        ui.html(
                            c.empty_html(
                                "Sin resultados."
                                if query
                                else "Aún no hay productos en el catálogo."
                            )
                        )
                        return
                    for product in listing:
                        _row(state, product, refresh_table)

            search.on_value_change(lambda _e=None: refresh_table())
            refresh_table()

        with c.card():
            c.section_title("Nuevo SKU")
            new_name = ui.input("Nombre del producto").classes("w-full")
            with ui.row().classes("grid grid-cols-2 md:grid-cols-4 gap-3 w-full"):
                new_cat = ui.select(
                    {cat["id"]: cat["name"] for cat in state.categories},
                    value=(
                        next(iter(state.categories)).get("id") if state.categories else None
                    ),
                    label="Categoría",
                ).classes("w-full")
                new_brand = ui.input("Marca").classes("w-full")
                new_unit = ui.select(
                    list(UNIT_OPTIONS), value="unidad", label="Unidad"
                ).classes("w-full")
                new_provider = ui.input("Comercio habitual").classes("w-full")

            def create_product() -> None:
                name = (new_name.value or "").strip()
                if not name:
                    ui.notify("El nombre es obligatorio.", type="warning")
                    return
                stamp = now_ms()
                state.repo.put(
                    "products",
                    {
                        "id": state.new_product_id(),
                        "workspace": state.workspace,
                        "name": name,
                        "name_lower": name.lower(),
                        "categoryId": new_cat.value,
                        "brand": new_brand.value or "",
                        "unit": new_unit.value or "unidad",
                        "subcategory": "",
                        "provider": new_provider.value or "",
                        "createdAt": stamp,
                        "updatedAt": stamp,
                    },
                )
                state.refresh()
                state.notify()
                new_name.value = ""
                new_brand.value = ""
                new_provider.value = ""
                ui.notify("SKU creado.", type="positive")

            ui.button("Crear SKU", on_click=create_product).props("color=primary unelevated")


def _row(state: AppState, product: dict[str, Any], refresh_table: Callable[[], None]) -> None:
    alert = _alert_for(state, product)
    with ui.row().classes("row between w-full items-center").style(
        "border-bottom:1px solid var(--line-soft); padding:6px 2px"
    ):
        with ui.column().classes("gap-0"):
            ui.html(
                f'<div style="font-weight:600">{_esc(product.get("name"))}</div>'
                f'<div class="muted text-xs">{_esc(product.get("id"))} · '
                f'{_esc(state.category_name(product.get("categoryId")) or "—")} · '
                f'{_esc(product.get("brand") or "—")} · {_esc(product.get("unit") or "—")}</div>'
            )
        with ui.row().classes("gap-2 items-center"):
            if alert is not None:
                ui.html(c.chip_html(alert["text"], alert["kind"]))
            ui.button(
                "Editar", on_click=lambda p=product: _edit_dialog(state, p, refresh_table)
            ).props("flat dense")
            ui.button(
                "Borrar", on_click=lambda p=product: _delete(state, p, refresh_table)
            ).props("flat dense color=negative")


def _alert_for(state: AppState, product: dict[str, Any]) -> dict[str, str] | None:
    history = [
        tx for tx in state.transactions() if tx.get("productId") == product.get("id")
    ]
    if len(history) < 2:
        return None
    ordered = sorted(history, key=lambda tx: str(tx.get("date") or ""))
    last = ordered[-1]
    quantity = last.get("quantity") or 1
    total_bs = last.get("amountBs") or 0
    if not state.rate_value or float(quantity) <= 0:
        return None
    current_unit = (float(total_bs) / state.rate_value) / float(quantity)
    result = domain_prices.compute_price_alert(
        ordered[:-1], current_unit, str(last.get("unit") or "unidad")
    )
    if result is None:
        return None
    view = domain_prices.price_alert_view(result)
    return {
        "text": f"{view['pct']} vs media {view['avg']}",
        "kind": {"ok": "ok", "warn": "warn", "bad": "bad"}[result.level],
    }


def _edit_dialog(state: AppState, product: dict[str, Any], refresh_table: Callable[[], None]) -> None:
    with ui.dialog() as dialog, c.card():
        c.section_title(f"Editar SKU · {product.get('id')}")
        name = ui.input("Nombre", value=product.get("name") or "").classes("w-full")
        category = ui.select(
            {cat["id"]: cat["name"] for cat in state.categories},
            value=product.get("categoryId"),
            label="Categoría",
        ).classes("w-full")
        with ui.row().classes("grid grid-cols-2 gap-3 w-full"):
            brand = ui.input("Marca", value=product.get("brand") or "").classes("w-full")
            unit = ui.select(
                list(UNIT_OPTIONS), value=product.get("unit") or "unidad", label="Unidad"
            ).classes("w-full")
            subcategory = ui.input(
                "Subcategoría", value=product.get("subcategory") or ""
            ).classes("w-full")
            provider = ui.input("Comercio", value=product.get("provider") or "").classes("w-full")

        def apply() -> None:
            new_name = (name.value or "").strip()
            if not new_name:
                ui.notify("El nombre es obligatorio.", type="warning")
                return
            stamp = now_ms()
            updated = dict(product)
            updated.update(
                {
                    "name": new_name,
                    "name_lower": new_name.lower(),
                    "categoryId": category.value,
                    "brand": brand.value or "",
                    "unit": unit.value or "unidad",
                    "subcategory": subcategory.value or "",
                    "provider": provider.value or "",
                    "updatedAt": stamp,
                }
            )
            state.repo.put("products", updated)
            # El ajuste propaga nombre y categoría a las compras del SKU.
            for tx in domain_products.rename_product_transactions(
                state.transactions(), product.get("id"), new_name, category.value or ""
            ):
                state.repo.put("transactions", tx)
            state.refresh()
            state.notify()
            dialog.close()
            refresh_table()
            ui.notify("SKU actualizado.", type="positive")

        with ui.row().classes("gap-2 mt-2"):
            ui.button("Guardar", on_click=apply).props("color=primary unelevated")
            ui.button("Cancelar", on_click=dialog.close).props("flat")
    dialog.open()


def _delete(state: AppState, product: dict[str, Any], refresh_table: Callable[[], None]) -> None:
    linked = len(
        [tx for tx in state.transactions() if tx.get("productId") == product.get("id")]
    )
    with ui.dialog() as dialog, c.card():
        c.section_title("Borrar SKU")
        ui.html(
            f'<div>¿Borrar <b>{_esc(product.get("name"))}</b>? '
            f"{linked} compras quedarán sin SKU (no se borran).</div>"
        )

        def confirm() -> None:
            state.repo.delete("products", product.get("id"))
            state.refresh()
            state.notify()
            dialog.close()
            refresh_table()
            ui.notify("SKU borrado.", type="positive")

        with ui.row().classes("gap-2 mt-2"):
            ui.button("Borrar", on_click=confirm).props("color=negative unelevated")
            ui.button("Cancelar", on_click=dialog.close).props("flat")
    dialog.open()


def _esc(value: Any) -> str:
    return escape_html(value)


def render(state: AppState) -> None:
    @ui.refreshable
    def content() -> None:
        _build(state)

    content()
    state.subscribe(content.refresh)
