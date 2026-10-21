"""Paneles de la interfaz: un módulo por pantalla de la versión de referencia."""

from __future__ import annotations

from . import (
    analisis,
    catalogo,
    categorias,
    configuracion,
    dashboard,
    ocr,
    registrar,
    reportes,
    tasas,
)

#: (clave, etiqueta, módulo) en el orden de las pestañas de la versión de referencia.
PANELS = (
    ("dashboard", "Dashboard", dashboard),
    ("registrar", "Registrar", registrar),
    ("catalogo", "Catálogo", catalogo),
    ("categorias", "Categorías", categorias),
    ("analisis", "Análisis", analisis),
    ("reportes", "Reportes", reportes),
    ("tasas", "Tasas", tasas),
    ("ocr", "OCR", ocr),
    ("configuracion", "Configuración", configuracion),
)

__all__ = ["PANELS"]
