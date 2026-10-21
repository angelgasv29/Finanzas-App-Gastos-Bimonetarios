"""Panel 9 · Configuración: preferencias, datos demo y mantenimiento.

Reúne los controles que en la versión de referencia viven en la cabecera (tema, moneda,
decimales, año fiscal y entorno), la carga del conjunto de demostración
(ajuste de ``loadDemoDataset``) y las utilidades de almacenamiento.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nicegui import ui

from ...core.constants import STORES
from ...core.ids import new_sku
from ...data.seed import seed_categories_if_empty
from ...domain import demo as domain_demo
from .. import components as c
from ..state import WORKSPACES, AppState

__all__ = ["render"]

THEME_LABELS = {"dark": "Oscuro", "light": "Claro"}
CURRENCY_LABELS = {"USD": "Dólares (USD)", "VES": "Bolívares (VES)"}
WORKSPACE_LABELS = {"personal": "Personal", "profesional": "Profesional"}


def _build(state: AppState) -> None:
    with ui.column().classes("w-full gap-4 p-4"):
        with c.card():
            c.section_title("Preferencias")
            with ui.row().classes("grid grid-cols-2 md:grid-cols-5 gap-3 w-full items-end"):
                workspace = ui.select(
                    WORKSPACE_LABELS, value=state.workspace, label="Entorno"
                ).classes("w-full")
                currency = ui.select(
                    CURRENCY_LABELS, value=state.currency, label="Moneda"
                ).classes("w-full")
                decimals = ui.number(
                    "Decimales", value=state.decimals, min=0, max=6, step=1
                ).classes("w-full")
                year = ui.number(
                    "Año fiscal", value=state.fiscal_year, min=2000, max=2100, step=1
                ).classes("w-full")
                theme = ui.select(
                    THEME_LABELS, value=state.theme, label="Tema"
                ).classes("w-full")

            def apply_workspace() -> None:
                if workspace.value and workspace.value != state.workspace:
                    state.set_workspace(workspace.value)

            def apply_currency() -> None:
                if currency.value:
                    state.set_currency(currency.value)

            def apply_decimals() -> None:
                if decimals.value is not None:
                    state.set_decimals(int(decimals.value))

            def apply_year() -> None:
                if year.value is not None:
                    state.set_fiscal_year(int(year.value))

            def apply_theme() -> None:
                if theme.value and theme.value != state.theme:
                    state.set_theme(theme.value)
                    ui.run_javascript("window.location.reload()")

            workspace.on_value_change(lambda _e=None: apply_workspace())
            currency.on_value_change(lambda _e=None: apply_currency())
            decimals.on_value_change(lambda _e=None: apply_decimals())
            year.on_value_change(lambda _e=None: apply_year())
            theme.on_value_change(lambda _e=None: apply_theme())

        with c.card():
            c.section_title(
                "Datos de demostración",
                c.chip_html(f"{len(domain_demo.DEMO_SAMPLE)} compras de ejemplo"),
            )
            ui.html(
                '<div class="muted">Carga un ejercicio completo de ejemplo '
                "(9 tasas, 8 SKU y 23 compras) en el entorno activo. "
                "No borra los datos que ya existan.</div>"
            )

            def load_demo() -> None:
                if not state.categories:
                    ui.notify(
                        "El entorno no tiene categorías: crea alguna antes de cargar la demo.",
                        type="warning",
                    )
                    return
                data = domain_demo.build_demo_dataset(
                    workspace=state.workspace,
                    categories=state.categories,
                    products=state.products,
                    now=state.audit_now(),
                    app_rate_value=state.rate_value,
                    sku_factory=lambda: new_sku(state.workspace),
                )
                if not data["count"]:
                    ui.notify("No se pudo generar la demo.", type="warning")
                    return
                for rate in data["rates"]:
                    state.repo.put("rates", rate)
                for product in data["products"]:
                    state.repo.put("products", product)
                for record in data["transactions"]:
                    state.repo.add("transactions", record)
                state.refresh()
                state.notify()
                ui.notify(
                    f"Demo cargada: {data['count']} compras y "
                    f"{len(data['products'])} SKU.",
                    type="positive",
                )

            ui.button("Cargar demo", on_click=load_demo).props("color=primary unelevated")

        with c.card():
            c.section_title("Almacenamiento")
            stats = state.storage_stats()
            c.data_table(
                ["Tabla", "Registros"],
                [(name, str(stats.get(name, 0))) for name in STORES],
                align_right=(1,),
            )
            muted = ui.html("").classes("muted text-xs")
            db_path = getattr(state.db, "path", None)
            size = ""
            if db_path:
                try:
                    size = f" · {Path(db_path).stat().st_size / 1024:.0f} KB"
                except OSError:
                    size = ""
            muted.content = (
                f'Base de datos: <span class="mono">{db_path}</span>{size}'
                if db_path
                else "Base de datos en memoria"
            )

            def wipe_confirm() -> None:
                with ui.dialog() as dialog, c.card():
                    c.section_title("Borrar todos los datos")
                    ui.html(
                        "<div>Se vaciarán <b>todas</b> las tablas del entorno y de "
                        "los demás entornos. Esta acción no se puede deshacer.</div>"
                    )

                    def confirm() -> None:
                        for store in STORES:
                            state.repo.clear(store)
                        state.clear_session_rate()
                        # La versión de referencia vuelve a sembrar las categorías cuando se
                        # borran («Re-seed solo si el usuario pidió borrar
                        # categorías»), para no dejar la app sin categorías.
                        seed_categories_if_empty(state.repo)
                        state.refresh()
                        state.notify()
                        dialog.close()
                        ui.notify("Datos borrados.", type="positive")

                    with ui.row().classes("gap-2 mt-2"):
                        ui.button("Borrar todo", on_click=confirm).props(
                            "color=negative unelevated"
                        )
                        ui.button("Cancelar", on_click=dialog.close).props("flat")
                dialog.open()

            ui.button("Borrar todos los datos…", on_click=wipe_confirm).props(
                "outline color=negative"
            )


def render(state: AppState) -> None:
    @ui.refreshable
    def content() -> None:
        _build(state)

    content()
    state.subscribe(content.refresh)
