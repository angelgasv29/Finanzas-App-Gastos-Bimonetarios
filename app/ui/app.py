"""Punto de entrada de la interfaz NiceGUI.

``build()`` **registra la página**; el estado se crea dentro del constructor,
una vez por cliente. ``main()`` arranca el servidor. La lógica no vive aquí: los
paneles delegan en ``app.domain``, ``app.analytics`` y ``app.exports``.

La versión de referencia guardaba ``APP`` en una variable global de la página del navegador:
cada pestaña tenía el suyo (entorno, año, moneda, decimales, tasa de sesión) y
compartía los datos por IndexedDB. Aquí se replica igual: cada pestaña abre su
propio :class:`~app.ui.state.AppState` sobre el mismo fichero SQLite.
"""

from __future__ import annotations

from pathlib import Path

from nicegui import ui

from . import layout
from .state import open_state

__all__ = ["build", "main"]


def build(
    path: str | Path | None = None,
    *,
    workspace: str = "personal",
    title: str = "Gastos Bimonetarios",
    route: str = "/",
) -> None:
    """Registra la página en ``route`` (no monta nada hasta que entra un cliente)."""
    # Primera pasada al arrancar: crea el esquema y siembra antes de que ningún
    # cliente se conecte, para que dos pestañas simultáneas no siembren a la vez.
    open_state(path, workspace=workspace).close()

    def index() -> None:
        state = open_state(path, workspace=workspace)
        # Cerrar la conexión cuando la pestaña se va (no al desconectarse: NiceGUI
        # permite reconectar y el cierre llegaría con la página aún viva).
        ui.context.client.on_delete(state.close)
        ui.page_title(title)
        layout.apply_theme(state)
        layout.header(state)
        layout.panel_tabs(state)

    ui.page(route)(index)


def main(
    path: str | Path | None = None,
    *,
    workspace: str = "personal",
    host: str = "127.0.0.1",
    port: int = 8080,
    reload: bool = False,
) -> None:
    """Arranca el servidor de NiceGUI."""
    build(path, workspace=workspace)
    ui.run(host=host, port=port, reload=reload, title="Gastos Bimonetarios")


if __name__ in {"__main__", "__mp_main__"}:  # pragma: no cover
    main()
