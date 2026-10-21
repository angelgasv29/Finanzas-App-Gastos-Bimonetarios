"""Tema visual: la paleta institucional de la versión de referencia como variables CSS.

La versión de referencia define su sistema de diseño con variables CSS
(``--bg-0``, ``--line``, ``--txt-1``…) que cambian según el tema claro/oscuro
(``:root[data-theme="light"]``). No se reutiliza su hoja de estilo (decisión
«Nivel 2»), pero sí la **paleta** —que está en ``app/core/constants.py``— para
que los colores coincidan.

NiceGUI ya trae Quasar; aquí solo se añaden las variables y unas pocas clases de
apoyo (``card``, ``chip``, ``kpi``…) con los mismos nombres que usa la versión de referencia,
de modo que las vistas portadas se lean igual.
"""

from __future__ import annotations

from ..core.constants import PALETTE

__all__ = ["theme_css", "accent_color"]

#: Colores de acento (no dependen del tema claro/oscuro).
ACCENT = PALETTE["accent"]


def accent_color(name: str, default: str = "#2563EB") -> str:
    """Color de la paleta de acento por nombre (``ok``, ``bad``, ``gold``…).

    >>> accent_color("ok")
    '#10B981'
    >>> accent_color("noexiste", "#000")
    '#000'
    """
    return ACCENT.get(name, default)


def theme_css(theme: str = "dark") -> str:
    """Hoja de estilo con las variables del tema pedido.

    >>> ":root" in theme_css() and "--bg-0:" in theme_css()
    True
    >>> theme_css("light").count("--bg-0:")
    1
    """
    if theme not in PALETTE:
        theme = "dark"
    palette = {**PALETTE[theme], **ACCENT}
    variables = "\n".join(
        f"      --{key.replace('_', '-')}: {value};" for key, value in palette.items()
    )
    dark = theme == "dark"
    return f"""
    :root {{
{variables}
      --radius: 14px;
      --radius-sm: 9px;
      --shadow: 0 1px 2px rgba(0, 0, 0, .28), 0 8px 24px rgba(0, 0, 0, .18);
    }}

    body {{
      background: var(--bg-0);
      color: var(--txt-0);
      font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
      font-size: 14px;
    }}

    .q-page, .q-layout, .q-drawer, .q-header {{
      background: var(--bg-0) !important;
      color: var(--txt-0) !important;
    }}

    .app-header {{
      background: var(--bg-1);
      border-bottom: 1px solid var(--line);
      padding: 10px 18px;
      display: flex;
      align-items: center;
      gap: 14px;
      flex-wrap: wrap;
    }}

    .app-title {{ font-weight: 700; font-size: 15px; letter-spacing: .2px; }}
    .muted {{ color: var(--txt-1); }}
    .dim {{ color: var(--txt-2); }}

    .card {{
      background: var(--bg-1);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 16px;
      box-shadow: var(--shadow);
    }}

    .card.tight {{ padding: 12px; }}

    .kpi {{ display: flex; flex-direction: column; gap: 4px; }}
    .kpi-val {{ font-size: 22px; font-weight: 700; letter-spacing: -.4px; }}
    .kpi-lab {{ font-size: 11.5px; text-transform: uppercase; letter-spacing: .6px; color: var(--txt-1); }}

    .chip {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 2px 9px;
      border-radius: 999px;
      font-size: 11.5px;
      font-weight: 600;
      border: 1px solid var(--line);
      background: var(--bg-2);
      color: var(--txt-0);
      white-space: nowrap;
    }}
    .chip.ok {{ color: var(--ok); border-color: color-mix(in srgb, var(--ok) 45%, var(--line)); }}
    .chip.warn {{ color: var(--gold); border-color: color-mix(in srgb, var(--gold) 45%, var(--line)); }}
    .chip.bad {{ color: var(--bad); border-color: color-mix(in srgb, var(--bad) 45%, var(--line)); }}
    .chip.brand {{ color: var(--accent); border-color: color-mix(in srgb, var(--accent) 45%, var(--line)); }}

    .row {{ display: flex; align-items: center; gap: 10px; }}
    .row.between {{ justify-content: space-between; }}
    .wrap {{ flex-wrap: wrap; }}
    .grid {{ display: grid; gap: 14px; }}

    .bar {{ height: 8px; border-radius: 999px; background: var(--bg-3); overflow: hidden; }}
    .bar > i {{ display: block; height: 100%; border-radius: 999px; background: var(--accent); }}

    table.data {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
    table.data th {{ text-align: left; color: var(--txt-1); font-weight: 600; padding: 8px 10px; border-bottom: 1px solid var(--line); }}
    table.data td {{ padding: 8px 10px; border-bottom: 1px solid var(--line-soft); }}
    table.data tr:hover td {{ background: var(--bg-2); }}

    .empty {{ text-align: center; padding: 34px; color: var(--txt-1); font-style: italic; }}

    .nicegui-content {{ padding: 0; }}
    .q-tab {{ text-transform: none !important; font-weight: 600; }}
    """


#: Modo oscuro por defecto de la versión de referencia (``DEFAULT_THEME``).
DEFAULT_THEME = "dark"
