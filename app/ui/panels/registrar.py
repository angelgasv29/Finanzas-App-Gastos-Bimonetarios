"""Panel 2 · Registrar: alta de compras con desglose de IVA.

Reutiliza las funciones de :mod:`app.domain.transactions` (validación, resolución
del SKU y construcción del registro) y :mod:`app.domain.vat` (vista previa). La
interfaz solo recoge los valores y los muestra.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from nicegui import ui

from ...core.constants import (
    NATURE_OPTIONS,
    PAYMENT_METHODS,
    PAYMENT_ORIGINS,
    UNIT_OPTIONS,
    get_origin_label,
)
from ...domain import prices as domain_prices
from ...domain import transactions as domain_tx
from ...domain import vat
from ...domain.errors import DomainError
from .. import components as c
from ..state import AppState

__all__ = ["render"]

VAT_LABELS = {"exento": "Exento", "incluido": "IVA incluido", "mas_iva": "IVA + 16%"}


def _custom_input(field: dict[str, Any], value: Any = None) -> ui.element:
    """Campo personalizado de una categoría (``customFields``).

    Reproduce los cuatro tipos de la versión de referencia: ``text``, ``number``, ``select`` y
    ``boolean``. El asterisco marca los obligatorios, igual que el atributo
    ``required`` del HTML.
    """
    label = (field.get("label") or "Campo") + (" *" if field.get("required") else "")
    kind = field.get("type") or "text"
    if kind == "number":
        try:
            start = float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            start = None
        element = ui.number(label, value=start, step=0.0001).classes("w-full")
    elif kind == "boolean":
        element = ui.checkbox(label, value=bool(value))
    elif kind == "select":
        options = [str(item) for item in (field.get("options") or [])]
        element = ui.select(
            options, value=value or None, label=label, clearable=True
        ).classes("w-full")
    else:
        element = ui.input(label, value="" if value is None else str(value)).classes(
            "w-full"
        )
    if field.get("id"):
        element.mark(f"cf-{field['id']}")
    return element


def _custom_value(field: dict[str, Any], widget: ui.element) -> Any:
    """Valor tal como lo guardaba la versión de referencia (texto, número como texto, bool)."""
    kind = field.get("type") or "text"
    if kind == "boolean":
        return bool(widget.value)
    if kind == "select":
        return widget.value or ""
    if kind == "number":
        return "" if widget.value is None else str(widget.value)
    return widget.value or ""


def _product_label(product: dict[str, Any], category_name: str = "") -> str:
    """Etiqueta buscable del catálogo: nombre, SKU y metadatos útiles."""
    parts = [
        product.get("name"),
        product.get("id"),
        category_name,
        product.get("brand"),
        product.get("provider"),
        product.get("unit"),
    ]
    return " · ".join(str(part) for part in parts if part not in (None, ""))


def _last_transaction_for(
    transactions: list[dict[str, Any]], product: dict[str, Any]
) -> dict[str, Any] | None:
    """Compra más reciente del producto, por ``productId`` o por nombre.

    Las compras antiguas pueden no tener ``productId``; en ese caso se comparan
    por nombre. El desempate usa la fecha y el ``id`` para que el resultado sea
    estable.
    """
    product_id = product.get("id")
    name_lower = str(product.get("name") or "").casefold()
    matches: list[dict[str, Any]] = []
    if product_id:
        matches = [tx for tx in transactions if tx.get("productId") == product_id]
    if not matches and name_lower:
        matches = [
            tx
            for tx in transactions
            if not tx.get("productId")
            and str(tx.get("productName") or "").casefold() == name_lower
        ]
    if not matches:
        return None
    return max(
        matches,
        key=lambda tx: (str(tx.get("date") or ""), tx.get("id") or 0),
    )


def _build(state: AppState) -> None:
    now_date = dt.date.today().isoformat()
    rate = state.active_rate

    if not state.categories:
        with ui.column().classes("w-full p-4"):
            with c.card():
                ui.html(c.empty_html("No hay categorías en este entorno. Créalas en «Categorías»."))
        return

    category_options = {cat["id"]: cat["name"] for cat in state.categories}
    first_category = next(iter(category_options))
    products_sorted = sorted(
        state.products, key=lambda item: str(item.get("name") or "").casefold()
    )
    product_by_id = {
        product["id"]: product
        for product in products_sorted
        if product.get("id")
    }
    product_options = {
        product["id"]: _product_label(
            product, state.category_name(product.get("categoryId"))
        )
        for product in products_sorted
        if product.get("id")
    }

    with ui.column().classes("w-full gap-4 p-4"):
        with c.card():
            c.section_title(
                "Registrar compra",
                (
                    c.chip_html(f"Tasa {state.rate_value:.4g} Bs/USD", "brand")
                    if rate
                    else c.chip_html("Sin tasa", "bad")
                ),
            )

            with ui.row().classes("w-full items-center gap-3"):
                f_pick = ui.select(
                    product_options,
                    label="Autocompletar producto",
                    with_input=True,
                    clearable=True,
                ).props("outlined dense prepend-icon=search").classes(
                    "w-full md:w-2/3"
                ).mark("reg-product-picker")
                ui.html(
                    '<div class="muted">Filtra por nombre, SKU, categoría, marca '
                    "o comercio.</div>"
                ).classes("text-sm")

            autofill_hint = ui.html(
                '<div class="muted">Elige un producto del catálogo para reutilizar '
                "sus datos.</div>"
            ).classes("w-full")

            with ui.row().classes("grid grid-cols-2 md:grid-cols-4 gap-3 w-full items-end"):
                f_date = ui.input("Fecha", value=now_date).props("type=date").classes("w-full")
                f_cat = ui.select(
                    category_options, value=first_category, label="Categoría"
                ).classes("w-full")
                f_name = ui.input("Producto").classes("w-full").mark("reg-product")
                with ui.element("div").classes("w-full") as qty_box:
                    f_qty = ui.number("Cantidad", value=None, min=0).classes("w-full")
                with ui.element("div").classes("w-full") as unit_box:
                    f_unit = ui.select(list(UNIT_OPTIONS), value="unidad", label="Unidad").classes("w-full")
                with ui.element("div").classes("w-full") as brand_box:
                    f_brand = ui.input("Marca").classes("w-full")
                with ui.element("div").classes("w-full") as sub_box:
                    f_sub = ui.input("Subcategoría").classes("w-full")
                with ui.element("div").classes("w-full") as prov_box:
                    f_prov = ui.input("Comercio").classes("w-full")
                f_pay = ui.select(list(PAYMENT_METHODS), value=None, label="Forma de pago").classes("w-full")
                f_origin = ui.select(
                    list(PAYMENT_ORIGINS), value=None, label="Plataforma origen"
                ).classes("w-full")
                f_nature = ui.select(
                    list(NATURE_OPTIONS), value="Recurrente", label="Naturaleza"
                ).classes("w-full")
                f_mode = ui.select(VAT_LABELS, value="incluido", label="Modalidad IVA").classes("w-full")
                f_bs = ui.number("Monto Bs", value=0, min=0, format="%.2f").classes("w-full").mark("reg-bs")
                f_usd = ui.number("Monto USD (opcional)", value=None, min=0, format="%.4f").classes("w-full")

            custom_box = ui.column().classes("w-full gap-2")
            custom_inputs: dict[str, ui.element] = {}
            autofill_custom: dict[str, Any] = {}

            def render_custom_fields() -> None:
                """Pinta los ``customFields`` de la categoría elegida."""
                custom_box.clear()
                custom_inputs.clear()
                category = next(
                    (item for item in state.categories if item.get("id") == f_cat.value),
                    None,
                )
                fields = (category or {}).get("customFields") or []
                if not fields:
                    return
                with custom_box:
                    ui.html('<div class="sec-title">Campos personalizados</div>')
                    with ui.row().classes(
                        "grid grid-cols-1 md:grid-cols-3 gap-3 w-full"
                    ):
                        for field in fields:
                            custom_inputs[field.get("id")] = _custom_input(
                                field, autofill_custom.get(field.get("id"))
                            )

            preview = ui.html("").classes("muted")
            alert_box = ui.html("").classes("w-full")

            field_boxes = {
                "quantity": (qty_box, f_qty),
                "unit": (unit_box, f_unit),
                "brand": (brand_box, f_brand),
                "subcategory": (sub_box, f_sub),
                "provider": (prov_box, f_prov),
            }

            selected_product_id: str | None = None
            guard = {"product": False}

            def apply_category_fields() -> None:
                """Muestra solo los campos que habilita la categoría elegida."""
                category = next(
                    (item for item in state.categories if item.get("id") == f_cat.value),
                    None,
                )
                enabled = (category or {}).get("enabledFields") or {}
                for key, (box, widget) in field_boxes.items():
                    visible = bool(enabled.get(key, True))
                    if not visible:
                        widget.value = None if key == "quantity" else ""
                    box.set_visibility(visible)
                render_custom_fields()

            def on_category_change() -> None:
                if not guard["product"]:
                    autofill_custom.clear()
                apply_category_fields()

            apply_category_fields()
            f_cat.on_value_change(lambda _e=None: on_category_change())

            def current_product_name() -> str:
                value = f_name.value
                if value in product_by_id:
                    return str(product_by_id[value].get("name") or "")
                return str(value or "").strip()

            def refresh_preview() -> None:
                view = vat.vat_preview(
                    f_bs.value, f_mode.value, state.rate_value, state.money
                )
                preview.content = (
                    f'<div class="row wrap" style="gap:8px">'
                    f'{c.chip_html("Base " + view["vpBaseBs"])}'
                    f'{c.chip_html("IVA " + view["vpIvaBs"])}'
                    f'{c.chip_html("Total " + view["vpTotalBs"], "brand")}'
                    f'{c.chip_html("≈ " + view["vpTotalUsd"])}'
                    f"</div>"
                )
                name = current_product_name()
                history = [
                    tx
                    for tx in state.transactions()
                    if (tx.get("productName") or "").casefold()
                    == name.casefold()
                ]
                result = domain_prices.price_alert_for_form(
                    product_id=selected_product_id or "",
                    product_name=name,
                    products=state.products,
                    history=history,
                    quantity=f_qty.value,
                    bs_amount=f_bs.value,
                    rate_value=state.rate_value,
                    unit=f_unit.value or "unidad",
                    vat_mode=f_mode.value or "incluido",
                )
                if result is None:
                    alert_box.content = ""
                else:
                    view_alert = domain_prices.price_alert_view(result)
                    kind = {"ok": "ok", "warn": "warn", "bad": "bad"}[result.level]
                    alert_box.content = c.chip_html(
                        f"{view_alert['title']} · media {view_alert['avg']} · "
                        f"mínimo {view_alert['lowest']} ({view_alert['lowWhere']})",
                        kind,
                    )

            def apply_product(product: dict[str, Any]) -> None:
                """Recupera los datos del catálogo y de la última compra."""
                last = _last_transaction_for(state.transactions(), product)
                guard["product"] = True
                try:
                    f_name.value = str(product.get("name") or "")
                    f_cat.value = product.get("categoryId") or f_cat.value
                    f_brand.value = (last or {}).get("brand") or product.get("brand") or ""
                    f_unit.value = (last or {}).get("unit") or product.get("unit") or "unidad"
                    f_sub.value = (
                        (last or {}).get("subcategory")
                        or product.get("subcategory")
                        or ""
                    )
                    f_prov.value = (
                        (last or {}).get("provider") or product.get("provider") or ""
                    )
                    f_pay.value = (last or {}).get("paymentMethod") or None
                    f_origin.value = (last or {}).get("originPlatform") or None
                    f_nature.value = (last or {}).get("nature") or "Recurrente"
                    f_mode.value = (last or {}).get("taxMode") or "incluido"
                    f_qty.value = (last or {}).get("quantity")
                    f_bs.value = 0
                    f_usd.value = None
                    autofill_custom.clear()
                    if last:
                        autofill_custom.update(last.get("customValues") or {})
                finally:
                    guard["product"] = False

                apply_category_fields()
                if last:
                    autofill_hint.content = c.chip_html(
                        "Autocompletado desde la última compra del "
                        f"{last.get('date') or '—'} · "
                        f"{state.fmt(last.get('amountUsd'), last.get('amountBs'))} · "
                        f"SKU {product.get('id')}",
                        "ok",
                    )
                else:
                    autofill_hint.content = c.chip_html(
                        f"Producto del catálogo · SKU {product.get('id')}", "brand"
                    )
                refresh_preview()

            def on_product_change() -> None:
                nonlocal selected_product_id
                value = f_pick.value
                product = product_by_id.get(value) if value else None
                if product is None:
                    selected_product_id = None
                    autofill_hint.content = (
                        '<div class="muted">Elige un producto del catálogo para '
                        "reutilizar sus datos.</div>"
                    )
                else:
                    selected_product_id = product["id"]
                    apply_product(product)
                refresh_preview()

            def on_name_change() -> None:
                nonlocal selected_product_id
                if guard["product"]:
                    return
                product = product_by_id.get(selected_product_id) if selected_product_id else None
                if product and current_product_name().casefold() != str(
                    product.get("name") or ""
                ).casefold():
                    selected_product_id = None
                    f_pick.value = None
                    autofill_hint.content = c.chip_html(
                        "Producto nuevo: se creará un SKU al guardar.", "warn"
                    )
                refresh_preview()

            for widget in (f_bs, f_mode, f_qty, f_unit):
                widget.on_value_change(lambda _e=None: refresh_preview())
            f_name.on_value_change(lambda _e=None: on_name_change())
            f_pick.on_value_change(lambda _e=None: on_product_change())
            f_usd.on_value_change(
                lambda _e=None: _apply_usd()
            )

            def _apply_usd() -> None:
                value = f_usd.value
                if value and state.rate_value:
                    f_bs.value = round(float(value) * state.rate_value, 2)
                    refresh_preview()

            def reset_form() -> None:
                nonlocal selected_product_id
                selected_product_id = None
                guard["product"] = True
                try:
                    f_date.value = now_date
                    f_cat.value = first_category
                    f_name.value = ""
                    f_qty.value = None
                    f_unit.value = "unidad"
                    f_brand.value = ""
                    f_sub.value = ""
                    f_prov.value = ""
                    f_pay.value = None
                    f_origin.value = None
                    f_nature.value = "Recurrente"
                    f_mode.value = "incluido"
                    f_bs.value = 0
                    f_usd.value = None
                finally:
                    guard["product"] = False
                f_pick.value = None
                autofill_custom.clear()
                autofill_hint.content = (
                    '<div class="muted">Elige un producto del catálogo para '
                    "reutilizar sus datos.</div>"
                )
                apply_category_fields()
                refresh_preview()

            def save() -> None:
                name = current_product_name()
                try:
                    domain_tx.validate(f_cat.value, f_date.value, name, f_bs.value)
                    domain_tx.require_rate(rate)
                except DomainError as exc:
                    ui.notify(str(exc), type="warning")
                    return

                product_id, created = domain_tx.resolve_product(
                    state.products,
                    state.workspace,
                    name,
                    category_id=f_cat.value,
                    brand=f_brand.value or "",
                    unit=f_unit.value or "",
                    subcategory=f_sub.value or "",
                    provider=f_prov.value or "",
                    product_id=selected_product_id,
                )
                if created is not None:
                    state.repo.put("products", created)

                category = next(
                    (item for item in state.categories if item.get("id") == f_cat.value),
                    None,
                )
                custom_values = {
                    field["id"]: _custom_value(field, custom_inputs[field["id"]])
                    for field in (category or {}).get("customFields") or []
                    if field.get("id") in custom_inputs
                }

                record = domain_tx.build_transaction(
                    workspace=state.workspace,
                    date=f_date.value,
                    category_id=f_cat.value,
                    product_name=name,
                    rate=rate,
                    bs_amount=f_bs.value,
                    mode=f_mode.value or "incluido",
                    product_id=product_id,
                    quantity=f_qty.value,
                    unit=f_unit.value or "",
                    brand=f_brand.value or "",
                    subcategory=f_sub.value or "",
                    provider=f_prov.value or "",
                    payment_method=f_pay.value or "",
                    origin_platform=f_origin.value or "",
                    nature=f_nature.value or "",
                    custom_values=custom_values,
                )
                state.repo.add("transactions", record)
                state.refresh()
                state.notify()
                ui.notify("Compra registrada.", type="positive")
                reset_form()

            with ui.row().classes("gap-2 mt-2"):
                ui.button("Guardar compra", on_click=save).props("color=primary unelevated").mark("reg-save")
                ui.button("Limpiar", on_click=reset_form).props("flat")

            refresh_preview()

        with c.card():
            txs = sorted(
                state.transactions(),
                key=lambda tx: (str(tx.get("date") or ""), tx.get("id") or 0),
                reverse=True,
            )
            c.section_title("Movimientos recientes", c.chip_html(f"{len(txs)} en total"))
            if not txs:
                ui.html(c.empty_html("Todavía no hay movimientos en este entorno."))
                return
            c.data_table(
                ["#", "Fecha", "Producto", "Categoría", "Comercio", "Origen", "Total"],
                [
                    (
                        str(tx.get("id")),
                        tx.get("date") or "—",
                        tx.get("productName") or "—",
                        state.category_name(tx.get("categoryId")) or "—",
                        tx.get("provider") or "—",
                        get_origin_label(tx),
                        state.fmt(tx.get("amountUsd"), tx.get("amountBs")),
                    )
                    for tx in txs[:20]
                ],
                align_right=(6,),
            )

        # El original corregía las compras con ``openTxEditor`` (editar o borrar).
        if txs:
            with c.card():
                c.section_title("Corregir un movimiento")
                ui.html(
                    '<div class="muted">Elige una compra para editar sus datos o para '
                    "borrarla. La lista muestra las 50 más recientes.</div>"
                )
                options = {
                    tx.get("id"): (
                        f'#{tx.get("id")} · {tx.get("date") or "—"} · '
                        f'{tx.get("productName") or "—"} · '
                        f'{state.fmt(tx.get("amountUsd"), tx.get("amountBs"))}'
                    )
                    for tx in txs[:50]
                }
                pick = ui.select(options, label="Movimiento", with_input=True).classes(
                    "w-full"
                )

                def chosen() -> dict[str, Any] | None:
                    tx_id = pick.value
                    if tx_id is None:
                        ui.notify("Elige un movimiento.", type="warning")
                        return None
                    return next((tx for tx in txs if tx.get("id") == tx_id), None)

                def edit() -> None:
                    tx = chosen()
                    if tx is not None:
                        _open_editor(state, tx)

                def remove() -> None:
                    tx = chosen()
                    if tx is not None:
                        _confirm_delete(state, tx)

                with ui.row().classes("gap-2"):
                    ui.button("Editar", on_click=edit).props("outline color=primary")
                    ui.button("Borrar", on_click=remove).props("outline color=negative")


def _open_editor(state: AppState, tx: dict[str, Any]) -> None:
    """Editor de una compra (``openTxEditor``, líneas 4278-4400).

    Edita los mismos campos que el original y reutiliza
    :func:`app.domain.transactions.apply_edit` para recalcular base, IVA, total y
    USD. La categoría y el ``productId`` no se tocan (igual que el original).
    """
    category = next(
        (item for item in state.categories if item.get("id") == tx.get("categoryId")),
        None,
    )
    enabled = (category or {}).get("enabledFields") or {}
    today = dt.date.today().isoformat()

    with ui.dialog() as dialog, c.card() as box:
        box.style("max-width: 720px")
        c.section_title(f"Editar compra #{tx.get('id')}")

        with ui.row().classes("grid grid-cols-1 md:grid-cols-2 gap-3 w-full"):
            e_date = ui.input(
                "Fecha", value=tx.get("date") or today
            ).props("type=date").classes("w-full").mark("edit-date")
            e_name = ui.input(
                "Producto", value=tx.get("productName") or ""
            ).classes("w-full").mark("edit-product")

        with ui.row().classes("grid grid-cols-1 md:grid-cols-2 gap-3 w-full"):
            e_bs = ui.number(
                "Monto Bs",
                value=float(tx.get("amountBs") or 0),
                min=0,
                format="%.2f",
            ).classes("w-full").mark("edit-bs")
            e_usd = ui.number(
                "Monto USD",
                value=float(tx.get("amountUsd") or 0),
                min=0,
                format="%.4f",
            ).classes("w-full").mark("edit-usd")

        with ui.row().classes("grid grid-cols-1 md:grid-cols-2 gap-3 w-full"):
            e_mode = ui.select(
                VAT_LABELS,
                value=tx.get("taxMode") or "incluido",
                label="Modalidad IVA",
            ).classes("w-full").mark("edit-mode")
            e_rate = ui.number(
                "Tasa (Bs/$)",
                value=float(tx.get("rate") or state.rate_value or 0),
                min=0,
                format="%.4f",
            ).classes("w-full").mark("edit-rate")

        e_qty = (
            ui.number(
                "Cantidad", value=tx.get("quantity"), min=0
            ).classes("w-full")
            if enabled.get("quantity")
            else None
        )
        e_unit = (
            ui.input("Unidad", value=tx.get("unit") or "").classes("w-full")
            if enabled.get("unit")
            else None
        )
        e_brand = (
            ui.input("Marca", value=tx.get("brand") or "").classes("w-full")
            if enabled.get("brand")
            else None
        )
        e_provider = (
            ui.input("Comercio", value=tx.get("provider") or "").classes("w-full")
            if enabled.get("provider")
            else None
        )
        e_origin = (
            ui.select(
                {origin: origin for origin in PAYMENT_ORIGINS},
                value=tx.get("originPlatform") or None,
                label="Plataforma origen",
                clearable=True,
            ).classes("w-full")
            if enabled.get("originPlatform")
            else None
        )

        e_notes = ui.textarea(
            "Notas", value=tx.get("notes") or ""
        ).classes("w-full")

        custom_fields = (category or {}).get("customFields") or []
        edit_custom: dict[str, ui.element] = {}
        if custom_fields:
            ui.html('<div class="sec-title">Campos personalizados</div>')
            with ui.row().classes("grid grid-cols-1 md:grid-cols-3 gap-3 w-full"):
                stored_values = tx.get("customValues") or {}
                for field in custom_fields:
                    edit_custom[field.get("id")] = _custom_input(
                        field, stored_values.get(field.get("id"))
                    )

        preview = ui.html("").classes("muted")

        def show_preview() -> None:
            view = vat.vat_preview(
                e_bs.value, e_mode.value or "incluido", e_rate.value, state.money
            )
            preview.content = (
                '<div class="row wrap" style="gap:8px">'
                + c.chip_html("Base " + view["vpBaseBs"])
                + c.chip_html("IVA " + view["vpIvaBs"])
                + c.chip_html("Total " + view["vpTotalBs"], "brand")
                + c.chip_html("≈ " + view["vpTotalUsd"])
                + "</div>"
            )

        # ``wireEditRecalc``: al escribir en un campo se recalculan los otros.
        guard = {"on": False}

        def recalc(field: str) -> None:
            if guard["on"]:
                return
            result = domain_tx.editor_recalc(
                field, e_bs.value, e_usd.value, e_rate.value
            )
            guard["on"] = True
            try:
                if result.get("txAmountUsd") is not None:
                    e_usd.value = float(result["txAmountUsd"])
                if result.get("txAmountBs") is not None:
                    e_bs.value = float(result["txAmountBs"])
            finally:
                guard["on"] = False
            show_preview()

        e_bs.on_value_change(lambda _e=None: recalc("bs"))
        e_usd.on_value_change(lambda _e=None: recalc("usd"))
        e_rate.on_value_change(lambda _e=None: recalc("rate"))
        e_mode.on_value_change(lambda _e=None: show_preview())
        show_preview()

        def save() -> None:
            name = (e_name.value or "").strip()
            if not name or not e_bs.value or float(e_bs.value) <= 0:
                ui.notify("Completa el producto y el monto.", type="warning")
                return
            updated = domain_tx.apply_edit(
                tx,
                date=e_date.value or tx.get("date") or today,
                product_name=name,
                bs_amount=e_bs.value,
                usd_amount=e_usd.value,
                mode=e_mode.value or "incluido",
                rate_value=e_rate.value,
                quantity=(
                    e_qty.value if e_qty is not None else tx.get("quantity")
                ),
                unit=e_unit.value if e_unit is not None else tx.get("unit"),
                brand=e_brand.value if e_brand is not None else tx.get("brand"),
                provider=(
                    e_provider.value if e_provider is not None else tx.get("provider")
                ),
                origin_platform=(
                    e_origin.value
                    if e_origin is not None
                    else tx.get("originPlatform")
                ),
                notes=e_notes.value or "",
                custom_values={
                    field["id"]: _custom_value(field, edit_custom[field["id"]])
                    for field in custom_fields
                    if field["id"] in edit_custom
                },
            )
            state.repo.put("transactions", updated)
            state.refresh()
            state.notify()
            dialog.close()
            ui.notify("Compra actualizada.", type="positive")

        with ui.row().classes("gap-2 mt-2"):
            ui.button("Guardar cambios", on_click=save).props(
                "color=primary unelevated"
            ).mark("edit-save")
            ui.button("Cancelar", on_click=dialog.close).props("flat")
    dialog.open()


def _confirm_delete(state: AppState, tx: dict[str, Any]) -> None:
    """Confirmación de borrado de una compra (la lista no tiene papelera)."""
    with ui.dialog() as dialog, c.card():
        c.section_title("Borrar movimiento")
        ui.html(
            f'<div>¿Borrar <b>{tx.get("productName") or "—"}</b> '
            f'del {tx.get("date") or "—"} por '
            f'{state.fmt(tx.get("amountUsd"), tx.get("amountBs"))}? '
            "Esta acción no se puede deshacer.</div>"
        )

        def confirm() -> None:
            state.repo.delete("transactions", tx.get("id"))
            state.refresh()
            state.notify()
            dialog.close()
            ui.notify("Movimiento borrado.", type="positive")

        with ui.row().classes("gap-2 mt-2"):
            ui.button("Borrar", on_click=confirm).props("color=negative unelevated")
            ui.button("Cancelar", on_click=dialog.close).props("flat")
    dialog.open()


def render(state: AppState) -> None:
    @ui.refreshable
    def content() -> None:
        _build(state)

    content()
    state.subscribe(content.refresh)
