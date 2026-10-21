"""Panel 4 · Categorías: alta, edición y borrado.

Cada categoría guarda qué campos del formulario habilita (``enabledFields``) y sus
campos personalizados (``customFields``): nombre, tipo (texto, número, lista o
sí/no), obligatoriedad y opciones.
"""

from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

from ...core.constants import CAT_COLORS
from ...core.ids import now_ms, uid
from ...core.text import escape_html
from .. import components as c
from ..state import AppState

__all__ = ["render"]

#: Campos del formulario que una categoría puede habilitar.
FIELD_KEYS = (
    "quantity",
    "unit",
    "brand",
    "subcategory",
    "provider",
    "paymentMethod",
    "originPlatform",
    "nature",
    "tax",
)
FIELD_LABELS = {
    "quantity": "Cantidad",
    "unit": "Unidad",
    "brand": "Marca",
    "subcategory": "Subcategoría",
    "provider": "Comercio",
    "paymentMethod": "Forma de pago",
    "originPlatform": "Plataforma",
    "nature": "Naturaleza",
    "tax": "IVA",
}


def _build(state: AppState) -> None:
    with ui.column().classes("w-full gap-4 p-4"):
        with c.card():
            c.section_title(
                "Categorías",
                c.chip_html(f"{len(state.categories)} en {state.workspace}"),
            )
            body = ui.column().classes("w-full gap-1")

            def refresh_table() -> None:
                body.clear()
                with body:
                    if not state.categories:
                        ui.html(c.empty_html("No hay categorías en este entorno."))
                        return
                    for category in state.categories:
                        _row(state, category, refresh_table)

            refresh_table()

        with c.card():
            c.section_title("Nueva categoría")
            name = ui.input("Nombre").classes("w-full")
            with ui.row().classes("grid grid-cols-2 md:grid-cols-4 gap-3 w-full"):
                color = ui.input("Color", value=CAT_COLORS["alimentacion"]).props(
                    "type=color"
                )
                provider = ui.checkbox("Comercio", value=True)
                subcategory = ui.checkbox("Subcategoría", value=True)
                quantity = ui.checkbox("Cantidad", value=True)
                brand = ui.checkbox("Marca", value=True)
                unit = ui.checkbox("Unidad", value=True)

            new_custom_fields: list[dict[str, Any]] = []
            rerender_new = _custom_fields_editor(new_custom_fields)

            def create_category() -> None:
                label = (name.value or "").strip()
                if not label:
                    ui.notify("El nombre es obligatorio.", type="warning")
                    return
                stamp = now_ms()
                state.repo.put(
                    "categories",
                    {
                        "id": state.new_product_id().replace("PROD", "CAT"),
                        "workspace": state.workspace,
                        "name": label,
                        "color": color.value or CAT_COLORS["alimentacion"],
                        "enabledFields": {
                            **{key: True for key in FIELD_KEYS},
                            "quantity": bool(quantity.value),
                            "unit": bool(unit.value),
                            "brand": bool(brand.value),
                            "subcategory": bool(subcategory.value),
                            "provider": bool(provider.value),
                        },
                        "customFields": [
                            dict(field)
                            for field in new_custom_fields
                            if (field.get("label") or "").strip()
                        ],
                        "createdAt": stamp,
                        "updatedAt": stamp,
                    },
                )
                state.refresh()
                state.notify()
                name.value = ""
                new_custom_fields.clear()
                rerender_new()
                ui.notify("Categoría creada.", type="positive")

            ui.button("Crear categoría", on_click=create_category).props(
                "color=primary unelevated"
            )


def _row(state: AppState, category: dict[str, Any], refresh_table: Callable[[], None]) -> None:
    color = category.get("color") or "#2563EB"
    count = len(
        [tx for tx in state.transactions() if tx.get("categoryId") == category.get("id")]
    )
    with ui.row().classes("row between w-full items-center").style(
        "border-bottom:1px solid var(--line-soft); padding:6px 2px"
    ):
        with ui.row().classes("items-center gap-3"):
            ui.html(
                f'<span style="display:inline-block;width:12px;height:12px;'
                f'border-radius:4px;background:{color}"></span>'
            )
            ui.html(
                f'<div><div style="font-weight:600">{escape_html(category.get("name"))}</div>'
                f'<div class="muted text-xs">{count} movimientos · '
                f'{_fields_summary(category)}</div></div>'
            )
        with ui.row().classes("gap-2"):
            ui.button(
                "Editar", on_click=lambda cat=category: _edit_dialog(state, cat, refresh_table)
            ).props("flat dense")
            ui.button(
                "Borrar", on_click=lambda cat=category: _delete(state, cat, refresh_table)
            ).props("flat dense color=negative")


def _fields_summary(category: dict[str, Any]) -> str:
    enabled = category.get("enabledFields") or {}
    active = [FIELD_LABELS[key] for key in FIELD_KEYS if enabled.get(key)]
    custom = category.get("customFields") or []
    base = ", ".join(active) if active else "sin campos"
    return f"{base} · {len(custom)} personalizados"


