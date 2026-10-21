"""Piezas de interfaz reutilizables.

Son envoltorios finos sobre los componentes de NiceGUI que reproducen las clases
del sistema de diseño de la versión de referencia (``card``, ``chip``, ``kpi``, ``bar`` y la
tabla ``data``). Mantener la construcción en un solo sitio evita que cada panel
repita el mismo HTML.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable, Iterator, Sequence

from nicegui import ui

from ..core.text import escape_html

__all__ = [
    "RawHtml",
    "bar_html",
    "card",
    "chip_html",
    "data_table",
    "empty_html",
    "kpi",
    "muted",
    "raw",
    "section_title",
]


class RawHtml(str):
    """Cadena que ya es HTML de la aplicación (no se vuelve a escapar).

    >>> RawHtml("<b>x</b>") == "<b>x</b>"
    True
    """


def raw(html_text: str) -> RawHtml:
    """Marca una cadena como HTML ya construido."""
    return RawHtml(html_text)


def chip_html(text: Any, kind: str = "") -> RawHtml:
    """``<span class="chip ok">texto</span>`` (el ``kind`` es ``ok``/``warn``/``bad``/``brand``).

    >>> chip_html("Estable", "ok")
    '<span class="chip ok">Estable</span>'
    >>> chip_html("<b>N</b>", "bad")
    '<span class="chip bad">&lt;b&gt;N&lt;/b&gt;</span>'
    """
    css = f"chip {kind}".strip()
    return RawHtml(f'<span class="{css}">{escape_html(text)}</span>')


def bar_html(pct: Any, color: str = "var(--accent)") -> RawHtml:
    """Barra de progreso; el ancho se limita a 0-100 %.

    >>> bar_html(48.4)
    '<div class="bar"><i style="width:48.4%; background:var(--accent)"></i></div>'
    """
    try:
        value = max(0.0, min(100.0, float(pct)))
    except (TypeError, ValueError):
        value = 0.0
    return RawHtml(
        f'<div class="bar"><i style="width:{value}%; background:{color}"></i></div>'
    )


def empty_html(text: str) -> RawHtml:
    """Bloque de «sin datos» con la misma pinta que la versión de referencia."""
    return RawHtml(f'<div class="empty">{escape_html(text)}</div>')


@contextmanager
def card(css: str = "") -> Iterator[ui.column]:
    """Tarjeta contenedora (``.card``)."""
    with ui.column().classes(f"card gap-2 w-full {css}".strip()) as column:
        yield column


def kpi(label: str, value: Any, sub: str = "") -> None:
    """Indicador con etiqueta, valor grande y nota opcional."""
    with ui.column().classes("kpi"):
        ui.html(f'<div class="kpi-lab">{escape_html(label)}</div>')
        ui.html(f'<div class="kpi-val">{escape_html(value)}</div>')
        if sub:
            ui.html(f'<div class="muted text-xs">{escape_html(sub)}</div>')


def muted(text: Any) -> None:
    ui.html(f'<div class="muted">{escape_html(text)}</div>')


def section_title(text: str, extra_html: str = "") -> None:
    """Título de sección con chips opcionales a la derecha."""
    with ui.row().classes("row between w-full items-center"):
        ui.html(f'<div style="font-weight:700">{escape_html(text)}</div>')
        if extra_html:
            ui.html(f'<div class="row wrap" style="gap:6px">{extra_html}</div>')


def data_table(
    headers: Sequence[str],
    rows: Iterable[Sequence[Any]],
    *,
    align_right: Sequence[int] = (),
) -> None:
    """Tabla simple con las cabeceras y las filas ya formateadas.

    Las celdas de texto se escapan; las que ya son HTML de la aplicación se
    marcan con :class:`RawHtml` (``chip_html``, ``bar_html`` y ``raw``).
    """
    right = set(align_right)

    def style(index: int) -> str:
        return ' style="text-align:right"' if index in right else ""

    def cell(value: Any) -> str:
        if isinstance(value, RawHtml):
            return str(value)
        return escape_html(value)

    head = "".join(f"<th{style(i)}>{escape_html(text)}</th>" for i, text in enumerate(headers))
    body = "".join(
        "<tr>"
        + "".join(f"<td{style(i)}>{cell(value)}</td>" for i, value in enumerate(row))
        + "</tr>"
        for row in rows
    )
    ui.html(f'<table class="data"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>')
