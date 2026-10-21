"""Pruebas del motor de análisis.

El verificación (la suite de contraste) ya compara estas mismas funciones contra el
JavaScript de referencia ejecutándolas con un DOM falso. Aquí se fijan los cálculos
con valores obtenidos a mano, para que la suite siga teniendo valor sin
no esté instalado.

Los valores esperados se derivan de las fórmulas de la versión de referencia:

* Laspeyres → peso = **gasto total** del producto, variación = primera compra
  frente a la última.
* Proyecciones → regresión lineal de mínimos cuadrados sobre los días
  transcurridos desde la primera observación.
* Recurrentes → ``próxima = última + intervalo`` calculada en medianoche UTC y
  leída con getters **locales**, lo que en un huso negativo devuelve el día
  anterior.
"""

from __future__ import annotations

import datetime as dt
import math

import pytest

from app.analytics import categories, extras, frequency, inflation, pivot, projection, variants
from app.analytics.common import by_product, series_from_history
from app.core.money import MoneyContext

CTX_USD = MoneyContext("USD", 2, 40.0)
CTX_VES = MoneyContext("VES", 2, 40.0)

PRODUCTS = [
    {"id": "p1", "name": "Harina", "unit": "kg"},
    {"id": "p2", "name": "Arroz", "unit": "kg"},
]

CATEGORIES = [
    {"id": "c1", "name": "Comida", "color": "#111111"},
    {"id": "c2", "name": "Ocio", "color": "#222222"},
]