def _custom_fields_editor(fields: list[dict[str, Any]]) -> Callable[[], None]:
    """Editor de ``customFields``; devuelve la función para repintarlo.

    La lista se modifica **en sitio**: el diálogo la lee al guardar. Los campos
    sin nombre se descartan al guardar, igual que la versión de referencia
    (``cfList.filter(cf => cf.label.trim())``).
    """
    box = ui.column().classes("w-full gap-2")

    def remove(index: int) -> None:
        fields.pop(index)
        rerender()

    def add() -> None:
        fields.append(
            {
                "id": uid("cf"),
                "label": "",
                "type": "text",
                "required": False,
                "options": [],
            }
        )
        rerender()

    def rerender() -> None:
        box.clear()
        with box:
            ui.html('<div class="sec-title">Campos personalizados</div>')
            if not fields:
                ui.html('<div class="muted">Sin campos personalizados.</div>')
            for index, field in enumerate(fields):
                with ui.row().classes("w-full items-end gap-2"):
                    label = ui.input(
                        "Nombre del campo", value=field.get("label") or ""
                    ).style("flex: 1 1 200px").mark(f"cf-label-{index}")
                    kind = ui.select(
                        {
                            "text": "Texto",
                            "number": "Número",
                            "select": "Lista",
                            "boolean": "Sí/No",
                        },
                        value=field.get("type") or "text",
                        label="Tipo",
                    ).style("width: 150px").mark(f"cf-type-{index}")
                    required = ui.checkbox(
                        "Obligatorio", value=bool(field.get("required"))
                    ).mark(f"cf-required-{index}")
                    options = ui.input(
                        "Opciones (solo Lista, separadas por coma)",
                        value=", ".join(field.get("options") or []),
                    ).style("flex: 1 1 180px").mark(f"cf-options-{index}")
                    ui.button(
                        icon="delete",
                        on_click=lambda _e=None, i=index: remove(i),
                    ).props("flat dense color=negative").mark(f"cf-del-{index}")

                    def update(
                        _e=None,
                        field=field,
                        label=label,
                        kind=kind,
                        required=required,
                        options=options,
                    ) -> None:
                        field["label"] = (label.value or "").strip()
                        field["type"] = kind.value or "text"
                        field["required"] = bool(required.value)
                        field["options"] = [
                            item.strip()
                            for item in (options.value or "").split(",")
                            if item.strip()
                        ]

                    for widget in (label, kind, required, options):
                        widget.on_value_change(update)

            ui.button("Añadir campo", on_click=lambda _e=None: add()).props(
                "outline"
            ).mark("cf-add")

    rerender()
    return rerender


def _edit_dialog(state: AppState, category: dict[str, Any], refresh_table: Callable[[], None]) -> None:
    enabled = category.get("enabledFields") or {}
    with ui.dialog() as dialog, c.card():
        c.section_title("Editar categoría")
        name = ui.input("Nombre", value=category.get("name") or "").classes("w-full")
        color = ui.input("Color", value=category.get("color") or "#2563EB").props("type=color")
        checks = {}
        with ui.row().classes("grid grid-cols-3 gap-2 w-full"):
            for key in FIELD_KEYS:
                checks[key] = ui.checkbox(
                    FIELD_LABELS[key], value=bool(enabled.get(key))
                )

        custom_fields = [dict(field) for field in category.get("customFields") or []]
        _custom_fields_editor(custom_fields)

        def apply() -> None:
            label = (name.value or "").strip()
            if not label:
                ui.notify("El nombre es obligatorio.", type="warning")
                return
            updated = dict(category)
            updated.update(
                {
                    "name": label,
                    "color": color.value or category.get("color") or "#2563EB",
                    "enabledFields": {
                        key: bool(checks[key].value) for key in FIELD_KEYS
                    },
                    "customFields": [
                        dict(field)
                        for field in custom_fields
                        if (field.get("label") or "").strip()
                    ],
                    "updatedAt": now_ms(),
                }
            )
            state.repo.put("categories", updated)
            state.refresh()
            state.notify()
            dialog.close()
            refresh_table()
            ui.notify("Categoría actualizada.", type="positive")

        with ui.row().classes("gap-2 mt-2"):
            ui.button("Guardar", on_click=apply).props(
                "color=primary unelevated"
            ).mark("cat-save")
            ui.button("Cancelar", on_click=dialog.close).props("flat")
    dialog.open()


def _delete(state: AppState, category: dict[str, Any], refresh_table: Callable[[], None]) -> None:
    count = len(
        [tx for tx in state.transactions() if tx.get("categoryId") == category.get("id")]
    )
    with ui.dialog() as dialog, c.card():
        c.section_title("Borrar categoría")
        ui.html(
            f'<div>¿Borrar <b>{escape_html(category.get("name"))}</b>? '
            f"{count} movimientos quedarán sin categoría.</div>"
        )

        def confirm() -> None:
            state.repo.delete("categories", category.get("id"))
            state.refresh()
            state.notify()
            dialog.close()
            refresh_table()
            ui.notify("Categoría borrada.", type="positive")

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
