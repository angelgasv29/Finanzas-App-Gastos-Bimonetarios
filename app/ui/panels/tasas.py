"""Panel 7 · Tasas: tasa del día, historial y sincronización con el BCV.

La versión de referencia consulta tres servicios públicos en cadena y se queda con el primero
que responde. Aquí se replica esa cadena con ``httpx``; si
todas fallan, se avisa y se puede introducir la tasa a mano.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Callable

import httpx
from nicegui import ui

from ...core.money import format_rate
from ...core.text import escape_html
from .. import components as c
from ..state import AppState

__all__ = ["render"]

#: (nombre, url, extractor) en el orden de la versión de referencia.
ENDPOINTS = (
    (
        "DolarAPI",
        "https://ve.dolarapi.com/v1/dolares/oficial",
        lambda data: data.get("promedio") or data.get("precio"),
    ),
    (
        "Pydolarve",
        "https://pydolarve.org/api/v1/dollar?page=bcv&monitor=bcv",
        lambda data: data.get("price")
        or (data.get("monitors") or {}).get("bcv", {}).get("price"),
    ),
    (
        "ExchangeDyn",
        "https://api.exchangedyn.com/markets/quotes/usdves/bcv",
        lambda data: (data.get("data") or {}).get("price"),
    ),
)


def fetch_bcv_rate(timeout: float = 8.0) -> tuple[float | None, str, str]:
    """Consulta la cadena de servicios. Devuelve ``(valor, fuente, error)``."""
    last_error = "Sin respuesta"
    for name, url, extract in ENDPOINTS:
        try:
            response = httpx.get(url, timeout=timeout)
            response.raise_for_status()
            value = extract(response.json())
            if value:
                return float(value), name, ""
        except Exception as exc:  # noqa: BLE001 - se prueba el siguiente servicio
            last_error = f"{name}: {exc}"
    return None, "", last_error


def _build(state: AppState) -> None:
    active = state.active_rate
    with ui.column().classes("w-full gap-4 p-4"):
        with c.card():
            c.section_title(
                "Tasa activa",
                (
                    c.chip_html(
                        f"{format_rate(state.rate_value)} Bs/USD · "
                        f"{active.get('date')} · {active.get('source')}",
                        "brand",
                    )
                    if active
                    else c.chip_html("Sin tasa", "bad")
                ),
            )
            if state.session_rate:
                ui.html(
                    c.chip_html("Tasa de sesión fijada a mano", "warn")
                )
                ui.button("Volver a la automática", on_click=_clear_session(state)).props("flat dense")

            with ui.row().classes("grid grid-cols-2 md:grid-cols-4 gap-3 w-full items-end"):
                manual_date = ui.input("Fecha", value=dt.date.today().isoformat()).props(
                    "type=date"
                ).classes("w-full")
                manual_value = ui.number("Tasa Bs/USD", value=None, min=0, format="%.4f").classes(
                    "w-full"
                )

                def save_manual() -> None:
                    if not manual_value.value or float(manual_value.value) <= 0:
                        ui.notify("Introduce una tasa válida.", type="warning")
                        return
                    state.repo.put(
                        "rates",
                        {
                            "date": manual_date.value,
                            "value": float(manual_value.value),
                            "source": "Manual",
                            "ts": int(dt.datetime.now().timestamp() * 1000),
                        },
                    )
                    # La versión de referencia fija la manual como tasa de la sesión
                    # (``lsSet(LS_KEYS.sessionRate, ...)``), aunque haya una del
                    # BCV con fecha más reciente.
                    state.lock_session_rate(
                        float(manual_value.value), manual_date.value
                    )
                    ui.notify(f"Tasa guardada para {manual_date.value}.", type="positive")

                ui.button("Guardar tasa", on_click=save_manual).props(
                    "color=primary unelevated"
                )

            async def sync() -> None:
                ui.notify("Consultando el BCV…")
                value, source, error = fetch_bcv_rate()
                if not value:
                    ui.notify(f"No se pudo obtener la tasa. {error}", type="negative")
                    return
                today = dt.date.today().isoformat()
                state.repo.put(
                    "rates",
                    {
                        "date": today,
                        "value": value,
                        "source": f"BCV·{source}",
                        "ts": int(dt.datetime.now().timestamp() * 1000),
                    },
                )
                # La versión de referencia suelta la tasa de sesión al sincronizar con el BCV
                # (``lsRemove(LS_KEYS.sessionRate)``).
                state.clear_session_rate()
                ui.notify(f"Tasa del día: {format_rate(value)} ({source}).", type="positive")

            ui.button("Sincronizar con el BCV", on_click=sync).props("outline")

        with c.card():
            c.section_title("Historial de tasas", c.chip_html(f"{len(state.rate_cache)} registros"))
            rates = state.rate_cache
            if not rates:
                ui.html(c.empty_html("No hay tasas registradas."))
            else:
                for rate in rates[:60]:
                    _rate_row(state, rate)

        with c.card():
            c.section_title("Referencia del cálculo")
            ui.html(
                '<div class="muted">La tasa activa es la que usan <code>fmtMoney</code>, '
                "la vista previa del IVA y el registro de compras. Si fijas una tasa de "
                "sesión, se mantiene aunque llegue una más reciente del BCV.</div>"
            )


def _clear_session(state: AppState) -> Callable[[], None]:
    def action() -> None:
        state.clear_session_rate()
        ui.notify("Tasa automática restaurada.")

    return action


def _rate_row(state: AppState, rate: dict[str, Any]) -> None:
    with ui.row().classes("row between w-full items-center").style(
        "border-bottom:1px solid var(--line-soft); padding:5px 2px"
    ):
        ui.html(
            f'<div><b>{escape_html(rate.get("date"))}</b> · '
            f'<span class="muted">{escape_html(rate.get("source") or "—")}</span></div>'
        )
        with ui.row().classes("items-center gap-3"):
            ui.html(f'<span>{format_rate(rate.get("value"))} Bs/USD</span>')

            def delete() -> None:
                state.repo.delete("rates", rate.get("date"))
                state.refresh()
                state.notify()
                ui.notify("Tasa borrada.", type="positive")

            ui.button("Borrar", on_click=delete).props("flat dense color=negative")


def render(state: AppState) -> None:
    @ui.refreshable
    def content() -> None:
        _build(state)

    content()
    state.subscribe(content.refresh)