def tx(**overrides):
    """Compra mínima con los campos que usan los cálculos."""
    base = {
        "productId": "p1",
        "productName": "Harina",
        "categoryId": "c1",
        "date": "2026-03-10",
        "quantity": 1,
        "amountUsd": 10.0,
        "amountBs": 400.0,
        "unit": "kg",
        "provider": "A",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# A · Precio e inflación
# ---------------------------------------------------------------------------


def test_analysis_a_kpis_de_un_producto() -> None:
    """Precio medio, variación y CAGR de un año exacto (100 → 121)."""
    txs = [
        tx(date="2026-01-01", amountUsd=100.0, amountBs=4000.0),
        tx(date="2027-01-01", amountUsd=121.0, amountBs=4840.0),
    ]
    view = inflation.analysis_a(txs, PRODUCTS, pid_a="p1", ctx=CTX_USD)

    assert view["puCount"] == "2"
    assert view["puAvg"] == "$ 110.50"
    assert view["puDelta"] == "+21.00%"
    assert view["puDeltaClass"] == "val bad"
    # (121/100)^(365/365) - 1 = 21 %
    assert view["puCagr"] == "+21.00% / año"
    assert view["puCagrClass"] == "val bad"


def test_analysis_a_sin_producto_usa_laspeyres() -> None:
    """Sin producto elegido solo se rellena el bloque Laspeyres."""
    txs = [
        tx(date="2026-01-05", quantity=2, amountUsd=10.0),
        tx(date="2026-02-05", quantity=2, amountUsd=12.0),
        tx(date="2026-03-05", quantity=1, amountUsd=7.0),
        tx(productId="p2", productName="Arroz", date="2026-01-08", quantity=3, amountUsd=9.0),
        tx(productId="p2", productName="Arroz", date="2026-02-08", quantity=3, amountUsd=12.0),
    ]
    view = inflation.analysis_a(txs, PRODUCTS, ctx=CTX_USD)

    assert view["puCount"] == "5"
    assert view["puAvg"] == "—"
    assert view["history"] == []
    # Harina: 5 → 7 (+40 %) con peso 29 · Arroz: 3 → 4 (+33.33 %) con peso 21
    assert view["laspeyresVal"] == "+37.20%"
    assert view["laspeyresSimple"] == "+36.67%"
    assert view["laspeyresDiff"] == "+0.53 pp"
    assert [row["name"] for row in view["top"]] == ["Harina", "Arroz"]
    assert [row["cls"] for row in view["top"]] == ["top1", "top2"]


def test_laspeyres_pondera_por_gasto_total() -> None:
    grouped = {
        "a": [
            {"date": "2026-01-01", "quantity": 1, "amountUsd": 10},
            {"date": "2026-02-01", "quantity": 1, "amountUsd": 12},
        ],
        "b": [
            {"date": "2026-01-01", "quantity": 1, "amountUsd": 90},
            {"date": "2026-02-01", "quantity": 1, "amountUsd": 99},
        ],
    }
    result = inflation.laspeyres(grouped)
    assert round(result["weighted"], 2) == 11.04
    assert round(result["simple"], 2) == 15.0
    assert round(result["diff"], 2) == -3.96


def test_series_from_history_rellena_dias_sin_compra() -> None:
    history = [
        type("H", (), {"date": "2026-01-01", "unit": 5.0})(),
        type("H", (), {"date": "2026-01-03", "unit": 8.0})(),
    ]
    assert series_from_history(history, ["2026-01-01", "2026-01-02", "2026-01-03"]) == [
        5.0,
        5.0,
        8.0,
    ]


# ---------------------------------------------------------------------------
# A-inner · Variantes de presentación
# ---------------------------------------------------------------------------


def test_variants_agrupa_por_unidad_y_elige_la_mas_economica() -> None:
    txs = [
        tx(date="2026-01-05", quantity=2, amountUsd=10.0, unit="kg"),
        tx(date="2026-02-05", quantity=2, amountUsd=12.0, unit="kg"),
        tx(date="2026-01-06", quantity=1, amountUsd=9.0, unit="docena"),
    ]
    view = variants.variants_view(txs, PRODUCTS, ctx=CTX_USD)

    assert view["empty"] is None
    # La "óptima" es la más económica (menor USD/unidad media) y el orden de las
    # filas también va de menor a mayor precio unitario.
    assert view["chips"]["bestKey"] == "kg"
    assert view["chips"]["variants"] == 2
    assert view["chips"]["bestUnit"] == "$ 5.5000"
    keys = [row["key"] for row in view["rows"]]
    assert keys == ["kg", "docena"]
    assert view["rows"][0]["unitUsd"] == "$ 5.5000"
    assert view["rows"][0]["pct"] == "71.0%"
    assert [row["best"] for row in view["rows"]] == [True, False]


def test_variants_radio_de_burbuja() -> None:
    """``max(6, min(34, sqrt(usd/maxUsd·34²/π)·π))``."""
    txs = [
        tx(date="2026-01-05", quantity=1, amountUsd=10.0, unit="kg"),
        tx(date="2026-02-05", quantity=1, amountUsd=2.0, unit="docena"),
    ]
    view = variants.variants_view(txs, PRODUCTS, ctx=CTX_USD)
    points = view["points"]
    # El mayor ocupa el radio máximo y el menor se calcula con la fórmula.
    assert max(point["r"] for point in points) == 34.0
    expected_small = max(6.0, min(34.0, math.sqrt((0.2 * 34 * 34 / math.pi)) * math.pi))
    assert min(point["r"] for point in points) == pytest.approx(expected_small)


# ---------------------------------------------------------------------------
# B · Pivote
# ---------------------------------------------------------------------------


def test_pivot_min_max_media_mediana_desvio() -> None:
    txs = [
        tx(provider="A", date="2026-03-01", quantity=1, amountUsd=4.0),
        tx(provider="A", date="2026-03-02", quantity=1, amountUsd=6.0),
        tx(provider="B", date="2026-03-01", quantity=1, amountUsd=9.0),
    ]
    view = pivot.pivot_view(txs)

    assert view["summary"]["groups"] == "2"
    assert view["summary"]["cheapest"] == "A"
    assert view["summary"]["mostExpensive"] == "B"
    # 9 − 5 = 4 (diferencia de precio medio unitario)
    assert view["summary"]["savings"] == "$ 4.0000"
    first = view["rows"][0]
    assert first["key"] == "A"
    assert (first["minUsd"], first["maxUsd"]) == ("$ 4.0000", "$ 6.0000")
    assert first["avgUsd"] == "$ 5.0000"
    assert first["medUsd"] == "$ 5.0000"
    assert first["stdUsd"] == "$ 1.4142"


def test_pivot_filtro_mismo_dia() -> None:
    """Con ``same_day_only`` se descartan los días con un solo comercio."""
    txs = [
        tx(provider="A", date="2026-03-01", quantity=1, amountUsd=4.0),
        tx(provider="B", date="2026-03-01", quantity=1, amountUsd=9.0),
        tx(provider="A", date="2026-03-02", quantity=1, amountUsd=6.0),
    ]
    view = pivot.pivot_view(txs, same_day_only=True)
    assert view["summary"]["groups"] == "2"
    # el orden de las filas es por gasto total descendente
    assert [row["key"] for row in view["rows"]] == ["B", "A"]
    assert view["rows"][1]["count"] == "1"


def test_pivot_sin_datos() -> None:
    view = pivot.pivot_view([])
    assert view["empty"] == "Sin datos para pivote en el período."
    assert view["rows"] == []
    assert view["chart"]["labels"] == []


# ---------------------------------------------------------------------------
# C · Frecuencia de compra
# ---------------------------------------------------------------------------


def test_frequency_intervalo_y_proxima_compra() -> None:
    txs = [
        tx(provider="A", date="2026-01-05", quantity=2, amountUsd=10.0),
        tx(provider="A", date="2026-02-05", quantity=2, amountUsd=12.0),
    ]
    view = frequency.frequency_view(txs, CATEGORIES)

    row = view["rows"][0]
    assert row["key"] == "A"
    assert row["interval"] == "31.0 días"
    assert row["avgQty"] == "2.00"
    assert row["avgTicket"] == "$ 11.00"
    assert row["totalUsd"] == "$ 22.00"
    assert row["lastDate"] == "2026-02-05"
    # 05/02 + 31 días = 08/03 en medianoche UTC; los getters locales (UTC−4)
    # devuelven el día anterior.
    assert row["next"] == "2026-03-07"
    assert row["soon"] is False


def test_frequency_soon_y_orden() -> None:
    txs = [
        tx(provider="A", date="2026-03-01", quantity=1, amountUsd=5.0),
        tx(provider="A", date="2026-03-10", quantity=1, amountUsd=5.0),
        tx(provider="B", date="2026-03-10", quantity=1, amountUsd=100.0),
        tx(provider="B", date="2026-03-11", quantity=1, amountUsd=100.0),
    ]
    # La fecha de "hoy" es la de los casos del verificación.
    now = dt.datetime(2026, 3, 15, 12, 0, 0)
    view = frequency.frequency_view(txs, CATEGORIES, now=now)
    keys = [row["key"] for row in view["rows"]]
    assert keys == ["B", "A"]  # orden por total gastado, descendente
    by_key = {row["key"]: row for row in view["rows"]}
    # A: intervalo 9 días → próxima 18/03, a 3 días de "hoy"
    assert by_key["A"]["soon"] is True
    assert by_key["A"]["interval"] == "9.0 días"
    assert by_key["B"]["interval"] == "1.0 días"


# ---------------------------------------------------------------------------
# D · Proyecciones
# ---------------------------------------------------------------------------


def test_rate_projection_horizontes_y_modelo() -> None:
    rates = [
        {"date": "2026-01-01", "value": 40.0},
        {"date": "2026-03-01", "value": 60.0},
    ]
    view = projection.rate_projection(rates)

    assert view["empty"] is None
    # b = 20/59; a 7 días → 40 + 0.338983·66 = 62.3729
    assert [(row["days"], row["rate"], row["pct"]) for row in view["rows"]] == [
        (7, "62,3729 Bs/$", "+3.95%"),
        (30, "70,1695 Bs/$", "+16.95%"),
        (90, "90,5085 Bs/$", "+50.85%"),
        (180, "121,0169 Bs/$", "+101.69%"),
        (365, "183,7288 Bs/$", "+206.21%"),
    ]
    assert view["model"] == "y = 40.0000 + 0.3390·días · R²=1.000"


def test_rate_projection_necesita_dos_tasas() -> None:
    view = projection.rate_projection([{"date": "2026-01-01", "value": 40.0}])
    assert view["empty"] == "Se necesitan al menos 2 tasas históricas registradas."
    assert view["rows"] == []
    assert view["chart"] is None


def test_product_projection_stats_y_modelo() -> None:
    purchases = [
        tx(date="2026-01-01", quantity=1, amountUsd=2.0, amountBs=80.0),
        tx(date="2026-04-01", quantity=1, amountUsd=4.0, amountBs=160.0),
    ]
    view = projection.product_projection(purchases, [], horizon_value="30")

    assert view["stats"]["currentUsd"] == "$ 4.0000"
    # 90 días de histórico + 30 de horizonte → 2 + (2/90)·120
    assert view["stats"]["projUsd"] == "$ 4.6667"
    assert view["stats"]["deltaUsd"] == "+16.67%"
    assert view["stats"]["currentBs"] == "Bs. 160,00"
    assert view["stats"]["rate"] == "160,00 Bs/$"
    assert view["model"]["count"] == 2
    assert view["model"]["usd"] == "y = 2.0000 + 0.02222·d · R² = 1.000"


def test_product_projection_horizonte_personalizado() -> None:
    purchases = [
        tx(date="2026-01-01", quantity=1, amountUsd=2.0, amountBs=80.0),
        tx(date="2026-04-01", quantity=1, amountUsd=4.0, amountBs=160.0),
    ]
    view = projection.product_projection(
        purchases, [], horizon_value="custom", custom_days="45"
    )
    assert view["stats"]["horizon"] == 45
    # 2 + (2/90)·135 = 5
    assert view["stats"]["projUsd"] == "$ 5.0000"


def test_product_projection_estados_vacios() -> None:
    empty = projection.product_projection([], [], selected=False)
    assert empty["empty"] == "Selecciona un producto."

    one = projection.product_projection([tx()], [])
    assert one["empty"] == "Se necesitan al menos 2 compras del producto."


def test_product_projection_usa_la_tasa_proyectada() -> None:
    purchases = [
        tx(date="2026-01-01", quantity=1, amountUsd=2.0, amountBs=80.0),
        tx(date="2026-04-01", quantity=1, amountUsd=4.0, amountBs=160.0),
    ]
    rates = [
        {"date": "2026-01-01", "value": 40.0},
        {"date": "2026-03-01", "value": 60.0},
    ]
    view = projection.product_projection(
        purchases, rates, app_rate_value=60.0, horizon_value="30"
    )
    # 40 + (20/59)·(59+30) = 70.1695
    assert view["stats"]["rate"] == "70,1695 Bs/$"


# ---------------------------------------------------------------------------
# E · Categorías, IVA y pagos
# ---------------------------------------------------------------------------


def test_category_impact_convierte_iva_con_la_tasa_de_cada_compra() -> None:
    """Bug #1 de la versión de referencia: ``ivaMonto`` viene en Bs y se pasa a USD con la
    tasa **histórica** de la transacción."""
    txs = [
        tx(categoryId="c1", amountUsd=10.0, amountBs=400.0, ivaMonto=16.0, rate=40.0),
        tx(categoryId="c1", amountUsd=10.0, amountBs=800.0, ivaMonto=32.0, rate=80.0),
    ]
    view = categories.category_impact(txs, CATEGORIES, app_rate_value=100.0)

    row = view["rows"][0]
    assert row["name"] == "Comida"
    assert row["count"] == "2"
    assert row["totalUsd"] == "$ 20.00"
    # 16/40 + 32/80 = 0.4 + 0.4
    assert row["ivaUsd"] == "$ 0.80"
    assert row["pct"] == "100.0%"


def test_category_impact_sin_categoria_conocida_y_sin_tasa() -> None:
    txs = [
        tx(categoryId="zz", amountUsd=4.0, amountBs=160.0, ivaMonto=8.0, rate=0),
    ]
    view = categories.category_impact(txs, CATEGORIES, app_rate_value=40.0)
    assert view["rows"][0]["name"] == "Sin categoría"
    assert view["rows"][0]["color"] == "#6B7280"
    # Sin tasa en la compra cae a la tasa activa (40).
    assert view["rows"][0]["ivaUsd"] == "$ 0.20"


def test_category_impact_inflacion_extra() -> None:
    txs = [
        tx(categoryId="c1", date="2026-03-01", quantity=2, amountUsd=4.0),
        tx(categoryId="c1", date="2026-03-15", quantity=2, amountUsd=8.0),
        tx(categoryId="c1", date="2026-03-25", quantity=1, amountUsd=5.0),
    ]
    view = categories.category_impact(txs, CATEGORIES)
    # unidades: 2 → 4 → 5; (5 − 2) · 1 compra final = 3
    assert view["rows"][0]["extraInflation"] == "+$ 3.00"
    assert view["rows"][0]["extraInflationUp"] is True


def test_vat_audit() -> None:
    txs = [
        tx(ivaMonto=16.0, baseImponible=100.0, amountBs=116.0, taxMode="incluido"),
        tx(ivaMonto=None, baseImponible=0.0, amountBs=50.0, taxMode="exento"),
    ]
    view = categories.vat_audit(txs)
    assert view["ivaTotal"] == "Bs. 16,00"
    assert view["baseTotal"] == "Bs. 100,00"
    assert view["taxed"] == "1"
    assert view["exento"] == "1"
    assert view["exentoTotal"] == "Bs. 50,00"
    # 16 / 166 · 100
    assert view["weightedIva"] == "9.64%"


def test_vat_audit_sin_gasto() -> None:
    view = categories.vat_audit([])
    assert view["weightedIva"] == "0%"
    assert view["ivaTotal"] == "Bs. 0,00"


def test_payment_impact_reparto_y_liquido() -> None:
    txs = [
        tx(paymentMethod="Efectivo Bs", amountUsd=10.0, amountBs=400.0),
        tx(paymentMethod="Pago Móvil", amountUsd=5.0, amountBs=200.0),
        tx(paymentMethod="Efectivo USD", amountUsd=5.0, amountBs=200.0),
    ]
    view = categories.payment_impact(txs)
    assert [row["key"] for row in view["rows"]] == [
        "Efectivo Bs",
        "Pago Móvil",
        "Efectivo USD",
    ]
    assert view["rows"][0]["pct"] == "50.0%"
    assert view["cashUsd"] == 15.0
    assert view["bankUsd"] == 5.0
    assert view["totalBsLiquidity"] == 800.0


def test_liquidity_split_separa_bs_de_divisas() -> None:
    """El ajuste de ``runAnalysisE`` separa por método y plataforma de origen."""
    txs = [
        tx(paymentMethod="Efectivo Bs", amountUsd=10.0),
        tx(paymentMethod="Pago Móvil", amountUsd=4.0),
        tx(paymentMethod="Efectivo USD", amountUsd=5.0),
        tx(paymentMethod="Transferencia", originPlatform="Binance P2P", amountUsd=3.0),
        tx(paymentMethod="Transferencia", originPlatform="Nómina", amountUsd=2.0),
    ]
    split = categories.liquidity_split(txs)
    assert split["usd"] == 8.0
    assert split["bsUsd"] == 16.0


def test_liquidity_split_redondea_a_dos_decimales() -> None:
    txs = [tx(paymentMethod="Pago Móvil", amountUsd=3.14159)]
    assert categories.liquidity_split(txs)["bsUsd"] == 3.14


# ---------------------------------------------------------------------------
# Extras del sub-panel E
# ---------------------------------------------------------------------------


def test_budget_traffic_light_estados_y_orden() -> None:
    txs = [
        # promedio histórico 20 → el mes auditado (60) es una desviación fuerte
        {"date": "2026-03-05", "categoryId": "c1", "amountUsd": 20, "amountBs": 800},
        {"date": "2026-04-05", "categoryId": "c1", "amountUsd": 20, "amountBs": 800},
        {"date": "2026-06-05", "categoryId": "c1", "amountUsd": 60, "amountBs": 3000},
        {"date": "2026-06-06", "categoryId": "c2", "amountUsd": 5, "amountBs": 250},
    ]
    view = extras.budget_traffic_light(
        txs,
        CATEGORIES,
        fiscal_year=2026,
        now=dt.datetime(2026, 6, 15, 12),
        ctx=CTX_USD,
    )
    assert view["empty"] is None
    # El ajuste ya no reordena por estado: las filas siguen el orden de las
    # categorías y el chip vive dentro de la fila.
    assert [(row["name"], row["state"]) for row in view["rows"]] == [
        ("Comida", "over"),
        ("Ocio", "new"),
    ]
    assert view["rows"][0]["delta"] == "+200.0%"
    assert view["rows"][0]["chip"] == "Excede +200.0%"
    assert view["rows"][0]["trend"] == ""
    assert view["chips"] == ["Excede +200.0%", "Nueva"]


def test_budget_traffic_light_sin_categorias() -> None:
    view = extras.budget_traffic_light(
        [], [], fiscal_year=2026, now=dt.datetime(2026, 6, 15, 12), ctx=CTX_USD
    )
    assert view["empty"] is None
    assert view["chips"] == []
    assert view["rows"] == []


def test_budget_traffic_light_en_bolivares() -> None:
    """En vista VES ``fmtMoney`` usa el importe en Bs cuando existe."""
    txs = [
        {"date": "2026-03-05", "categoryId": "c1", "amountUsd": 20, "amountBs": 800},
        {"date": "2026-04-05", "categoryId": "c1", "amountUsd": 20, "amountBs": 800},
        {"date": "2026-06-05", "categoryId": "c1", "amountUsd": 20, "amountBs": 400},
    ]
    view = extras.budget_traffic_light(
        txs,
        CATEGORIES,
        fiscal_year=2026,
        now=dt.datetime(2026, 6, 15, 12),
        ctx=CTX_VES,
    )
    assert view["rows"][0]["current"] == "Bs. 400,00"
    assert view["rows"][0]["average"] == "Bs. 800,00"


def test_pareto_acumulado_y_color() -> None:
    txs = [
        tx(categoryId="c1", amountUsd=80.0),
        tx(categoryId="c2", amountUsd=20.0),
        tx(categoryId="c1", amountUsd=-5.0),
    ]
    view = extras.pareto(txs, CATEGORIES)
    assert view["empty"] is False
    assert view["labels"] == ["Comida", "Ocio"]
    assert view["values"] == [75.0, 20.0]
    assert view["cumulative"] == [pytest.approx(78.947368), pytest.approx(100.0)]
    assert view["colors"] == ["#111111c0", "#222222c0"]
    assert view["borders"] == ["#111111", "#222222"]


def test_pareto_sin_gasto_positivo() -> None:
    view = extras.pareto([tx(amountUsd=0.0)], CATEGORIES)
    assert view["empty"] is True
    assert view["labels"] == []


def test_sparklines_geometria_y_meses() -> None:
    txs = [
        {"date": "2026-02-05", "categoryId": "c1", "amountUsd": 5},
        {"date": "2026-03-05", "categoryId": "c1", "amountUsd": 10},
    ]
    view = extras.sparklines(
        txs,
        CATEGORIES,
        fiscal_year=2026,
        now=dt.datetime(2026, 3, 15, 12),
        width=60,
        height=24,
    )
    assert view["months"] == [
        "2025-10",
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
        "2026-03",
    ]
    assert view["series"]["c1"] == [0.0, 0.0, 0.0, 0.0, 5.0, 10.0]
    # Geometría del ajuste: x = (i/(n-1))·(w−4)+2, y = h−3−(v/max)·(h−6).
    assert view["points"]["c1"][0] == [2.0, 21.0]
    assert view["points"]["c1"][5] == [58.0, 3.0]
    assert view["colors"]["c1"] == "#111111"


def test_sparklines_incluye_canvas_desconocidos() -> None:
    """Los ``canvas`` presentes en el DOM se dibujan aunque la categoría no exista."""
    view = extras.sparklines(
        [{"date": "2026-03-05", "categoryId": "zz", "amountUsd": 4}],
        CATEGORIES,
        fiscal_year=2026,
        now=dt.datetime(2026, 3, 15, 12),
        width=60,
        height=24,
        canvas_ids=["zz"],
    )
    assert view["series"]["zz"] == [0.0, 0.0, 0.0, 0.0, 0.0, 4.0]
    assert view["colors"]["zz"] == "#2563EB"


def test_outlier_scatter_marca_outliers() -> None:
    txs = [tx(date=f"2026-03-0{i}", amountUsd=10.0) for i in range(1, 8)]
    txs.append(tx(date="2026-03-09", amountUsd=100.0, provider="Z"))
    view = extras.outlier_scatter(txs, CATEGORIES)

    assert view["empty"] is False
    assert view["points"][-1]["outlier"] is True
    assert view["points"][0]["outlier"] is False
    assert view["points"][-1]["x"] == 9
    assert view["points"][-1]["tooltip"].endswith("Outlier")
    assert [group["color"] for group in view["groups"]] == ["#11111190"]


def test_outlier_scatter_ignora_importes_no_positivos() -> None:
    view = extras.outlier_scatter([tx(amountUsd=0.0)], CATEGORIES)
    assert view["empty"] is True
    assert view["points"] == []


def test_hierarchical_tree_totales_y_productos() -> None:
    txs = [
        tx(categoryId="c1", subcategory="Lácteos", quantity=2, amountUsd=10.0, amountBs=400.0),
        tx(categoryId="c1", subcategory="Lácteos", quantity=1, amountUsd=5.0, amountBs=200.0),
        tx(categoryId="c1", subcategory="", quantity=3, amountUsd=12.0, amountBs=480.0,
           productId="p2", productName="Arroz"),
    ]
    view = extras.hierarchical_tree(txs, CATEGORIES, ctx=CTX_USD)

    assert view["empty"] is None
    assert [(node["level"], node["name"]) for node in view["nodes"]] == [
        ("cat", "Comida"),
        ("sub", "Lácteos"),
        ("sub", "— Sin subcategoría —"),
    ]
    assert view["nodes"][0]["total"] == "$ 27.00"
    assert view["nodes"][0]["qty"] == "6.00 unid."
    assert [prod["pos"] for prod in view["prods"]] == ["2×", "1×"]
    assert view["prods"][0]["meta"] == "3.00 kg · $ 15.00"


def test_hierarchical_tree_sin_transacciones() -> None:
    view = extras.hierarchical_tree([], CATEGORIES, ctx=CTX_USD)
    assert view["empty"] == "Sin transacciones en el período."
    assert view["nodes"] == []


# ---------------------------------------------------------------------------
# Auxiliares de agrupación
# ---------------------------------------------------------------------------


def test_by_product_respeta_el_orden_de_aparicion() -> None:
    txs = [
        tx(productId="b", date="2026-01-01"),
        tx(productId="a", date="2026-02-01"),
        tx(productId="b", date="2026-03-01"),
    ]
    grouped = by_product(txs)
    assert list(grouped) == ["b", "a"]
    assert len(grouped["b"]) == 2
