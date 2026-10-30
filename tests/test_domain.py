"""Pruebas de las reglas de negocio.

El verificación (la suite de contraste) ya compara las **vistas** contra el
JavaScript de referencia. Aquí se fijan las reglas de negocio que no pasan por la
interfaz —alta, edición, filtros, tasas, avisos— con valores calculados a mano,
para que la suite siga siendo útil sin depender de herramientas externas.
"""

from __future__ import annotations

import datetime as dt
import math

import pytest

from app.core.money import MoneyContext, js_parse_float, js_round, js_to_fixed
from app.domain import (
    breakeven,
    dates,
    filters,
    prices,
    rates,
    recurring,
    runrate,
    transactions,
    vat,
)
from app.domain.errors import MissingRateError, ValidationError

IVA = 0.16
CTX_USD = MoneyContext("USD", 2, 40.0)
CTX_VES = MoneyContext("VES", 2, 40.0)


def tx(**overrides):
    """Transacción mínima con los campos que usan los cálculos."""
    base = {
        "date": "2026-03-10",
        "amountUsd": 10.0,
        "amountBs": 400.0,
        "nature": "Extraordinario",
        "taxMode": "incluido",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# IVA
# ---------------------------------------------------------------------------


def test_iva_incluido_deriva_la_base_del_total():
    amounts = vat.compute_vat(116, "incluido")
    assert amounts.total == 116
    assert amounts.base == pytest.approx(100)
    # El IVA es una resta, no una multiplicación: 116 − 100 = 16.
    assert amounts.iva == pytest.approx(16)
    assert amounts.base + amounts.iva == amounts.total


def test_iva_exento_no_calcula_impuesto():
    amounts = vat.compute_vat(116, "exento")
    assert (amounts.base, amounts.iva, amounts.total) == (116, 0, 116)


def test_iva_mas_iva_suma_al_monto():
    amounts = vat.compute_vat(100, "mas_iva")
    assert amounts.base == 100
    assert amounts.iva == pytest.approx(16)
    assert amounts.total == pytest.approx(116)


@pytest.mark.parametrize("mode", ["mas_iva", "lo-que-sea", ""])
def test_cualquier_modo_desconocido_cae_en_mas_iva(mode):
    assert vat.compute_vat(100, mode).total == pytest.approx(116)


@pytest.mark.parametrize("raw", ["abc", "", None, "0"])
def test_monto_no_numerico_es_cero(raw):
    amounts = vat.compute_vat(raw, "incluido")
    assert (amounts.base, amounts.iva, amounts.total) == (0, 0, 0)


def test_iva_acepta_prefijo_numerico_como_parsefloat():
    # ``parseFloat('12.5kg')`` es 12.5 en JavaScript.
    assert vat.compute_vat("12.5kg", "exento").total == 12.5


def test_rounded_vat_redondea_a_dos_decimales():
    amounts = vat.rounded_vat(100.05, "incluido")
    assert amounts.base == 86.25
    assert amounts.iva == 13.8
    assert amounts.total == 100.05


def test_vista_previa_escribe_los_cuatro_nodos():
    view = vat.vat_preview(116, "incluido", 36.64, CTX_VES)
    assert view == {
        "vpBaseBs": "Bs. 100,00",
        "vpIvaBs": "Bs. 16,00",
        "vpTotalBs": "Bs. 116,00",
        "vpTotalUsd": "$ 3.17",
    }


def test_vista_previa_sin_tasa_deja_el_usd_en_cero():
    assert vat.vat_preview(116, "exento", None, CTX_VES)["vpTotalUsd"] == "$ 0.00"


# ---------------------------------------------------------------------------
# Tasas
# ---------------------------------------------------------------------------


def test_tasa_exacta_para_la_fecha():
    store = [
        {"date": "2026-03-15", "value": 36.64, "source": "BCV"},
        {"date": "2026-01-10", "value": 36.05, "source": "manual"},
    ]
    found = rates.get_rate_for_date(store, "2026-03-15")
    assert found == {"value": 36.64, "date": "2026-03-15", "source": "BCV"}


def test_tasa_historica_usa_la_ultima_anterior():
    store = [
        {"date": "2026-03-15", "value": 36.64, "source": "BCV"},
        {"date": "2026-01-10", "value": 36.05, "source": "manual"},
    ]
    found = rates.get_rate_for_date(store, "2026-02-01")
    assert found["value"] == 36.05
    assert found["date"] == "2026-01-10"
    assert found["source"] == "manual (histórico)"


def test_tasa_anterior_a_la_primera_no_existe():
    store = [{"date": "2026-03-15", "value": 36.64, "source": "BCV"}]
    assert rates.get_rate_for_date(store, "2025-12-31") is None


def test_tasa_sin_fecha_es_la_activa():
    active = {"value": 1.0, "date": "d", "source": "s"}
    assert rates.get_rate_for_date([], None, active) is active


def test_rate_value_of_descarta_valores_falsos():
    assert rates.rate_value_of({"value": 36.64}) == 36.64
    assert rates.rate_value_of({"value": 0}) == 0
    assert rates.rate_value_of(None) == 0
    assert rates.rate_value_of({}) == 0


def test_orden_de_tasas_descendente():
    store = [{"date": "2026-01-10"}, {"date": "2026-03-15"}]
    assert [r["date"] for r in rates.sort_rates_desc(store)] == [
        "2026-03-15",
        "2026-01-10",
    ]


def test_tasa_activa_solo_cambia_sin_bloqueo_de_sesion():
    newest = {"value": 36.64, "date": "2026-03-15", "source": "BCV"}
    old = {"value": 1.0, "date": "2020-01-01", "source": "x"}
    assert rates.pick_active_rate([newest], old, session_locked=True) is old
    assert rates.pick_active_rate([newest], old)["date"] == "2026-03-15"
    assert rates.pick_active_rate([], None) is None


# ---------------------------------------------------------------------------
# Transacciones
# ---------------------------------------------------------------------------


def test_alta_completa_calcula_iva_y_dolares():
    record = transactions.build_transaction(
        workspace="personal",
        date="2026-03-15",
        category_id="cat_1",
        product_name="Harina",
        rate={"value": 36.64, "date": "2026-03-15", "source": "BCV"},
        bs_amount=116,
        mode="incluido",
        quantity="2",
        unit="kg",
        brand="  PAN  ",
        timestamp=1,
    )
    assert record["year"] == 2026
    assert record["baseImponible"] == 100.0
    assert record["ivaMonto"] == 16.0
    assert record["amountBs"] == 116.0
    assert record["amountUsd"] == 3.1659
    assert record["rate"] == 36.64
    assert record["rateDate"] == "2026-03-15"
    assert record["rateSource"] == "BCV"
    assert record["quantity"] == 2
    assert record["brand"] == "PAN"
    assert record["taxMode"] == "incluido"
    assert record["createdAt"] == record["updatedAt"] == 1


def test_alta_guarda_la_tasa_de_iva_personalizada():
    record = transactions.build_transaction(
        workspace="personal",
        date="2026-03-15",
        category_id="cat_1",
        product_name="Harina",
        rate={"value": 40, "date": "2026-03-15", "source": "BCV"},
        bs_amount=100,
        mode="mas_iva",
        iva_rate=0.08,
        timestamp=1,
    )
    assert record["ivaRate"] == 0.08
    assert record["baseImponible"] == 100.0
    assert record["ivaMonto"] == 8.0
    assert record["amountBs"] == 108.0
    assert record["amountUsd"] == 2.7


def test_alta_sin_tasa_iva_explicita_usa_el_16_por_ciento():
    record = transactions.build_transaction(
        workspace="personal",
        date="2026-03-15",
        category_id="cat_1",
        product_name="Harina",
        rate={"value": 40, "date": "2026-03-15", "source": "BCV"},
        bs_amount=116,
        timestamp=1,
    )
    assert record["ivaRate"] == 0.16


def test_alta_guarda_cero_y_vacio_como_null():
    record = transactions.build_transaction(
        workspace="personal",
        date="2026-03-15",
        category_id="cat_1",
        product_name="Harina",
        rate={"value": 36.64, "date": "2026-03-15", "source": "BCV"},
        bs_amount=116,
        quantity="0",
    )
    assert record["quantity"] is None
    assert record["unit"] == ""
    assert record["customValues"] == {}


def test_alta_exige_tasa():
    with pytest.raises(MissingRateError):
        transactions.build_transaction(
            workspace="personal",
            date="2026-03-15",
            category_id="cat_1",
            product_name="Harina",
            rate={"value": 0, "date": "2026-03-15", "source": "BCV"},
            bs_amount=116,
        )


@pytest.mark.parametrize(
    ("category", "date", "name", "bs"),
    [
        ("", "2026-03-15", "Harina", 116),
        ("cat_1", "", "Harina", 116),
        ("cat_1", "2026-03-15", "", 116),
        ("cat_1", "2026-03-15", "Harina", 0),
    ],
)
def test_validacion_de_campos_obligatorios(category, date, name, bs):
    with pytest.raises(ValidationError):
        transactions.validate(category, date, name, bs)


def test_validacion_acepta_el_minimo():
    transactions.validate("cat_1", "2026-03-15", "Harina", 0.01)


def test_producto_existente_se_reutiliza_sin_importar_mayusculas():
    products = [{"id": "PROD-P-A", "name": "Harina PAN"}]
    assert transactions.resolve_product(products, "personal", "harina pan") == (
        "PROD-P-A",
        None,
    )


def test_producto_nuevo_se_crea_con_unidad_por_defecto():
    product_id, created = transactions.resolve_product(
        [],
        "personal",
        "Arroz",
        category_id="cat_1",
        sku_factory=lambda _ws: "PROD-P-NEW",
        timestamp=7,
    )
    assert (product_id, created["name_lower"], created["unit"]) == (
        "PROD-P-NEW",
        "arroz",
        "unidad",
    )
    assert created["createdAt"] == created["updatedAt"] == 7


def test_producto_elegido_a_mano_no_se_crea():
    assert transactions.resolve_product(
        [], "personal", "Arroz", product_id="PROD-P-B"
    ) == ("PROD-P-B", None)


def test_edicion_conserva_lo_que_no_se_toca():
    original = {
        "id": 7,
        "createdAt": 1,
        "categoryId": "cat_1",
        "subcategory": "x",
        "rate": 36.64,
        "amountBs": 100.0,
        "amountUsd": 2.5,
        "unit": "kg",
    }
    updated = transactions.apply_edit(
        original,
        date="2026-04-01",
        product_name="Arroz",
        bs_amount=232,
        usd_amount=232 / 40,
        mode="incluido",
        rate_value=40,
        timestamp=99,
    )
    assert updated["id"] == 7
    assert updated["createdAt"] == 1
    assert updated["categoryId"] == "cat_1"
    assert updated["subcategory"] == "x"
    assert updated["amountBs"] == 232.0
    assert updated["baseImponible"] == 200.0
    assert updated["ivaMonto"] == 32.0
    assert updated["amountUsd"] == 5.8
    assert updated["updatedAt"] == 99
    # Sin tasa nueva se conserva la anterior.
    assert (
        transactions.apply_edit(
            original,
            date="2026-04-01",
            product_name="Arroz",
            bs_amount=1,
            usd_amount=0,
            mode="exento",
            rate_value=0,
        )["rate"]
        == 36.64
    )


def test_la_edicion_puede_cambiar_categoria_y_tasa_iva():
    original = {
        "id": 7,
        "categoryId": "cat_1",
        "rate": 40,
        "amountBs": 116.0,
        "amountUsd": 2.9,
        "ivaRate": 0.16,
    }
    updated = transactions.apply_edit(
        original,
        date="2026-03-15",
        product_name="Harina",
        bs_amount=108,
        usd_amount=108 / 40,
        mode="incluido",
        rate_value=40,
        iva_rate=0.08,
        category_id="cat_2",
    )
    assert updated["categoryId"] == "cat_2"
    assert updated["ivaRate"] == 0.08
    assert updated["baseImponible"] == 100.0
    assert updated["ivaMonto"] == 8.0


def test_el_usd_editado_manda_sobre_el_bs():
    # Difieren en más de un céntimo: se usa el USD.
    assert transactions.resolve_edited_bs(116, 10, 36.64) == pytest.approx(366.4)
    # Coinciden: se respeta lo tecleado.
    assert transactions.resolve_edited_bs(116, 3.1659, 36.64) == 116
    # USD vacío: se respeta el Bs.
    assert transactions.resolve_edited_bs(116, 0, 36.64) == 116


def test_recalculo_del_formulario_respeta_tofixed():
    assert transactions.recalc_bs_usd("bs", "116", "", 36.64)["txAmountUsd"] == "3.1659"
    assert transactions.recalc_bs_usd("usd", "", "10", 36.64)["txAmountBs"] == "366.40"
    assert transactions.recalc_bs_usd("bs", "abc", "", 36.64)["txAmountUsd"] == ""
    assert transactions.recalc_bs_usd("bs", "116", "", 0) == {
        "txAmountBs": None,
        "txAmountUsd": None,
    }
    assert transactions.recalc_bs_usd("otro", "116", "10", 36.64) == {
        "txAmountBs": None,
        "txAmountUsd": None,
    }


def test_recalculo_del_editor_mantiene_el_usd_al_cambiar_la_tasa():
    assert transactions.editor_recalc("rate", "", "10", 40)["txAmountBs"] == "400.00"
    assert transactions.editor_recalc("bs", "116", "", 36.64)["txAmountUsd"] == "3.1659"
    # El editor exige tasa positiva.
    assert transactions.editor_recalc("usd", "", "10", 0) == {
        "txAmountBs": None,
        "txAmountUsd": None,
    }


def test_repetir_compra_cambia_la_fecha_y_vacia_los_montos():
    original = {
        "id": 3,
        "productId": "PROD-P-A",
        "productName": "Harina",
        "categoryId": "cat_1",
        "quantity": 2,
        "unit": "kg",
        "taxMode": "exento",
    }
    clone = transactions.repeat_transaction(original, "2026-10-17", ("unidad", "kg"))
    assert clone["date"] == "2026-10-17"
    assert clone["quantity"] == 2
    assert clone["taxMode"] == "exento"
    assert clone["unitWarning"] is None
    assert "amountBs" not in clone
    assert "amountUsd" not in clone


def test_repetir_compra_avisa_de_unidad_desconocida():
    clone = transactions.repeat_transaction(
        {"id": 1, "productName": "X", "unit": "galón"}, "2026-10-17", ("unidad", "kg")
    )
    assert clone["unitWarning"] == "galón"
    assert clone["unit"] == "unidad"


# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------


def _filtros():
    return [
        {
            "id": 1,
            "productName": "Harina",
            "taxMode": "exento",
            "nature": "Recurrente",
            "date": "2026-03-15",
            "categoryId": "c1",
        },
        {
            "id": 2,
            "productName": "Arroz",
            "taxMode": "incluido",
            "nature": "Extraordinario",
            "date": "2026-03-16",
            "categoryId": "c1",
        },
        {
            "id": 3,
            "productName": "Café",
            "taxMode": "incluido",
            "nature": "Recurrente",
            "date": "2026-04-01",
            "categoryId": "c2",
        },
    ]


def test_filtro_por_naturaleza():
    assert [t["id"] for t in filters.filter_transactions(_filtros(), nature="Recurrente")] == [
        1,
        3,
    ]


def test_filtro_exento_solo_exentos():
    assert [t["id"] for t in filters.filter_transactions(_filtros(), tax="exento")] == [1]


def test_filtro_incluido_significa_con_iva():
    assert [t["id"] for t in filters.filter_transactions(_filtros(), tax="incluido")] == [
        2,
        3,
    ]


def test_filtros_se_combinan():
    assert [
        t["id"]
        for t in filters.filter_transactions(
            _filtros(), nature="Recurrente", tax="incluido"
        )
    ] == [3]


def test_busqueda_ignora_mayusculas_y_acentos_no():
    assert [t["id"] for t in filters.filter_transactions(_filtros(), query="CAF")] == [3]
    assert [t["id"] for t in filters.filter_transactions(_filtros(), query="cafe")] == []


def test_busqueda_por_nombre_de_categoria():
    cats = [{"id": "c2", "name": "Ocio"}]
    assert [
        t["id"]
        for t in filters.filter_transactions(_filtros(), query="ocio", categories=cats)
    ] == [3]


def test_busqueda_por_valores_personalizados():
    txs = [
        {
            "id": 1,
            "productName": "Harina",
            "date": "2026-03-15",
            "customValues": {"presentacion": "1kg"},
        }
    ]
    assert [t["id"] for t in filters.filter_transactions(txs, query="1kg")] == [1]


def test_orden_descendente_por_fecha_y_luego_id():
    ordered = filters.sort_transactions_desc(_filtros())
    assert [t["id"] for t in ordered] == [3, 2, 1]


# ---------------------------------------------------------------------------
# Run-rate
# ---------------------------------------------------------------------------


def test_run_rate_proyecta_el_mes_lineal():
    txs = [
        tx(date="2026-03-01", amountUsd=100, amountBs=4000),
        tx(date="2026-03-10", amountUsd=200, amountBs=8000),
        tx(date="2026-02-28", amountUsd=999, amountBs=36600),  # otro mes
    ]
    rate = runrate.compute_run_rate(
        txs, fiscal_year=2026, now=dt.datetime(2026, 3, 15, 12)
    )
    assert rate.count == 2
    assert rate.accumulated_usd == 300
    assert rate.projected_usd == pytest.approx(300 / 15 * 31)
    assert rate.day_progress == pytest.approx(15 / 31 * 100)
    assert rate.month_key == "2026-03"
    assert rate.audit.is_live_month is True


def test_run_rate_sin_datos_no_divide_por_cero():
    rate = runrate.compute_run_rate(
        [], fiscal_year=2026, now=dt.datetime(2026, 3, 15, 12)
    )
    assert rate.count == 0
    assert rate.projected_usd == 0
    # El corte sigue siendo el día de hoy, así que la barra no se va a cero.
    assert rate.day_progress == pytest.approx(15 / 31 * 100)


def test_run_rate_mira_todo_el_mes_auditado_no_solo_lo_pasado():
    # El original filtra por prefijo de fecha, no por "hoy": un movimiento del
    # día 20 cuenta aunque hoy sea el 15. Un año anterior no cuenta.
    txs = [
        tx(date="2026-03-20", amountUsd=50),
        tx(date="2025-03-10", amountUsd=50),
    ]
    rate = runrate.compute_run_rate(
        txs, fiscal_year=2026, now=dt.datetime(2026, 3, 15, 12)
    )
    assert rate.count == 1
    assert rate.accumulated_usd == 50


def test_run_rate_audita_el_ultimo_mes_con_movimiento():
    # Sin movimientos en el mes del reloj, el parche audita el último mes con
    # datos y corta en su último día con actividad (no en el día de hoy).
    txs = [tx(date="2026-01-20", amountUsd=50)]
    rate = runrate.compute_run_rate(
        txs, fiscal_year=2026, now=dt.datetime(2026, 6, 15, 12)
    )
    assert rate.month_key == "2026-01"
    assert rate.current_day == 20
    assert rate.audit.is_live_month is False
    assert rate.projected_usd == pytest.approx(50 / 20 * 31)


def test_vista_run_rate_usa_el_simbolo_de_la_moneda_activa():
    txs = [tx(date="2026-03-01", amountUsd=100, amountBs=3664)]
    now = dt.datetime(2026, 3, 15, 12)
    vista_usd = runrate.run_rate_view(txs, fiscal_year=2026, now=now, ctx=CTX_USD)
    vista_ves = runrate.run_rate_view(txs, fiscal_year=2026, now=now, ctx=CTX_VES)
    assert vista_usd["runRateProj"] == "$ 206.67"
    assert vista_ves["runRateProj"] == "Bs. 7.572,27"
    assert vista_usd["runRateSub"] == "Período 2026-03 · Acumulado: $ 100.00 (1 movs)"
    assert vista_usd["runRateDay"] == "Corte día 15 de 31 (2026-03)"
    assert vista_usd["runRateBar"] == "48.4%"


def test_vista_run_rate_sin_datos():
    view = runrate.run_rate_view(
        [], fiscal_year=2026, now=dt.datetime(2026, 3, 15, 12), ctx=CTX_USD
    )
    assert view["runRateSub"] == "Sin datos en 2026-03"
    assert view["runRateProj"] == "$ 0.00"
    assert view["runRatePacePct"] == "Media: $ 0.00/día"


# ---------------------------------------------------------------------------
# Punto de equilibrio
# ---------------------------------------------------------------------------


def test_equilibrio_separa_fijo_de_variable():
    txs = [
        tx(date="2026-03-02", nature="Recurrente", amountUsd=100, amountBs=4000),
        tx(date="2026-03-03", nature="Recurrente", amountUsd=100, amountBs=4000),
        tx(date="2026-03-20", nature="Extraordinario", amountUsd=50, amountBs=2000),
        tx(date="2026-02-20", nature="Recurrente", amountUsd=500, amountBs=1),
    ]
    be = breakeven.compute_break_even(
        txs, fiscal_year=2026, now=dt.datetime(2026, 3, 15, 12)
    )
    assert be.fixed_usd == 200
    assert be.variable_usd == 50
    assert be.total_usd == 250
    assert be.fixed_pct == pytest.approx(80)
    assert be.variable_pct == pytest.approx(20)


def test_equilibrio_sin_gastos():
    be = breakeven.compute_break_even(
        [], fiscal_year=2026, now=dt.datetime(2026, 3, 15, 12)
    )
    assert be.total_usd == 0
    # Sin datos las barras quedan al 50 % (mitad y mitad).
    assert (be.fixed_pct, be.variable_pct) == (50.0, 50.0)


def test_vista_equilibrio_redondea_el_porcentaje():
    txs = [
        tx(date="2026-05-01", nature="Recurrente", amountUsd=1000, amountBs=36640),
        tx(date="2026-05-02", nature="Extraordinario", amountUsd=2000, amountBs=73280),
    ]
    view = breakeven.break_even_view(
        txs, fiscal_year=2026, now=dt.datetime(2026, 5, 10, 12), ctx=CTX_USD
    )
    assert view["breakEvenSub"] == "Período 2026-05 · 33.3% Fijo vs 66.7% Variable"
    assert view["beFixedBar"] == "33.3%"
    assert view["beVarBar"] == "66.7%"
    assert view["beFixedVal"] == "$ 1,000.00"
    assert view["beVarVal"] == "$ 2,000.00"


# ---------------------------------------------------------------------------
# Recurrentes
# ---------------------------------------------------------------------------


def _compras(dates, **overrides):
    base = {
        "productId": "P1",
        "productName": "Netflix",
        "nature": "Recurrente",
        "amountUsd": 10,
        "amountBs": 366.4,
    }
    base.update(overrides)
    return [dict(base, date=date) for date in dates]


def test_recurrente_pendiente_y_vencido():
    txs = _compras(["2026-01-05", "2026-02-04", "2026-03-06"])
    pending = recurring.find_recurring_commitments(
        txs, fiscal_year=2026, now=dt.datetime(2026, 4, 10, 12, 0)
    )
    assert len(pending) == 1
    assert pending[0].projected_date == "2026-04-05"
    assert pending[0].last_date == "2026-03-06"
    assert pending[0].avg_interval == 30
    assert pending[0].overdue is True


def test_recurrente_proximo_no_vencido():
    txs = _compras(["2026-01-05", "2026-02-04", "2026-03-06"])
    pending = recurring.find_recurring_commitments(
        txs, fiscal_year=2026, now=dt.datetime(2026, 4, 3, 8, 0)
    )
    assert pending[0].overdue is False


def test_recurrente_necesita_al_menos_dos_compras():
    txs = _compras(["2026-01-05"])
    assert (
        recurring.find_recurring_commitments(
            txs, fiscal_year=2026, now=dt.datetime(2026, 3, 20, 12, 0)
        )
        == []
    )


def test_recurrente_bastan_dos_compras():
    # El parche baja el mínimo de tres compras a dos.
    txs = _compras(["2026-02-04", "2026-03-06"])
    pending = recurring.find_recurring_commitments(
        txs, fiscal_year=2026, now=dt.datetime(2026, 4, 3, 12, 0)
    )
    assert len(pending) == 1
    assert pending[0].avg_interval == 30


def test_recurrente_con_intervalo_cero_se_descarta():
    txs = _compras(["2026-01-05", "2026-01-05", "2026-01-05"])
    assert (
        recurring.find_recurring_commitments(
            txs, fiscal_year=2026, now=dt.datetime(2026, 3, 20, 12, 0)
        )
        == []
    )


def test_recurrente_a_menos_de_35_dias_avisa():
    # Ya no importa si se compró este mes: lo que decide es que la próxima
    # compra esperada no quede a más de 35 días.
    txs = _compras(["2025-12-20", "2026-02-03", "2026-03-20"])
    pending = recurring.find_recurring_commitments(
        txs, fiscal_year=2026, now=dt.datetime(2026, 4, 1, 12, 0)
    )
    assert len(pending) == 1
    assert pending[0].projected_date == "2026-05-04"


def test_recurrente_lejano_se_descarta():
    # A más de 35 días *y* después del cierre del mes auditado, no se avisa.
    txs = _compras(["2026-04-01", "2026-04-20"])
    assert (
        recurring.find_recurring_commitments(
            txs, fiscal_year=2026, now=dt.datetime(2026, 3, 10, 12, 0)
        )
        == []
    )


def test_recurrente_sin_id_se_agrupa_por_nombre():
    # El parche agrupa por ``productId || productName``.
    txs = _compras(["2026-02-04", "2026-03-06"], productId="")
    pending = recurring.find_recurring_commitments(
        txs, fiscal_year=2026, now=dt.datetime(2026, 4, 3, 12, 0)
    )
    assert len(pending) == 1
    assert pending[0].name == "Netflix"


def test_recurrente_con_intervalo_fraccionario_redondea():
    txs = _compras(["2026-01-01", "2026-01-31", "2026-03-01"])
    pending = recurring.find_recurring_commitments(
        txs, fiscal_year=2026, now=dt.datetime(2026, 4, 1, 12, 0)
    )
    assert pending[0].avg_interval == 30
    assert pending[0].projected_date == "2026-03-31"


def test_recurrente_sin_nombre_usa_el_sku():
    txs = _compras(["2025-12-06", "2026-01-05", "2026-02-04"], productName="")
    pending = recurring.find_recurring_commitments(
        txs, fiscal_year=2026, now=dt.datetime(2026, 3, 10, 12, 0)
    )
    assert pending[0].name == "P1"


def test_recurrentes_se_ordenan_por_fecha_esperada():
    txs = _compras(["2025-12-20", "2026-01-20", "2026-02-20"], productId="P2")
    txs += _compras(["2025-12-06", "2026-01-05", "2026-02-04"], productId="P1")
    pending = recurring.find_recurring_commitments(
        txs, fiscal_year=2026, now=dt.datetime(2026, 3, 10, 12, 0)
    )
    assert [p.product_id for p in pending] == ["P1", "P2"]


def test_chip_de_recurrentes():
    def c(overdue: bool) -> recurring.RecurringCommitment:
        return recurring.RecurringCommitment(
            "p", "X", "2026-03-20", 1.0, 40.0, 30, overdue, "2026-02-18"
        )

    assert recurring.recurring_chip([]) == ("0 detectados", "chip ok")
    assert recurring.recurring_chip([c(False)]) == ("1 detectado", "chip warn")
    assert recurring.recurring_chip([c(False), c(False)]) == (
        "2 detectados",
        "chip warn",
    )
    assert recurring.recurring_chip([c(True)]) == ("1 detectado", "chip bad")


def test_vista_de_recurrentes_suma_lo_esperado():
    commitments = [
        recurring.RecurringCommitment("p1", "A", "2026-03-20", 10.0, 400.0, 30, False, "2026-02-18"),
        recurring.RecurringCommitment("p2", "B", "2026-03-25", 5.5, 220.0, 15, False, "2026-03-10"),
    ]
    view = recurring.recurring_view(commitments, CTX_USD)
    assert view["recurringChip"] == "2 detectados"
    assert view["recurringChipClass"] == "chip warn"
    assert view["recurringCommitted"] == "$ 15.50"


# ---------------------------------------------------------------------------
# Alerta de sobreprecio
# ---------------------------------------------------------------------------


def _hist(*unit_prices, quantity=2):
    """Histórico con esos precios unitarios en USD (amountUsd = precio × qty)."""
    return [
        {
            "date": f"2026-0{index + 1}-10",
            "quantity": quantity,
            "amountUsd": price * quantity,
        }
        for index, price in enumerate(unit_prices)
    ]


def test_alerta_avisa_con_una_sola_compra_previa():
    # El parche quita el mínimo de dos compras previas.
    alert = prices.compute_price_alert(_hist(2.5), 3.0)
    assert alert is not None
    assert alert.level == prices.LEVEL_BAD  # +20 % sobre la única referencia
    assert alert.history_count == 1


def test_alerta_dentro_del_rango():
    alert = prices.compute_price_alert(_hist(2.5, 3.5), 2.4)
    assert alert.level == prices.LEVEL_OK
    assert alert.pct == pytest.approx(-20.0)


def test_alerta_aviso_por_encima_del_promedio():
    alert = prices.compute_price_alert(_hist(2.5, 3.5), 3.3)
    assert alert.level == prices.LEVEL_WARN
    assert alert.avg == pytest.approx(3.0)


def test_alerta_umbral_amarillo_es_dos_por_ciento():
    # Hasta +2 % todavía es verde; por encima ya avisa.
    assert prices.compute_price_alert(_hist(2.5, 3.5), 3.05).level == prices.LEVEL_OK
    assert prices.compute_price_alert(_hist(2.5, 3.5), 3.1).level == prices.LEVEL_WARN


def test_alerta_sobreprecio_por_encima_del_15_por_ciento():
    alert = prices.compute_price_alert(_hist(2.5, 3.5), 4.5)
    assert alert.level == prices.LEVEL_BAD
    assert alert.pct_label == "+50.0%"


def test_alerta_sin_ningun_precio_unitario_positivo():
    history = [
        {"date": "2026-01-10", "quantity": 2, "amountUsd": 0},
        {"date": "2026-02-10", "quantity": 2, "amountUsd": 0},
    ]
    assert prices.compute_price_alert(history, 3.0) is None


def test_alerta_descarta_precios_no_positivos_pero_sigue_si_queda_alguno():
    history = [
        {"date": "2026-01-10", "quantity": 2, "amountUsd": 0},
        {"date": "2026-02-10", "quantity": 2, "amountUsd": 5},
    ]
    alert = prices.compute_price_alert(history, 3.0)
    assert alert is not None
    assert alert.avg == pytest.approx(2.5)


def test_alerta_localiza_el_precio_mas_bajo():
    history = [
        {"date": "2026-01-10", "quantity": 2, "amountUsd": 7, "provider": "Bodega"},
        {"date": "2026-02-10", "quantity": 2, "amountUsd": 5, "provider": "Mercado"},
    ]
    alert = prices.compute_price_alert(history, 3.0, "kg")
    assert alert.lowest_value == 2.5
    assert alert.low_where == "Mercado · 2026-02-10"


def test_alerta_sin_comercio():
    history = [
        {"date": "2026-01-10", "quantity": 2, "amountUsd": 5},
        {"date": "2026-02-10", "quantity": 2, "amountUsd": 7},
    ]
    # El guion es el marcador del original (``low.tx.provider || '—'``).
    assert prices.compute_price_alert(history, 3.0).low_where == "— · 2026-01-10"


def test_alerta_resuelve_el_producto_por_nombre():
    products = [{"id": "P1", "name_lower": "café molido"}]
    assert prices.resolve_product_id("", "  Café Molido ", products) == "P1"
    assert prices.resolve_product_id("P9", "café molido", products) == "P9"
    assert prices.resolve_product_id("", "otro", products) == ""


def test_alerta_unitaria_con_modalidad_mas_iva():
    # El total se multiplica por 1 + IVA antes de comparar contra el histórico.
    history = [{"date": "2026-01-10", "quantity": 1, "amountUsd": 4}]
    incluido = prices.price_alert_for_form(
        product_id="P1", history=history, quantity="1", bs_amount="400", rate_value=100
    )
    mas_iva = prices.price_alert_for_form(
        product_id="P1",
        history=history,
        quantity="1",
        bs_amount="400",
        rate_value=100,
        vat_mode="mas_iva",
    )
    assert incluido.current_unit_usd == pytest.approx(4.0)
    assert mas_iva.current_unit_usd == pytest.approx(4.64)


@pytest.mark.parametrize(
    ("pid", "quantity", "bs", "rate"),
    [
        ("", "2", "220", 36.64),
        ("P1", "2", "", 36.64),
        ("P1", "2", "220", 0),
    ],
)
def test_alerta_no_se_muestra_sin_datos(pid, quantity, bs, rate):
    history = [
        {"date": "2026-01-10", "quantity": 2, "amountUsd": 5},
        {"date": "2026-02-10", "quantity": 2, "amountUsd": 7},
    ]
    assert (
        prices.price_alert_for_form(
            product_id=pid,
            history=history,
            quantity=quantity,
            bs_amount=bs,
            rate_value=rate,
        )
        is None
    )


def test_alerta_cantidad_por_defecto_es_uno():
    # Ya no se oculta el aviso cuando la cantidad falta o es <= 0: se usa 1.
    history = [{"date": "2026-01-10", "quantity": 2, "amountUsd": 10}]
    sin_cantidad = prices.price_alert_for_form(
        product_id="P1", history=history, quantity="", bs_amount="220", rate_value=36.64
    )
    con_cero = prices.price_alert_for_form(
        product_id="P1", history=history, quantity="0", bs_amount="220", rate_value=36.64
    )
    assert sin_cantidad is not None
    assert sin_cantidad.current_unit_usd == pytest.approx(220 / 36.64)
    assert con_cero.current_unit_usd == pytest.approx(220 / 36.64)


def test_alerta_unidad_por_defecto():
    history = [
        {"date": "2026-01-10", "quantity": 2, "amountUsd": 5},
        {"date": "2026-02-10", "quantity": 2, "amountUsd": 7},
    ]
    alert = prices.price_alert_for_form(
        product_id="P1",
        history=history,
        quantity="2",
        bs_amount="220",
        rate_value=36.64,
    )
    assert alert.unit == "unidad"
    assert prices.price_alert_view(alert)["unit"] == "unidad"


# ---------------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------------


def test_dias_del_mes_incluye_bisiesto():
    assert dates.days_in_month(2026, 2) == 28
    assert dates.days_in_month(2024, 2) == 29
    assert dates.days_in_month(2026, 12) == 31


def test_mismo_mes():
    ref = dt.date(2026, 3, 15)
    assert dates.same_month("2026-03-01", ref) is True
    assert dates.same_month("2026-02-28", ref) is False
    assert dates.same_month("", ref) is False


def test_fecha_local_a_medianoche_no_desplaza_el_dia():
    # El original construye ``new Date('2026-03-15T00:00:00')`` (local).
    ms = dates.local_midnight_ms("2026-03-15")
    assert dates.local_date_at(ms) == dt.date(2026, 3, 15)


def test_parseo_de_fechas_invalidas():
    assert dates.parse_iso_date("no-es-fecha") is None
    assert dates.parse_local_date("no-es-fecha") is None
    assert dates.parse_iso_date("2026-03-15") == dt.date(2026, 3, 15)


# ---------------------------------------------------------------------------
# Coherencia entre el dominio y las primitivas de formato
# ---------------------------------------------------------------------------


def test_tofixed_cuatro_decimales_del_alta_coincide_con_el_recalculo():
    record = transactions.build_transaction(
        workspace="personal",
        date="2026-03-15",
        category_id="cat_1",
        product_name="Harina",
        rate={"value": 36.64, "date": "2026-03-15", "source": "BCV"},
        bs_amount=116,
        timestamp=1,
    )
    assert float(transactions.recalc_bs_usd("bs", "116", "", 36.64)["txAmountUsd"]) == record[
        "amountUsd"
    ]


def test_parse_float_de_python_es_el_de_v8():
    assert js_parse_float("2.5 kg") == 2.5
    assert math.isnan(js_parse_float("kg"))
    assert js_to_fixed(1 / 3, 4) == "0.3333"
    assert js_round(2.5, 0) == 3
