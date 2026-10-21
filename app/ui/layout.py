"""Armazón de la interfaz: tema, cabecera y pestañas.

La cabecera reproduce los controles globales de la versión de referencia (entorno, año fiscal,
moneda, decimales, tema y tasa activa). Los paneles se montan dentro de
``ui.tab_panels``; cada uno se repinta solo cuando el estado avisa.
"""

from __future__ import annotations

import logging

from nicegui import ui

from ..core.money import format_rate
from . import components as c
from .components import card, empty_html, section_title
from .panels import PANELS
from .state import AppState
from .theme import theme_css

__all__ = ["apply_theme", "header", "panel_tabs"]

WORKSPACE_LABELS = {"personal": "Personal", "profesional": "Profesional"}
CURRENCY_LABELS = {"USD": "USD", "VES": "Bs"}


def apply_theme(state: AppState) -> None:
    """Inyecta las variables CSS del tema activo."""
    ui.add_head_html(f"<style>\n{theme_css(state.theme)}\n</style>")


def _rate_chip(state: AppState) -> str:
    active = state.active_rate
    if not active:
        return c.chip_html("Sin tasa registrada", "bad")
    label = f"{format_rate(state.rate_value)} Bs/USD · {active.get('date')}"
    kind = "warn" if state.session_rate else "brand"
    return c.chip_html(label, kind)


def header(state: AppState) -> None:
    """Barra superior con los ajustes globales."""
    with ui.row().classes("app-header row between w-full items-center").style(
        "padding:10px 24px 10px 16px; box-sizing:border-box; "
        "border-bottom:1px solid var(--line); "
        "background:var(--bg-1); position:sticky; top:0; z-index:10"
    ):
        with ui.row().classes("items-center gap-3"):
            ui.html('<div style="font-weight:800; font-size:18px">Gastos Bimonetarios</div>')

            @ui.refreshable
            def rate_chip() -> None:
                ui.html(_rate_chip(state))

            rate_chip()
            state.subscribe(rate_chip.refresh)

        with ui.row().classes("items-center gap-3 wrap"):
            workspace = ui.select(
                WORKSPACE_LABELS, value=state.workspace, label=None
            ).props("dense outlined options-dense").style("min-width:130px")
            year = ui.number(
                value=state.fiscal_year, min=2000, max=2100, step=1, label=None
            ).props("dense outlined").style("width:96px")
            currency = ui.select(
                CURRENCY_LABELS, value=state.currency, label=None
            ).props("dense outlined options-dense").style("min-width:96px")
            decimals = ui.number(
                value=state.decimals, min=0, max=6, step=1, label=None
            ).props("dense outlined").style("width:78px")
            theme = ui.select(
                {"dark": "Oscuro", "light": "Claro"}, value=state.theme, label=None
            ).props("dense outlined options-dense").style("min-width:104px")

            def change_workspace() -> None:
                if workspace.value and workspace.value != state.workspace:
                    state.set_workspace(workspace.value)

            def change_year() -> None:
                if year.value is not None:
                    state.set_fiscal_year(int(year.value))

            def change_currency() -> None:
                if currency.value:
                    state.set_currency(currency.value)

            def change_decimals() -> None:
                if decimals.value is not None:
                    state.set_decimals(int(decimals.value))

            def change_theme() -> None:
                if theme.value and theme.value != state.theme:
                    state.set_theme(theme.value)
                    ui.run_javascript("window.location.reload()")

            workspace.on_value_change(lambda _e=None: change_workspace())
            year.on_value_change(lambda _e=None: change_year())
            currency.on_value_change(lambda _e=None: change_currency())
            decimals.on_value_change(lambda _e=None: change_decimals())
            theme.on_value_change(lambda _e=None: change_theme())


def panel_tabs(state: AppState) -> None:
    """Pestañas principales con los nueve paneles."""
    with ui.tabs().classes("w-full").style(
        "background:var(--bg-1); border-bottom:1px solid var(--line)"
    ) as tabs:
        for key, label, _module in PANELS:
            ui.tab(key, label=label)

    with ui.tab_panels(tabs, value=PANELS[0][0]).classes("w-full"):
        for key, label, module in PANELS:
            with ui.tab_panel(key).classes("p-0"):
                try:
                    module.render(state)
                except Exception as exc:  # noqa: BLE001 - un panel no debe tumbar la app
                    logging.exception("Fallo al montar el panel %s", key)
                    with card():
                        section_title(f"No se pudo montar «{label}»")
                        ui.html(
                            empty_html(f"{type(exc).__name__}: {exc}")
                        )
