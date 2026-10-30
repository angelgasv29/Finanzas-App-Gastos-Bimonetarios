"""Panel 2 · Registrar: alta de compras con desglose de IVA.

Reutiliza las funciones de :mod:`app.domain.transactions` (validación, resolución
del SKU y construcción del registro) y :mod:`app.domain.vat` (vista previa). La
interfaz solo recoge los valores y los muestra.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Callable

from nicegui import ui

from ...core.constants import (
    NATURE_OPTIONS,
    PAYMENT_METHODS,
    PAYMENT_ORIGINS,
    UNIT_OPTIONS,
    get_origin_label,
)
from ...core.suggestions import best_match, normalize_text, similar_values
from ...domain import prices as domain_prices
from ...domain import transactions as domain_tx
from ...domain import vat
from ...domain.errors import DomainError
from .. import components as c
from ..state import AppState

__all__ = ["render"]

VAT_LABELS = {
    "exento": "Exento",
    "incluido": "IVA incluido",
    "mas_iva": "IVA + tasa indicada",
}
DEFAULT_VAT_PERCENT = 16.0


def _vat_percent(value: Any) -> float:
    """Convierte la fracción guardada (0,16) en porcentaje para la interfaz."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return DEFAULT_VAT_PERCENT
    if number <= 1:
        number *= 100
    return round(max(0.0, min(100.0, number)), 4)


