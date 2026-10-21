"""Constantes de dominio.

Implementación de la sección 1 del JavaScript de referencia (líneas 2648-2700 de
la referencia).

Se conservan los nombres de referencia en ``UPPER_SNAKE_CASE`` para poder
rastrear cada valor hasta su origen.
"""

from __future__ import annotations

from typing import Any, Final

# ---------------------------------------------------------------------------
# Base de datos (origen: IndexedDB, líneas 2651-2656)
# ---------------------------------------------------------------------------

DB_NAME: Final[str] = "GastosBimonetariosDB"
DB_VERSION: Final[int] = 1

STORES: Final[dict[str, str]] = {
    "transactions": "transactions",
    "products": "products",
    "categories": "categories",
    "rates": "rates",
    "closures": "closures",
}

# Claves de configuración (origen: localStorage, líneas 2657-2662)
LS_KEYS: Final[dict[str, str]] = {
    "theme": "gb_theme",
    "workspace": "gb_workspace",
    "fiscal_year": "gb_fiscal_year",
    "session_rate": "gb_session_rate",
    "decimals": "gb_decimals",
    "default_workspace": "gb_default_workspace",
    "currency": "gb_currency_view",
    "default_currency": "gb_default_currency",
}

# ---------------------------------------------------------------------------
# Impuestos
# ---------------------------------------------------------------------------

IVA_RATE: Final[float] = 0.16

# Modos de IVA del formulario de registro (líneas 1619-1626 del HTML)
VAT_MODES: Final[tuple[str, str, str]] = ("exento", "incluido", "mas_iva")

# ---------------------------------------------------------------------------
# Catálogos de dominio
# ---------------------------------------------------------------------------

# "Catálogo canónico de plataformas de fondeo (M1). Representa el ORIGEN del
# dinero, independiente del método de pago."
PAYMENT_ORIGINS: Final[tuple[str, ...]] = (
    "Binance P2P",
    "Zinli",
    "Bancamiga",
    "Banesco",
    "Mercantil",
    "BDV",
    "Efectivo USD",
    "Efectivo VES",
    "Wally",
    "PayPal",
    "Zelle",
    "Otro",
)

# Etiqueta de retrocompatibilidad para transacciones anteriores a Fase C.
ORIGIN_UNKNOWN: Final[str] = "— No especificado"

# Colores por categoría por defecto
CAT_COLORS: Final[dict[str, str]] = {
    "alimentacion": "#2563EB",
    "salud": "#10B981",
    "servicios": "#D97706",
    "transporte": "#8B5CF6",
    "insumos": "#0EA5E9",
    "operaciones": "#F59E0B",
    "honorarios": "#8B5CF6",
}

# Paleta institucional. Necesaria para la interfaz.
PALETTE: Final[dict[str, dict[str, str]]] = {
    "dark": {
        "bg_0": "#090A0D",
        "bg_1": "#111318",
        "bg_2": "#161920",
        "bg_3": "#1C2029",
        "line": "#222631",
        "line_soft": "#1A1D26",
        "txt_0": "#F3F4F6",
        "txt_1": "#9CA3AF",
        "txt_2": "#6B7280",
    },
    "light": {
        "bg_0": "#F8FAFC",
        "bg_1": "#FFFFFF",
        "bg_2": "#F1F5F9",
        "bg_3": "#E8EDF3",
        "line": "#E2E8F0",
        "line_soft": "#EDF1F5",
        "txt_0": "#0F172A",
        "txt_1": "#475569",
        "txt_2": "#94A3B8",
    },
    "accent": {
        "accent": "#2563EB",
        "ok": "#10B981",
        "gold": "#D97706",
        "bad": "#EF4444",
    },
}

# ---------------------------------------------------------------------------
# Campos del formulario dinámico
# ---------------------------------------------------------------------------

UNIT_OPTIONS: Final[tuple[str, ...]] = (
    "unidad",
    "g",
    "kg",
    "mg",
    "ml",
    "L",
    "empaque",
    "caja",
    "docena",
    "par",
    "metro",
    "m2",
    "m3",
    "otro",
)

PAYMENT_METHODS: Final[tuple[str, ...]] = (
    "Efectivo Bs",
    "Efectivo USD",
    "Pago Movil",
    "Punto de Venta/Debito",
    "Transferencia Bancaria",
    "Zelle",
    "Billetera Digital/Cripto",
    "Otro",
)

NATURE_OPTIONS: Final[tuple[str, ...]] = ("Recurrente", "Extraordinario")

PREDEF_FIELDS: Final[list[dict[str, Any]]] = [
    {
        "key": "productName",
        "label": "Nombre del Producto / Servicio",
        "type": "text",
        "requiredAlways": True,
    },
    {"key": "quantity", "label": "Cantidad", "type": "number"},
    {
        "key": "unit",
        "label": "Peso / Unidad de Medida",
        "type": "select",
        "options": UNIT_OPTIONS,
    },
    {"key": "brand", "label": "Marca", "type": "text"},
    {"key": "subcategory", "label": "Subcategoría", "type": "text"},
    {"key": "provider", "label": "Abastecimiento / Comercio", "type": "text"},
    {
        "key": "paymentMethod",
        "label": "Método de Pago",
        "type": "select",
        "options": PAYMENT_METHODS,
    },
    {
        "key": "originPlatform",
        "label": "Plataforma Origen (fondeo)",
        "type": "select",
        "options": PAYMENT_ORIGINS,
    },
    {
        "key": "nature",
        "label": "Naturaleza del Gasto",
        "type": "select",
        "options": NATURE_OPTIONS,
    },
    {"key": "tax", "label": "IVA (16%)", "type": "computed"},
]

# Tipos de período del panel de análisis
TEMPORAL_MODES: Final[tuple[str, ...]] = (
    "week",
    "month",
    "bimester",
    "quarter",
    "quadrimester",
    "semester",
    "year",
    "custom",
)

TEMPORAL_MODE_NAMES: Final[dict[str, str]] = {
    "week": "Semana",
    "month": "Mes",
    "bimester": "Bimestre",
    "quarter": "Trimestre",
    "quadrimester": "Cuatrimestre",
    "semester": "Semestre",
    "year": "Año",
    "custom": "Personalizado",
}

# Modos de vista de la lista de movimientos
TX_VIEW_MODES: Final[tuple[str, ...]] = ("list", "acc", "top10", "top20", "freq")

# Tipos de pivote
PIVOT_TYPES: Final[tuple[str, ...]] = (
    "provider",
    "brand",
    "payment",
    "originPlatform",
    "subcategory",
)


def get_origin_label(tx: dict[str, Any] | None) -> str:
    """Etiqueta de presentación de la plataforma origen. Nunca devuelve vacío.

    Implementación exacto de ``getOriginLabel``.
    """
    if not tx:
        return ORIGIN_UNKNOWN
    value = str(tx.get("originPlatform") or "").strip()
    return value if value else ORIGIN_UNKNOWN
