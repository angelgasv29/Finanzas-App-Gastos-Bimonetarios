"""Interfaz gráfica (Fases 7-8) construida con NiceGUI.

La interfaz **no** calcula: lee el estado de :class:`app.ui.state.AppState`, llama
a las funciones de :mod:`app.domain`, :mod:`app.analytics` y :mod:`app.exports`
—ya verificadas contra la versión de referencia— y pinta el resultado.

Reparto:

- :mod:`app.ui.theme`   Variables CSS de la paleta institucional.
- :mod:`app.ui.state`   Estado de cada pestaña (repositorio, entorno, cachés, tasa).
- :mod:`app.ui.layout`  Cabecera, pestañas y contenedor de paneles.
- :mod:`app.ui.panels`  Un módulo por panel de la aplicación.
- :mod:`app.ui.app`     Ensamblado y arranque (``ui.run``).
"""

from __future__ import annotations

from .state import AppState

__all__ = ["AppState"]