def _custom_input(field: dict[str, Any], value: Any = None) -> ui.element:
    """Campo personalizado de una categoría (``customFields``).

    Reproduce los cuatro tipos del original: ``text``, ``number``, ``select`` y
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
    """Valor tal como lo guardaba el original (texto, número como texto, bool)."""
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


def _render_suggestions(
    box: ui.element,
    query: str,
    values: list[str],
    on_pick: Callable[[str], None],
    *,
    include_exact: bool = False,
    label: str = "Quizás quisiste decir",
) -> None:
    """Pinta debajo de un campo los valores existentes más parecidos.

    ``include_exact`` sirve para el producto: si el nombre ya existe, conviene
    ofrecer «Usar ficha existente» para recuperar marca, comercio y última
    compra. En los demás campos una coincidencia exacta no necesita sugerencia.
    """
    box.clear()
    if not str(query or "").strip():
        return
    matches = similar_values(query, values, limit=3, cutoff=0.68)
    wanted = normalize_text(query)
    if not include_exact:
        matches = [
            item for item in matches if normalize_text(item[0]) != wanted
        ]
    if not matches:
        return

    with box:
        ui.html(f'<div class="muted text-xs">{label}</div>')
        with ui.row().classes("w-full gap-1 flex-wrap"):
            for value, _score, count in matches:
                if normalize_text(value) == wanted:
                    text = f"Usar «{value}»"
                else:
                    suffix = f" · {count}" if count > 1 else ""
                    text = f"{value}{suffix}"
                ui.button(
                    text,
                    on_click=lambda selected=value: on_pick(selected),
                ).props("flat dense no-caps size=sm").classes("text-left")


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
    context = state.register_context if state.register_context.get("keep", True) else {}
    initial_date = str(context.get("date") or now_date)
    initial_category = context.get("category_id")
    if initial_category not in category_options:
        initial_category = first_category
    initial_vat = context.get("vat_percent", DEFAULT_VAT_PERCENT)
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
    product_names = [
        str(product.get("name") or "").strip()
        for product in products_sorted
        if str(product.get("name") or "").strip()
    ]
    product_by_name = {
        str(product.get("name") or "").strip(): product
        for product in products_sorted
        if str(product.get("name") or "").strip()
    }
    existing_transactions = state.transactions()

    def existing_values(field: str) -> list[str]:
        """Valores ya usados en el catálogo o en el histórico."""
        values: list[str] = []
        for item in [*state.products, *existing_transactions]:
            value = str(item.get(field) or "").strip()
            if value:
                values.append(value)
        return values

    provider_values = existing_values("provider")
    brand_values = existing_values("brand")
    subcategory_values = existing_values("subcategory")

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
                with ui.element("div").classes("w-full"):
                    f_date = ui.input("Fecha", value=initial_date).props("type=date").classes("w-full").mark("reg-date")
                    date_hint = ui.html("").classes("muted text-xs")
                f_cat = ui.select(
                    category_options, value=initial_category, label="Categoría"
                ).classes("w-full").mark("reg-category")
                with ui.element("div").classes("w-full") as name_box:
                    f_name = ui.input("Producto").classes("w-full").mark("reg-product")
                    name_suggest = ui.column().classes("w-full gap-1").mark(
                        "reg-product-suggestions"
                    )
                with ui.element("div").classes("w-full") as qty_box:
                    f_qty = ui.number("Cantidad", value=None, min=0).classes("w-full")
                with ui.element("div").classes("w-full") as unit_box:
                    f_unit = ui.select(list(UNIT_OPTIONS), value="unidad", label="Unidad").classes("w-full")
                with ui.element("div").classes("w-full") as brand_box:
                    f_brand = ui.input("Marca").classes("w-full").mark("reg-brand")
                    brand_suggest = ui.column().classes("w-full gap-1").mark(
                        "reg-brand-suggestions"
                    )
                with ui.element("div").classes("w-full") as sub_box:
                    f_sub = ui.input("Subcategoría").classes("w-full").mark("reg-subcategory")
                    sub_suggest = ui.column().classes("w-full gap-1").mark(
                        "reg-subcategory-suggestions"
                    )
                with ui.element("div").classes("w-full") as prov_box:
                    f_prov = ui.input("Comercio").classes("w-full").mark("reg-provider")
                    prov_suggest = ui.column().classes("w-full gap-1").mark(
                        "reg-provider-suggestions"
                    )
                f_pay = ui.select(list(PAYMENT_METHODS), value=None, label="Forma de pago").classes("w-full")
                f_origin = ui.select(
                    list(PAYMENT_ORIGINS), value=None, label="Plataforma origen"
                ).classes("w-full")
                f_nature = ui.select(
                    list(NATURE_OPTIONS), value="Recurrente", label="Naturaleza"
                ).classes("w-full")
                f_mode = ui.select(VAT_LABELS, value="incluido", label="Modalidad IVA").classes("w-full")
                f_vat_rate = ui.number(
                    "Tasa IVA (%)",
                    value=initial_vat,
                    min=0,
                    max=100,
                    step=0.01,
                    format="%.2f",
                ).classes("w-full").mark("reg-vat-rate")
                f_bs = ui.number("Monto Bs", value=0, min=0, format="%.2f").classes("w-full").mark("reg-bs")
                f_usd = ui.number("Monto USD (opcional)", value=None, min=0, format="%.4f").classes("w-full")

            ui.html(
                '<div class="muted text-xs">La tasa de IVA se guarda con cada '
                "compra. 16 % es el valor inicial; cámbialo si la normativa "
                "aplicable o el ticket indican otra alícuota. Esta herramienta "
                "no sustituye asesoría fiscal.</div>"
            ).classes("w-full")

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

            def current_vat_rate() -> float:
                value = f_vat_rate.value
                return 0.0 if value is None else float(value) / 100

            def refresh_preview() -> None:
                view = vat.vat_preview(
                    f_bs.value,
                    f_mode.value,
                    state.rate_value,
                    state.money,
                    current_vat_rate(),
                )
                preview.content = (
                    f'<div class="row wrap" style="gap:8px">'
                    f'{c.chip_html("Base " + view["vpBaseBs"])}'
                    f'{c.chip_html("IVA " + view["vpIvaBs"])}'
                    f'{c.chip_html("Total " + view["vpTotalBs"], "brand")}'
                    f'{c.chip_html("≈ " + view["vpTotalUsd"])}'
                    f'{c.chip_html(f"Tasa IVA {float(f_vat_rate.value or 0):.2f}%")}'
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
                    f_vat_rate.value = _vat_percent(
                        (last or {}).get("ivaRate", DEFAULT_VAT_PERCENT / 100)
                    )
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

            def pick_product_name(value: str) -> None:
                product = product_by_name.get(value)
                if product is None:
                    f_name.value = value
                    return
                f_pick.value = product.get("id")
                if f_pick.value != product.get("id"):
                    f_name.value = value
                name_suggest.clear()

            def update_name_suggestions() -> None:
                if selected_product_id:
                    name_suggest.clear()
                    return
                _render_suggestions(
                    name_suggest,
                    str(f_name.value or ""),
                    product_names,
                    pick_product_name,
                    include_exact=True,
                    label="Producto del catálogo",
                )

            def pick_brand(value: str) -> None:
                f_brand.value = value
                brand_suggest.clear()

            def pick_subcategory(value: str) -> None:
                f_sub.value = value
                sub_suggest.clear()

            def pick_provider(value: str) -> None:
                f_prov.value = value
                prov_suggest.clear()

            def update_brand_suggestions() -> None:
                if guard["product"]:
                    brand_suggest.clear()
                    return
                _render_suggestions(
                    brand_suggest,
                    str(f_brand.value or ""),
                    brand_values,
                    pick_brand,
                    label="Marca existente",
                )

            def update_subcategory_suggestions() -> None:
                if guard["product"]:
                    sub_suggest.clear()
                    return
                _render_suggestions(
                    sub_suggest,
                    str(f_sub.value or ""),
                    subcategory_values,
                    pick_subcategory,
                    label="Subcategoría existente",
                )

            def update_provider_suggestions() -> None:
                if guard["product"]:
                    prov_suggest.clear()
                    return
                _render_suggestions(
                    prov_suggest,
                    str(f_prov.value or ""),
                    provider_values,
                    pick_provider,
                    label="Comercio existente",
                )

            def on_name_field_change() -> None:
                on_name_change()
                update_name_suggestions()

            for widget in (f_bs, f_mode, f_vat_rate, f_qty, f_unit):
                widget.on_value_change(lambda _e=None: refresh_preview())
            f_name.on_value_change(lambda _e=None: on_name_field_change())
            f_brand.on_value_change(lambda _e=None: update_brand_suggestions())
            f_sub.on_value_change(lambda _e=None: update_subcategory_suggestions())
            f_prov.on_value_change(lambda _e=None: update_provider_suggestions())
            f_pick.on_value_change(lambda _e=None: on_product_change())
            f_usd.on_value_change(
                lambda _e=None: _apply_usd()
            )

            def _apply_usd() -> None:
                value = f_usd.value
                if value and state.rate_value:
                    f_bs.value = round(float(value) * state.rate_value, 2)
                    refresh_preview()

            def update_date_hint() -> None:
                today = dt.date.today().isoformat()
                if f_date.value and str(f_date.value) != today:
                    date_hint.content = c.chip_html(
                        f"Fecha fijada: {f_date.value}", "warn"
                    )
                else:
                    date_hint.content = (
                        '<div class="muted text-xs">Fecha de hoy</div>'
                    )

            def use_today() -> None:
                f_date.value = dt.date.today().isoformat()
                update_date_hint()

            f_date.on_value_change(lambda _e=None: update_date_hint())
            update_date_hint()

            with ui.row().classes("items-center gap-3 w-full"):
                sticky_context = ui.checkbox(
                    "Conservar fecha, categoría y tasa IVA al guardar",
                    value=bool(state.register_context.get("keep", True)),
                ).classes("text-sm").mark("reg-keep-context")
                ui.button("Usar fecha de hoy", on_click=use_today).props(
                    "flat dense"
                ).mark("reg-today")

            def reset_form(keep_context: bool = False) -> None:
                nonlocal selected_product_id
                kept_date = str(f_date.value or dt.date.today().isoformat())
                kept_category = f_cat.value or first_category
                kept_vat = (
                    f_vat_rate.value
                    if f_vat_rate.value is not None
                    else DEFAULT_VAT_PERCENT
                )
                if not keep_context:
                    state.register_context = {"keep": False}
                    sticky_context.value = False
                selected_product_id = None
                guard["product"] = True
                try:
                    f_date.value = (
                        kept_date if keep_context else dt.date.today().isoformat()
                    )
                    f_cat.value = (
                        kept_category if keep_context else first_category
                    )
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
                    f_vat_rate.value = (
                        kept_vat if keep_context else DEFAULT_VAT_PERCENT
                    )
                    f_bs.value = 0
                    f_usd.value = None
                finally:
                    guard["product"] = False
                f_pick.value = None
                for box in (name_suggest, brand_suggest, sub_suggest, prov_suggest):
                    box.clear()
                autofill_custom.clear()
                autofill_hint.content = (
                    '<div class="muted">Elige un producto del catálogo para '
                    "reutilizar sus datos.</div>"
                )
                apply_category_fields()
                update_date_hint()
                refresh_preview()

            def save() -> None:
                nonlocal selected_product_id
                name = current_product_name()
                vat_percent = (
                    DEFAULT_VAT_PERCENT
                    if f_vat_rate.value is None
                    else float(f_vat_rate.value)
                )
                if not 0 <= vat_percent <= 100:
                    ui.notify(
                        "La tasa de IVA debe estar entre 0 y 100 %.", type="warning"
                    )
                    return
                try:
                    domain_tx.validate(f_cat.value, f_date.value, name, f_bs.value)
                    domain_tx.require_rate(rate)
                except DomainError as exc:
                    ui.notify(str(exc), type="warning")
                    return

                # Una errata no debe crear un producto o un comercio paralelo.
                # Solo se corrige cuando el parecido es alto y tiene las mismas
                # palabras; así «Central Madeirense 2» sigue siendo una variante.
                corrections: list[str] = []
                product_match = best_match(name, product_names)
                matched_product = (
                    product_by_name.get(product_match) if product_match else None
                )
                if matched_product and (
                    name != product_match or selected_product_id != matched_product.get("id")
                ):
                    if name != product_match:
                        corrections.append(f"producto «{product_match}»")
                    name = str(matched_product.get("name") or product_match)
                    selected_product_id = matched_product.get("id")

                brand = str(f_brand.value or "").strip()
                brand_match = best_match(brand, brand_values)
                if brand_match and brand_match != brand:
                    corrections.append(f"marca «{brand_match}»")
                    brand = brand_match

                subcategory = str(f_sub.value or "").strip()
                subcategory_match = best_match(subcategory, subcategory_values)
                if subcategory_match and subcategory_match != subcategory:
                    corrections.append(f"subcategoría «{subcategory_match}»")
                    subcategory = subcategory_match

                provider = str(f_prov.value or "").strip()
                provider_match = best_match(provider, provider_values)
                if provider_match and provider_match != provider:
                    corrections.append(f"comercio «{provider_match}»")
                    provider = provider_match

                if corrections:
                    ui.notify(
                        "Se reutilizó: " + ", ".join(corrections) + ".",
                        type="info",
                    )

                product_id, created = domain_tx.resolve_product(
                    state.products,
                    state.workspace,
                    name,
                    category_id=f_cat.value,
                    brand=brand,
                    unit=f_unit.value or "",
                    subcategory=subcategory,
                    provider=provider,
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
                    iva_rate=vat_percent / 100,
                    product_id=product_id,
                    quantity=f_qty.value,
                    unit=f_unit.value or "",
                    brand=brand,
                    subcategory=subcategory,
                    provider=provider,
                    payment_method=f_pay.value or "",
                    origin_platform=f_origin.value or "",
                    nature=f_nature.value or "",
                    custom_values=custom_values,
                )
                state.repo.add("transactions", record)
                keep_context = bool(sticky_context.value)
                if keep_context:
                    state.register_context = {
                        "keep": True,
                        "date": str(f_date.value or dt.date.today().isoformat()),
                        "category_id": f_cat.value,
                        "vat_percent": vat_percent,
                    }
                else:
                    state.register_context = {"keep": False}
                state.refresh()
                state.notify()
                ui.notify("Compra registrada.", type="positive")

            with ui.row().classes("gap-2 mt-2"):
                ui.button("Guardar compra", on_click=save).props("color=primary unelevated").mark("reg-save")
                ui.button("Limpiar", on_click=lambda: reset_form(False)).props("flat")

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
    """Editor de una compra.

    Edita los mismos campos que el original, **incluida la categoría**, y
    reutiliza :func:`app.domain.transactions.apply_edit` para recalcular base,
    IVA, total y USD. La tasa de IVA queda guardada con la compra para que el
    histórico siga siendo auditable si la normativa cambia.
    """
    category_options = {cat["id"]: cat["name"] for cat in state.categories}
    if not category_options:
        ui.notify("Crea una categoría antes de editar una compra.", type="warning")
        return
    category_by_id = {cat["id"]: cat for cat in state.categories}
    current_category_id = tx.get("categoryId")
    if current_category_id not in category_options:
        current_category_id = None
    today = dt.date.today().isoformat()

    with ui.dialog() as dialog, c.card() as box:
        box.style("max-width: 760px")
        c.section_title(f"Editar compra #{tx.get('id')}")
        ui.html(
            '<div class="muted text-xs">Cambiar la categoría solo reclasifica '
            "esta compra; no borra ni duplica el movimiento.</div>"
        )

        with ui.row().classes("grid grid-cols-1 md:grid-cols-2 gap-3 w-full"):
            e_date = ui.input(
                "Fecha", value=tx.get("date") or today
            ).props("type=date").classes("w-full").mark("edit-date")
            e_name = ui.input(
                "Producto", value=tx.get("productName") or ""
            ).classes("w-full").mark("edit-product")

        e_cat = ui.select(
            category_options,
            value=current_category_id,
            label="Categoría",
        ).classes("w-full").mark("edit-category")

        with ui.row().classes("grid grid-cols-1 md:grid-cols-3 gap-3 w-full"):
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
            e_rate = ui.number(
                "Tasa (Bs/$)",
                value=float(tx.get("rate") or state.rate_value or 0),
                min=0,
                format="%.4f",
            ).classes("w-full").mark("edit-rate")

        with ui.row().classes("grid grid-cols-1 md:grid-cols-2 gap-3 w-full"):
            e_mode = ui.select(
                VAT_LABELS,
                value=tx.get("taxMode") or "incluido",
                label="Modalidad IVA",
            ).classes("w-full").mark("edit-mode")
            e_vat_rate = ui.number(
                "Tasa IVA (%)",
                value=_vat_percent(tx.get("ivaRate", DEFAULT_VAT_PERCENT / 100)),
                min=0,
                max=100,
                step=0.01,
                format="%.2f",
            ).classes("w-full").mark("edit-vat-rate")

        with ui.row().classes("grid grid-cols-1 md:grid-cols-3 gap-3 w-full"):
            with ui.element("div").classes("w-full") as qty_box:
                e_qty = ui.number(
                    "Cantidad", value=tx.get("quantity"), min=0
                ).classes("w-full")
            with ui.element("div").classes("w-full") as unit_box:
                e_unit = ui.input("Unidad", value=tx.get("unit") or "").classes(
                    "w-full"
                )
            with ui.element("div").classes("w-full") as brand_box:
                e_brand = ui.input("Marca", value=tx.get("brand") or "").classes(
                    "w-full"
                )

        with ui.row().classes("grid grid-cols-1 md:grid-cols-3 gap-3 w-full"):
            with ui.element("div").classes("w-full") as sub_box:
                e_sub = ui.input(
                    "Subcategoría", value=tx.get("subcategory") or ""
                ).classes("w-full")
            with ui.element("div").classes("w-full") as provider_box:
                e_provider = ui.input(
                    "Comercio", value=tx.get("provider") or ""
                ).classes("w-full")
            with ui.element("div").classes("w-full") as pay_box:
                e_pay = ui.select(
                    list(PAYMENT_METHODS),
                    value=tx.get("paymentMethod") or None,
                    label="Forma de pago",
                    clearable=True,
                ).classes("w-full")

        with ui.row().classes("grid grid-cols-1 md:grid-cols-2 gap-3 w-full"):
            with ui.element("div").classes("w-full") as origin_box:
                e_origin = ui.select(
                    list(PAYMENT_ORIGINS),
                    value=tx.get("originPlatform") or None,
                    label="Plataforma origen",
                    clearable=True,
                ).classes("w-full")
            with ui.element("div").classes("w-full") as nature_box:
                e_nature = ui.select(
                    list(NATURE_OPTIONS),
                    value=tx.get("nature") or None,
                    label="Naturaleza",
                    clearable=True,
                ).classes("w-full")

        e_notes = ui.textarea(
            "Notas", value=tx.get("notes") or ""
        ).classes("w-full")

        custom_box = ui.column().classes("w-full gap-2")
        edit_custom: dict[str, ui.element] = {}
        stored_custom = dict(tx.get("customValues") or {})

        def render_custom_fields() -> None:
            custom_box.clear()
            edit_custom.clear()
            category = category_by_id.get(e_cat.value) or {}
            fields = category.get("customFields") or []
            if not fields:
                return
            with custom_box:
                ui.html('<div class="sec-title">Campos personalizados</div>')
                ui.html(
                    '<div class="muted text-xs">Pertenecen a la categoría '
                    "elegida; si la cambias, se muestran los de la nueva.</div>"
                )
                with ui.row().classes(
                    "grid grid-cols-1 md:grid-cols-3 gap-3 w-full"
                ):
                    for field in fields:
                        edit_custom[field.get("id")] = _custom_input(
                            field, stored_custom.get(field.get("id"))
                        )

        field_boxes = {
            "quantity": (qty_box, e_qty),
            "unit": (unit_box, e_unit),
            "brand": (brand_box, e_brand),
            "subcategory": (sub_box, e_sub),
            "provider": (provider_box, e_provider),
            "paymentMethod": (pay_box, e_pay),
            "originPlatform": (origin_box, e_origin),
            "nature": (nature_box, e_nature),
        }

        def apply_category_fields() -> None:
            category = category_by_id.get(e_cat.value) or {}
            enabled = category.get("enabledFields") or {}
            for _key, (container, _widget) in field_boxes.items():
                container.set_visibility(bool(enabled.get(_key, True)))
            render_custom_fields()

        e_cat.on_value_change(lambda _e=None: apply_category_fields())
        apply_category_fields()

        preview = ui.html("").classes("muted")

        def show_preview() -> None:
            vat_percent = (
                DEFAULT_VAT_PERCENT
                if e_vat_rate.value is None
                else float(e_vat_rate.value)
            )
            view = vat.vat_preview(
                e_bs.value,
                e_mode.value or "incluido",
                e_rate.value,
                state.money,
                vat_percent / 100,
            )
            preview.content = (
                '<div class="row wrap" style="gap:8px">'
                + c.chip_html("Base " + view["vpBaseBs"])
                + c.chip_html("IVA " + view["vpIvaBs"])
                + c.chip_html("Total " + view["vpTotalBs"], "brand")
                + c.chip_html("≈ " + view["vpTotalUsd"])
                + c.chip_html(f"Tasa IVA {vat_percent:.2f}%")
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
        e_vat_rate.on_value_change(lambda _e=None: show_preview())
        show_preview()

        def save() -> None:
            name = (e_name.value or "").strip()
            if not name or not e_bs.value or float(e_bs.value) <= 0:
                ui.notify("Completa el producto y el monto.", type="warning")
                return
            vat_percent = (
                DEFAULT_VAT_PERCENT
                if e_vat_rate.value is None
                else float(e_vat_rate.value)
            )
            if not 0 <= vat_percent <= 100:
                ui.notify(
                    "La tasa de IVA debe estar entre 0 y 100 %.", type="warning"
                )
                return
            category = category_by_id.get(e_cat.value) or {}
            custom_fields = category.get("customFields") or []
            updated = domain_tx.apply_edit(
                tx,
                date=e_date.value or tx.get("date") or today,
                product_name=name,
                bs_amount=e_bs.value,
                usd_amount=e_usd.value,
                mode=e_mode.value or "incluido",
                rate_value=e_rate.value,
                iva_rate=vat_percent / 100,
                category_id=e_cat.value,
                quantity=e_qty.value,
                unit=e_unit.value,
                brand=e_brand.value,
                subcategory=e_sub.value,
                provider=e_provider.value,
                payment_method=e_pay.value or "",
                origin_platform=e_origin.value or "",
                nature=e_nature.value or "",
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
