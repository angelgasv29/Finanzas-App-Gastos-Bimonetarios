"""Sub-pestaña E · Categorías · IVA · Pagos (``runAnalysisE``, 5615-5754).

Tres bloques:

1. **Impacto por categoría**: gasto, IVA convertido a USD con la tasa histórica
   de cada compra (Bug #1 corregido en la versión de referencia) e inflación extra estimada.
2. **Auditoría de IVA**: acumulado, base imponible, gravadas y exentas.
3. **Formas de pago**: reparto por método y líquido (efectivo frente a banco).
"""

from __future__ import annotations

from typing import Any

from ..core.money import format_bs, format_usd, js_number_or_zero, js_round, js_to_fixed
from ..core.stats import unit_price

__all__ = ["category_impact", "vat_audit", "payment_impact", "liquidity_split"]

NO_CATEGORY = "Sin categoría"
NO_CATEGORY_COLOR = "#6B7280"
NO_PAYMENT = "No especificado"
CASH_METHODS = ("Efectivo Bs", "Efectivo USD")

# Conjuntos del ajuste de ``runAnalysisE``.
USD_PAYMENT_METHODS = frozenset({"Efectivo USD", "Zelle", "Billetera Digital/Cripto"})
USD_ORIGIN_PLATFORMS = frozenset(
    {"Binance P2P", "Zinli", "Efectivo USD", "Wally", "PayPal", "Zelle"}
)


def liquidity_split(txs: list[dict[str, Any]]) -> dict[str, float]:
    """Reparto real del gasto entre bolívares y divisas (ajuste de ``runAnalysisE``).

    La versión de referencia sustituye el gráfico de liquidez por uno que separa lo pagado en
    Bs de lo pagado en divisas, mirando el **método de pago** y la **plataforma
    de origen**:

    >>> txs = [
    ...   {"paymentMethod": "Efectivo USD", "amountUsd": 10},
    ...   {"paymentMethod": "Pago Movil", "amountUsd": 5},
    ...   {"paymentMethod": "Transferencia Bancaria", "originPlatform": "Binance P2P", "amountUsd": 2},
    ...   {"paymentMethod": "Efectivo Bs", "amountUsd": 3},
    ... ]
    >>> split = liquidity_split(txs)
    >>> split["usd"], split["bsUsd"]
    (12.0, 8.0)
    """
    paid_usd = 0.0
    paid_bs_in_usd = 0.0
    for tx in txs:
        if (
            tx.get("paymentMethod") in USD_PAYMENT_METHODS
            or tx.get("originPlatform") in USD_ORIGIN_PLATFORMS
        ):
            paid_usd += js_number_or_zero(tx.get("amountUsd"))
        else:
            paid_bs_in_usd += js_number_or_zero(tx.get("amountUsd"))
    return {"bsUsd": js_round(paid_bs_in_usd, 2), "usd": js_round(paid_usd, 2)}


def _rate_for_iva(tx: dict[str, Any], app_rate_value: float | None) -> float:
    """``Number(t.rate) || (APP.rate && APP.rate.value) || 1``."""
    return js_number_or_zero(tx.get("rate")) or js_number_or_zero(
        app_rate_value
    ) or 1.0


def category_impact(
    txs: list[dict[str, Any]],
    categories: list[dict[str, Any]],
    *,
    app_rate_value: float | None = None,
    decimals: int = 2,
) -> dict[str, Any]:
    """Tabla de impacto por categoría.

    >>> txs = [
    ...   {"categoryId": "c1", "amountUsd": 10, "amountBs": 400, "ivaMonto": 16, "rate": 40},
    ...   {"categoryId": "c1", "amountUsd": 5, "amountBs": 200, "ivaMonto": 8, "rate": 40},
    ... ]
    >>> view = category_impact(txs, [{"id": "c1", "name": "Comida", "color": "#123456"}])
    >>> view["rows"][0]["name"], view["rows"][0]["count"], view["rows"][0]["ivaUsd"]
    ('Comida', '2', '$ 0.60')
    """
    by_category: dict[str, dict[str, Any]] = {}
    for tx in txs:
        category_id = tx.get("categoryId") or "none"
        found = next(
            (c for c in categories if c.get("id") == tx.get("categoryId")), None
        )
        group = by_category.get(category_id)
        if group is None:
            group = {
                "key": category_id,
                "name": (found or {}).get("name") or NO_CATEGORY,
                "color": (found or {}).get("color") or NO_CATEGORY_COLOR,
                "totalUsd": 0.0,
                "totalBs": 0.0,
                "ivaUsd": 0.0,
                "count": 0,
                "records": [],
            }
            by_category[category_id] = group
        group["totalUsd"] += js_number_or_zero(tx.get("amountUsd"))
        group["totalBs"] += js_number_or_zero(tx.get("amountBs"))
        group["ivaUsd"] += js_number_or_zero(tx.get("ivaMonto")) / _rate_for_iva(
            tx, app_rate_value
        )
        group["count"] += 1
        group["records"].append(tx)

    ordered = sorted(
        by_category.values(), key=lambda group: group["totalUsd"], reverse=True
    )
    total_usd = 0.0
    for group in ordered:
        total_usd += group["totalUsd"]

    rows: list[dict[str, Any]] = []
    for group in ordered:
        # ``if (!skuInCat[r.productId])``: una clave vacía se recrea cada vez.
        by_product: dict[Any, list[dict[str, Any]]] = {}
        for record in group["records"]:
            product_id = record.get("productId")
            bucket = by_product.get(product_id) if product_id else None
            if bucket is None:
                bucket = []
                by_product[product_id] = bucket
            bucket.append(record)

        extra_inflation = 0.0
        for purchases in by_product.values():
            if len(purchases) < 2:
                continue
            purchases.sort(key=lambda tx: tx.get("date") or "")
            first_unit = purchases[0].get("unitPriceUsd") or unit_price(
                purchases[0]
            )["unitUsd"]
            last = purchases[-1]
            last_unit = last.get("unitPriceUsd") or unit_price(last)["unitUsd"]
            extra_inflation += (last_unit - first_unit) * (
                js_number_or_zero(last.get("quantity")) or 1
            )

        rows.append(
            {
                "key": group["key"],
                "name": group["name"],
                "color": group["color"],
                "count": str(group["count"]),
                "totalUsd": format_usd(group["totalUsd"], decimals),
                "pct": (
                    js_to_fixed((group["totalUsd"] / total_usd) * 100, 1) + "%"
                    if total_usd
                    else "0%"
                ),
                "ivaUsd": format_usd(group["ivaUsd"], decimals),
                "extraInflation": (
                    ("+" if extra_inflation >= 0 else "")
                    + format_usd(extra_inflation, decimals)
                ),
                "extraInflationUp": extra_inflation > 0,
            }
        )

    return {
        "empty": None if rows else "Sin datos.",
        "rows": rows,
        "chart": {
            "labels": [group["name"] for group in ordered],
            "values": [group["totalUsd"] for group in ordered],
            "colors": [group["color"] for group in ordered],
        },
    }


