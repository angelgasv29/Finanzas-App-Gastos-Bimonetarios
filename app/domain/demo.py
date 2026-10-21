"""Dataset de demostración (``loadDemoDataset``) y su arreglo posterior.

La versión de referencia genera ~23 compras «realistas» repartidas por el año más sus nueve
tasas de referencia, y después la sección CAPA DE COMPATIBILIDAD las retoca (línea
7980): rellena la plataforma de origen y **corrige el café de 1000 g**, cuyo
precio por gramo dejaba el total por debajo de un dólar.

Aquí se portan las dos mitades por separado:

* :func:`build_demo_dataset` — genera las tasas, los SKU que falten y las
  compras (la parte de ``loadDemoDataset`` de referencia).
* :func:`fix_demo_dataset` — aplica los retoques del ajuste en orden de
  inserción.

La confirmación previa (``confirm(...)``) y los avisos son de la interfaz.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Callable

from ..core.money import js_number_or_zero, js_round

__all__ = [
    "DEMO_ORIGINS",
    "DEMO_RATE_TABLE",
    "build_demo_dataset",
    "fix_demo_dataset",
]

#: Tasas de referencia por día (mes-día) que usa el demo.
DEMO_RATE_TABLE = (
    ("01-10", 36.05),
    ("02-15", 36.35),
    ("03-15", 36.80),
    ("04-20", 37.40),
    ("05-18", 38.20),
    ("06-22", 39.50),
    ("07-25", 41.10),
    ("08-19", 42.80),
    ("09-20", 44.60),
)

#: Plataformas que el ajuste reparte, en orden, entre las compras demo.
DEMO_ORIGINS = (
    "Banesco",
    "Pago Movil",
    "Efectivo USD",
    "Bancamiga",
    "Binance P2P",
    "Zelle",
    "Mercantil",
    "Zinli",
    "BDV",
)

#: Tasa de último recurso cuando la fecha no está en la tabla y no hay tasa activa.
FALLBACK_RATE = 36.5

#: Factor de IVA incluido de la versión de referencia (constante del motor de IVA).
IVA_FACTOR = 1.16

#: ``cat`` = ranura de categoría: 0 → alimentación, 1 → salud, 2 → servicios.
#: (fecha, ranura, nombre, marca, unidad, subcategoría, comercio, cantidad,
#:  USD/unidad, forma de pago, modalidad de IVA, naturaleza)
DEMO_SAMPLE = (
    ("01-10", 0, "Harina de Maíz Precocida 1kg", "PAN", "kg", "Despensa", "Excelsior Gama", 4, 1.05, "Pago Movil", "exento", "Recurrente"),
    ("03-15", 0, "Harina de Maíz Precocida 1kg", "PAN", "kg", "Despensa", "Excelsior Gama", 4, 1.12, "Punto de Venta/Debito", "exento", "Recurrente"),
    ("03-15", 0, "Harina de Maíz Precocida 1kg", "PAN", "kg", "Despensa", "Automercado Forum", 4, 0.99, "Efectivo USD", "exento", "Recurrente"),
    ("06-22", 0, "Harina de Maíz Precocida 1kg", "PAN", "kg", "Despensa", "Automercado Forum", 5, 1.18, "Pago Movil", "exento", "Recurrente"),
    ("09-20", 0, "Harina de Maíz Precocida 1kg", "PAN", "kg", "Despensa", "Excelsior Gama", 4, 1.26, "Pago Movil", "exento", "Recurrente"),
    ("01-10", 0, "Café Molido Gourmet 500g", "Fama de América", "g", "Bebidas", "Excelsior Gama", 500, 0.0096, "Punto de Venta/Debito", "incluido", "Recurrente"),
    ("04-20", 0, "Café Molido Gourmet 500g", "Fama de América", "g", "Bebidas", "Automercado Forum", 500, 0.0105, "Efectivo USD", "incluido", "Recurrente"),
    ("07-25", 0, "Café Molido Gourmet 500g", "Madrid", "g", "Bebidas", "Automercado Plaza", 500, 0.0112, "Zelle", "incluido", "Recurrente"),
    ("09-20", 0, "Café Molido Gourmet 500g", "Fama de América", "g", "Bebidas", "Excelsior Gama", 1000, 0.0061, "Pago Movil", "incluido", "Recurrente"),
    ("02-15", 1, "Vitamina C + Zinc 30 tab", "Calox", "unidad", "Suplementos", "Farmatodo", 1, 6.50, "Pago Movil", "incluido", "Extraordinario"),
    ("08-19", 1, "Vitamina C + Zinc 30 tab", "Calox", "unidad", "Suplementos", "Farmatodo", 1, 7.40, "Billetera Digital/Cripto", "incluido", "Extraordinario"),
    ("01-10", 2, "Internet Fibra 400 Mbps", "NetUno", "unidad", "Internet", "Portal Web", 1, 30.00, "Zelle", "incluido", "Recurrente"),
    ("05-18", 2, "Internet Fibra 400 Mbps", "NetUno", "unidad", "Internet", "Portal Web", 1, 32.50, "Billetera Digital/Cripto", "incluido", "Recurrente"),
    ("09-20", 2, "Internet Fibra 400 Mbps", "NetUno", "unidad", "Internet", "Portal Web", 1, 35.00, "Pago Movil", "incluido", "Recurrente"),
    ("02-15", 0, "Leche en Polvo 900g", "Nestlé", "g", "Lácteos", "Excelsior Gama", 900, 0.0091, "Pago Movil", "exento", "Recurrente"),
    ("05-18", 0, "Leche en Polvo 900g", "Nestlé", "g", "Lácteos", "Automercado Forum", 900, 0.0101, "Efectivo USD", "exento", "Recurrente"),
    ("08-19", 0, "Leche en Polvo 900g", "Nestlé", "g", "Lácteos", "Automercado Forum", 900, 0.0109, "Pago Movil", "exento", "Recurrente"),
    ("03-15", 1, "Jabón de Baño x3", "Dove", "empaque", "Cuidado Personal", "Farmatodo", 1, 4.20, "Punto de Venta/Debito", "incluido", "Recurrente"),
    ("06-22", 1, "Jabón de Baño x3", "Dove", "empaque", "Cuidado Personal", "Farmatodo", 1, 4.80, "Pago Movil", "incluido", "Recurrente"),
    ("04-20", 2, "Plan Móvil 20GB", "Digitel", "unidad", "Telefonía", "Portal Web", 1, 8.50, "Pago Movil", "incluido", "Recurrente"),
    ("07-25", 2, "Plan Móvil 20GB", "Digitel", "unidad", "Telefonía", "Portal Web", 1, 9.20, "Pago Movil", "incluido", "Recurrente"),
    ("01-10", 0, "Arroz Blanco 1kg", "Mary", "kg", "Despensa", "Excelsior Gama", 3, 1.10, "Pago Movil", "exento", "Recurrente"),
    ("06-22", 0, "Arroz Blanco 1kg", "Mary", "kg", "Despensa", "Excelsior Gama", 3, 1.35, "Pago Movil", "exento", "Recurrente"),
)


def _local_year(now: dt.datetime) -> int:
    """Año local del reloj (la versión de referencia usa ``new Date().getFullYear()``).

    >>> _local_year(dt.datetime(2026, 3, 15, 12))
    2026
    """
    return now.year


def _now_ms(now: dt.datetime) -> int:
    """``Date.now()`` a partir del reloj local (naïve).

    >>> _now_ms(dt.datetime(2026, 3, 15, 12, 30, 45))
    1773592245000
    """
    return int(now.timestamp() * 1000)


def build_demo_dataset(
    *,
    workspace: str,
    categories: list[dict[str, Any]],
    products: list[dict[str, Any]],
    now: dt.datetime,
    app_rate_value: Any = None,
    sku_factory: Callable[[], str],
) -> dict[str, Any]:
    """Genera el dataset demo: tasas, SKU nuevos y compras.

    Devuelve los tres grupos **en el orden en que la versión de referencia los escribe**.
    ``products`` sólo incluye los SKU creados (los que ya estaban en el catálogo
    se reutilizan por nombre). Si no hay categorías devuelve todo vacío: el
    de referencia avisa y no carga nada.

    >>> import datetime as dt
    >>> cats = [{"id": "c1"}, {"id": "c2"}, {"id": "c3"}]
    >>> ids = iter(["PROD-P-AAAA", "PROD-P-BBBB", "PROD-P-CCCC", "PROD-P-DDDD",
    ...             "PROD-P-EEEE", "PROD-P-FFFF", "PROD-P-GGGG", "PROD-P-HHHH"])
    >>> data = build_demo_dataset(
    ...     workspace="personal", categories=cats, products=[],
    ...     now=dt.datetime(2026, 3, 15, 12, 0),
    ...     sku_factory=lambda: next(ids),
    ... )
    >>> len(data["rates"]), len(data["transactions"])
    (9, 23)
    >>> data["transactions"][0]["date"], data["transactions"][0]["rate"]
    ('2026-01-10', 36.05)
    >>> data["transactions"][0]["amountUsd"], data["transactions"][0]["amountBs"]
    (4.2, 151.41)
    >>> sorted({p["name"] for p in data["products"]})
    ['Arroz Blanco 1kg', 'Café Molido Gourmet 500g', 'Harina de Maíz Precocida 1kg', 'Internet Fibra 400 Mbps', 'Jabón de Baño x3', 'Leche en Polvo 900g', 'Plan Móvil 20GB', 'Vitamina C + Zinc 30 tab']
    """
    if not categories:
        return {"rates": [], "products": [], "transactions": [], "count": 0}

    cat_by_slot = [
        categories[0],
        categories[1] if len(categories) > 1 else categories[0],
        categories[2] if len(categories) > 2 else categories[0],
    ]

    year = _local_year(now)
    timestamp = _now_ms(now)
    rate_by_date = {f"{year}-{day}": value for day, value in DEMO_RATE_TABLE}

    rates = [
        {"date": date, "value": value, "source": "Demo", "ts": timestamp}
        for date, value in rate_by_date.items()
    ]

    catalogue = list(products)
    new_products: list[dict[str, Any]] = []
    transactions: list[dict[str, Any]] = []

    for (
        day,
        slot,
        name,
        brand,
        unit,
        subcategory,
        store,
        quantity,
        unit_usd,
        payment,
        iva_mode,
        nature,
    ) in DEMO_SAMPLE:
        date = f"{year}-{day}"
        rate = rate_by_date.get(date) or app_rate_value or FALLBACK_RATE
        total_usd = quantity * unit_usd
        total_bs = total_usd * rate
        if iva_mode == "incluido":
            base_bs = total_bs / IVA_FACTOR
            iva_bs = total_bs - base_bs
        else:
            base_bs = total_bs
            iva_bs = 0.0

        product_id = ""
        existing = next(
            (
                product
                for product in catalogue
                if str(product.get("name", "")).lower() == name.lower()
            ),
            None,
        )
        if existing is not None:
            product_id = existing.get("id")
        else:
            created = {
                "id": sku_factory(),
                "workspace": workspace,
                "name": name,
                "name_lower": name.lower(),
                "categoryId": cat_by_slot[slot].get("id"),
                "brand": brand,
                "unit": unit,
                "subcategory": subcategory,
                "provider": store,
                "createdAt": timestamp,
                "updatedAt": timestamp,
            }
            new_products.append(created)
            catalogue.append(created)
            product_id = created["id"]

        transactions.append(
            {
                "workspace": workspace,
                "year": year,
                "date": date,
                "productId": product_id,
                "productName": name,
                "categoryId": cat_by_slot[slot].get("id"),
                "quantity": quantity,
                "unit": unit,
                "brand": brand,
                "subcategory": subcategory,
                "provider": store,
                "paymentMethod": payment,
                "originPlatform": "",
                "nature": nature,
                "taxMode": iva_mode,
                "baseImponible": js_round(base_bs, 2),
                "ivaMonto": js_round(iva_bs, 2),
                "amountBs": js_round(total_bs, 2),
                "amountUsd": js_round(total_usd, 4),
                "rate": js_round(rate, 4),
                "rateDate": date,
                "rateSource": "Demo",
                "customValues": {},
                "notes": "Registro Demo",
                "createdAt": timestamp,
                "updatedAt": timestamp,
            }
        )

    return {
        "rates": rates,
        "products": new_products,
        "transactions": transactions,
        "count": len(transactions),
    }


def fix_demo_dataset(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Retoques del ajuste sobre las compras demo, en orden de inserción.

    Sólo se devuelven las compras con ``rateSource === 'Demo'`` (las únicas que
    el ajuste vuelve a escribir). El contador de plataformas avanza con **cada**
    compra demo, tenga ya origen o no.

    >>> txs = [
    ...   {"id": 1, "rateSource": "Demo", "productName": "Arroz Blanco 1kg",
    ...    "quantity": 3, "amountUsd": 3.3},
    ...   {"id": 2, "rateSource": "Demo", "productName": "Café Molido Gourmet 500g",
    ...    "quantity": 1000, "amountUsd": 6.1, "rate": 44.6,
    ...    "amountBs": 272.06, "baseImponible": 234.53, "ivaMonto": 37.53},
    ...   {"id": 3, "rateSource": "manual", "productName": "Otra", "quantity": 1},
    ... ]
    >>> fixed = fix_demo_dataset(txs)
    >>> [tx["id"] for tx in fixed]
    [1, 2]
    >>> fixed[0]["originPlatform"], fixed[1]["originPlatform"]
    ('Banesco', 'Pago Movil')
    >>> fixed[1]["amountUsd"], fixed[1]["amountBs"]
    (12.2, 544.12)
    >>> fixed[1]["baseImponible"], fixed[1]["ivaMonto"]
    (469.07, 75.05)
    """
    updates: list[dict[str, Any]] = []
    index = 0
    for tx in transactions:
        if tx.get("rateSource") != "Demo":
            continue
        updated = dict(tx)
        if not updated.get("originPlatform"):
            updated["originPlatform"] = DEMO_ORIGINS[index % len(DEMO_ORIGINS)]
        name = str(updated.get("productName") or "")
        amount_usd = updated.get("amountUsd")
        if (
            "Café" in name
            and updated.get("quantity") == 1000
            and amount_usd is not None
            and float(amount_usd) < 8
        ):
            updated["amountUsd"] = 12.20
            updated["amountBs"] = js_round(
                12.20 * (js_number_or_zero(updated.get("rate")) or 44.6), 2
            )
            updated["baseImponible"] = js_round(updated["amountBs"] / IVA_FACTOR, 2)
            updated["ivaMonto"] = js_round(
                updated["amountBs"] - updated["baseImponible"], 2
            )
        updates.append(updated)
        index += 1
    return updates
