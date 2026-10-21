"""Pruebas del formato de moneda.

Los casos marcados con **[verificado]** son los que revelaron una diferencia
real entre JavaScript y Python durante la comparación cruzada con la referencia. Son los
más importantes de todo el proyecto: si alguno falla, la aplicación mostrará
importes distintos a la de referencia.
"""

from __future__ import annotations

import math

import pytest

from app.core.money import (
    MoneyContext,
    fmt_money,
    format_bs,
    format_pct,
    format_rate,
    format_usd,
    js_number_guard,
    js_number_or_zero,
    js_round,
    money_symbol,
    money_value,
)


class TestCoerciones:
    """Las dos coercciones de la versión de referencia no son intercambiables."""

    def test_guard_protege_falsy(self) -> None:
        # Number(n||0): el || actúa ANTES de convertir.
        assert js_number_guard(None) == 0.0
        assert js_number_guard("") == 0.0
        assert js_number_guard(0) == 0.0
        assert js_number_guard(False) == 0.0
        assert js_number_guard("12.5") == 12.5

    def test_guard_no_protege_cadena_no_numerica(self) -> None:
        # Number("abc") es NaN y el ||0 ya se aplicó, así que NO protege.
        assert math.isnan(js_number_guard("abc"))

    def test_or_zero_si_protege_cadena_no_numerica(self) -> None:
        # Number(n)||0: el || actúa DESPUÉS, así que NaN cae a 0.
        assert js_number_or_zero("abc") == 0.0
        assert js_number_or_zero(None) == 0.0
        assert js_number_or_zero("12.5") == 12.5


class TestFormatBs:
    def test_basico(self) -> None:
        assert format_bs(1234.5) == "Bs. 1.234,50"
        assert format_bs(0) == "Bs. 0,00"
        assert format_bs(100) == "Bs. 100,00"

    def test_millones(self) -> None:
        assert format_bs(1234567.891) == "Bs. 1.234.567,89"

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (0.015, "Bs. 0,02"),  # [verificado] binario 0.0149999... → toLocale sube
            (2.675, "Bs. 2,68"),  # [verificado] binario 2.6749999... → toLocale sube
            (0.005, "Bs. 0,01"),
            (999.999, "Bs. 1.000,00"),
        ],
    )
    def test_redondeo_toLocaleString(self, value: float, expected: str) -> None:
        """``toLocaleString`` redondea la representación decimal corta."""
        assert format_bs(value) == expected

    def test_negativos(self) -> None:
        assert format_bs(-1234.567) == "Bs. -1.234,57"
        assert format_bs(-0.001) == "Bs. -0,00"

    def test_entrada_no_numerica_produce_nan(self) -> None:
        # Comportamiento de la versión de referencia: Number("abc") es NaN y no está protegido.
        assert format_bs("abc") == "Bs. NaN"
        assert format_bs(None) == "Bs. 0,00"
        assert format_bs(True) == "Bs. 1,00"


class TestFormatUsd:
    def test_basico(self) -> None:
        assert format_usd(1234.5) == "$ 1,234.50"
        assert format_usd(1234.5, 4) == "$ 1,234.5000"
        assert format_usd(0) == "$ 0.00"

    @pytest.mark.parametrize(
        ("value", "dec", "expected"),
        [
            (0.015, 2, "$ 0.02"),  # [verificado]
            (2.675, 2, "$ 2.68"),  # [verificado]
            (40.12345, 4, "$ 40.1235"),  # [verificado]
        ],
    )
    def test_redondeo(self, value: float, dec: int, expected: str) -> None:
        assert format_usd(value, dec) == expected


class TestFormatRate:
    def test_minimo_dos_decimales(self) -> None:
        assert format_rate(40.5) == "40,50"
        assert format_rate(0) == "0,00"

    def test_maximo_cuatro_decimales(self) -> None:
        assert format_rate(40.505) == "40,505"
        assert format_rate(40.12345) == "40,1235"  # [verificado]
        assert format_rate(40.123456) == "40,1235"


class TestFormatPct:
    def test_basico(self) -> None:
        assert format_pct(0) == "0.00%"
        assert format_pct(100) == "100.00%"

    def test_redondeo_toFixed(self) -> None:
        """``toFixed`` redondea el binario exacto, no la representación corta.

        Este es el contraejemplo que distingue las dos estrategias de la versión de referencia:
        ``2.675`` es en binario ``2.6749999999999998...``, así que ``toFixed``
        baja a ``2.67`` mientras que ``toLocaleString`` sube a ``2.68``.
        Comprobado ejecutando la versión de referencia con la referencia.
        """
        assert format_pct(2.675) == "2.67%"
        assert format_bs(2.675) == "Bs. 2,68"  # la otra estrategia, en el mismo valor

    def test_valor_por_encima_del_empate(self) -> None:
        # 12.345 es en binario 12.34500000000000063..., por ENCIMA del empate.
        assert format_pct(12.345) == "12.35%"
        assert format_bs(12.345) == "Bs. 12,35"

    def test_protege_nan(self) -> None:
        # formatPct usa Number(n)||0, así que sí protege.
        assert format_pct("abc") == "0.00%"


class TestJsRound:
    def test_empates_hacia_arriba(self) -> None:
        # Math.round, no el round() bancario de Python. Con decimales enteros
        # hace falta d=0, porque el valor por defecto es 2 igual que en la versión de referencia.
        assert js_round(2.5, 0) == 3.0
        assert js_round(3.5, 0) == 4.0
        assert js_round(-2.5, 0) == -2.0
        assert js_round(0.5, 0) == 1.0

    def test_casos_del_verificacion(self) -> None:
        # Verificados contra la referencia: el producto 2.675*100 da 267.5 exacto.
        assert js_round(2.675) == 2.68
        assert js_round(1234.5) == 1234.5
        assert js_round(0) == 0.0
        assert js_round(2.5) == 2.5  # sin cambios: 2.5 ya tiene 1 decimal

    def test_precision_configurable(self) -> None:
        assert js_round(1.005, 2) == 1.0
        assert js_round(1.2345, 3) == 1.235


class TestFmtMoney:
    def test_vista_usd(self) -> None:
        ctx = MoneyContext("USD", 2, 40.5)
        assert fmt_money(10, 405, ctx) == "$ 10.00"
        assert fmt_money(0, 405, ctx) == "$ 10.00"  # cae a Bs/tasa
        assert fmt_money(0, 0, ctx) == "$ 0.00"

    def test_vista_ves(self) -> None:
        ctx = MoneyContext("VES", 2, 40.5)
        assert fmt_money(10, 405, ctx) == "Bs. 405,00"
        assert fmt_money(10, 0, ctx) == "Bs. 405,00"  # cae a USD*tasa
        assert fmt_money(0, 0, ctx) == "Bs. 0,00"

    def test_override_de_decimales(self) -> None:
        ctx = MoneyContext("USD", 2, None)
        assert fmt_money(10, 0, ctx, 4) == "$ 10.0000"

    def test_sin_tasa_no_rompe(self) -> None:
        ctx = MoneyContext("VES", 2, None)
        assert fmt_money(10, 0, ctx) == "Bs. 0,00"


class TestMoneyValueYSymbol:
    def test_symbol(self) -> None:
        assert money_symbol(MoneyContext("VES")) == "Bs"
        assert money_symbol(MoneyContext("USD")) == "USD"

    def test_value(self) -> None:
        assert money_value(10, 405, MoneyContext("VES")) == 405.0
        assert money_value(10, 405, MoneyContext("USD")) == 10.0
        assert money_value(None, None, MoneyContext("USD")) == 0.0