def vat_audit(txs: list[dict[str, Any]]) -> dict[str, Any]:
    """Auditoría de IVA del período.

    >>> txs = [
    ...   {"ivaMonto": 16, "baseImponible": 100, "amountBs": 116, "taxMode": "incluido"},
    ...   {"ivaMonto": None, "baseImponible": 0, "amountBs": 50, "taxMode": "exento"},
    ... ]
    >>> view = vat_audit(txs)
    >>> view["ivaTotal"], view["baseTotal"], view["weightedIva"]
    ('Bs. 16,00', 'Bs. 100,00', '9.64%')
    """
    iva_total = 0.0
    base_total = 0.0
    total_bs = 0.0
    exento_total = 0.0
    exento_count = 0
    taxed_count = 0
    for tx in txs:
        iva_total += js_number_or_zero(tx.get("ivaMonto"))
        base_total += js_number_or_zero(tx.get("baseImponible"))
        amount_bs = js_number_or_zero(tx.get("amountBs"))
        total_bs += amount_bs
        if tx.get("taxMode") == "exento":
            exento_count += 1
            exento_total += amount_bs
        else:
            taxed_count += 1

    return {
        "ivaTotal": format_bs(iva_total),
        "baseTotal": format_bs(base_total),
        "taxed": str(taxed_count),
        "exento": str(exento_count),
        "exentoTotal": format_bs(exento_total),
        "weightedIva": (
            js_to_fixed((iva_total / total_bs) * 100, 2) + "%" if total_bs else "0%"
        ),
    }


def payment_impact(txs: list[dict[str, Any]], *, decimals: int = 2) -> dict[str, Any]:
    """Reparto por método de pago y líquido efectivo/banco.

    >>> txs = [
    ...   {"paymentMethod": "Efectivo Bs", "amountUsd": 10, "amountBs": 400},
    ...   {"paymentMethod": "Pago Móvil", "amountUsd": 5, "amountBs": 200},
    ... ]
    >>> view = payment_impact(txs)
    >>> [(row["key"], row["pct"]) for row in view["rows"]]
    [('Efectivo Bs', '66.7%'), ('Pago Móvil', '33.3%')]
    >>> view["cashUsd"], view["bankUsd"]
    (10.0, 5.0)
    """
    by_payment: dict[str, dict[str, Any]] = {}
    for tx in txs:
        method = tx.get("paymentMethod") or NO_PAYMENT
        group = by_payment.get(method)
        if group is None:
            group = {"count": 0, "totalUsd": 0.0, "totalBs": 0.0}
            by_payment[method] = group
        group["count"] += 1
        group["totalUsd"] += js_number_or_zero(tx.get("amountUsd"))
        group["totalBs"] += js_number_or_zero(tx.get("amountBs"))

    ordered = sorted(
        by_payment.items(), key=lambda item: item[1]["totalUsd"], reverse=True
    )
    total_usd = 0.0
    for _key, group in ordered:
        total_usd += group["totalUsd"]

    rows = [
        {
            "key": key,
            "count": str(group["count"]),
            "totalUsd": format_usd(group["totalUsd"], decimals),
            "pct": (
                js_to_fixed((group["totalUsd"] / total_usd) * 100, 1) + "%"
                if total_usd
                else "0%"
            ),
        }
        for key, group in ordered
    ]

    cash_usd = 0.0
    bank_usd = 0.0
    total_bs_liquidity = 0.0
    total_usd_liquidity = 0.0
    for tx in txs:
        method = tx.get("paymentMethod") or ""
        amount_usd = js_number_or_zero(tx.get("amountUsd"))
        if method in CASH_METHODS:
            cash_usd += amount_usd
        else:
            bank_usd += amount_usd
        total_bs_liquidity += js_number_or_zero(tx.get("amountBs"))
        total_usd_liquidity += amount_usd

    return {
        "empty": None if rows else "Sin datos.",
        "rows": rows,
        "cashUsd": cash_usd,
        "bankUsd": bank_usd,
        "totalBsLiquidity": total_bs_liquidity,
        "totalUsdLiquidity": total_usd_liquidity,
    }
