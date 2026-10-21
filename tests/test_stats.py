"""Pruebas de la estadística descriptiva y la regresión."""

from __future__ import annotations

import pytest

from app.core.stats import cagr, linear_regression, mean, median, stdev, unit_price


class TestMedian:
    def test_lista_vacia(self) -> None:
        assert median([]) == 0

    def test_longitud_impar(self) -> None:
        assert median([3, 1, 2]) == 2
        assert median([5]) == 5
        assert median([10, 20, 30, 40, 50]) == 30

    def test_longitud_par(self) -> None:
        assert median([1, 2, 3, 4]) == 2.5
        assert median([1.5, 2.25, 3.125]) == 2.25

    def test_ordena_activamente(self) -> None:
        # La versión de referencia ordena con sort(); no asume entrada ordenada.
        assert median([9, 1, 5, 3, 7]) == 5

    def test_negativos_y_repetidos(self) -> None:
        assert median([-5, 5]) == 0
        assert median([7, 7, 7, 7]) == 7


class TestMean:
    def test_lista_vacia(self) -> None:
        assert mean([]) == 0

    def test_basico(self) -> None:
        assert mean([1, 2, 3]) == 2.0
        assert mean([5]) == 5
        assert mean([-1, 1]) == 0

    def test_suma_secuencial(self) -> None:
        # Se replica el orden de reduce() para igualar el error de coma flotante.
        assert mean([0.1, 0.2, 0.3]) == (0.1 + 0.2 + 0.3) / 3


class TestStdev:
    def test_menos_de_dos_elementos(self) -> None:
        assert stdev([]) == 0
        assert stdev([5]) == 0

    def test_es_muestral(self) -> None:
        # Divide entre (n-1), no entre n. (Verificado contra la referencia.)
        assert stdev([2, 4, 4, 4, 5, 5, 7, 9]) == pytest.approx(
            2.138089935299395, rel=1e-9
        )

    def test_todos_iguales(self) -> None:
        assert stdev([0, 0, 0]) == 0

    def test_valores_repetidos_del_verificacion(self) -> None:
        assert stdev([10, 12, 23, 23, 16, 23, 21, 16]) == pytest.approx(
            5.237229365663817, rel=1e-9
        )


class TestLinearRegression:
    def test_recta_perfecta(self) -> None:
        result = linear_regression([0, 1, 2, 3], [1, 3, 5, 7])
        assert result["b"] == 2.0
        assert result["a"] == 1.0
        assert result["r2"] == 1.0

    def test_menos_de_dos_puntos(self) -> None:
        assert linear_regression([1], [5]) == {"a": 5, "b": 0, "r2": 0}
        assert linear_regression([], []) == {"a": 0, "b": 0, "r2": 0}

    def test_x_constante_no_divide_entre_cero(self) -> None:
        result = linear_regression([1, 1, 1], [1, 2, 3])
        assert result["b"] == 0

    def test_valores_de_ejemplo(self) -> None:
        result = linear_regression([1, 2, 3, 4, 5], [2, 4, 5, 4, 5])
        assert result["b"] == pytest.approx(0.6, rel=1e-9)
        assert result["a"] == pytest.approx(2.2, rel=1e-9)
        assert result["r2"] == pytest.approx(0.6, rel=1e-9)


class TestCagr:
    def test_crecimiento_de_un_ano(self) -> None:
        assert cagr(100, 121, 365) == pytest.approx(21.0, rel=1e-9)

    def test_sin_cambio(self) -> None:
        assert cagr(100, 100, 365) == pytest.approx(0.0, abs=1e-12)

    def test_decrecimiento(self) -> None:
        assert cagr(100, 50, 365) == pytest.approx(-50.0, rel=1e-9)

    @pytest.mark.parametrize(
        ("first", "last", "days"),
        [
            (0, 121, 365),  # valor inicial cero
            (100, 0, 365),  # valor final cero
            (100, 121, 0),  # sin días
            (100, 121, -5),  # días negativos
        ],
    )
    def test_devuelve_cero(self, first: float, last: float, days: float) -> None:
        assert cagr(first, last, days) == 0

    def test_tres_anos(self) -> None:
        assert cagr(1, 2, 1095) == pytest.approx(25.9921049894873, rel=1e-9)


class TestUnitPrice:
    def test_con_cantidad(self) -> None:
        result = unit_price(
            {"quantity": 2, "amountBs": 100, "amountUsd": 20, "unit": "kg"}
        )
        assert result == {"unitBs": 50.0, "unitUsd": 10.0, "qty": 2.0, "unit": "kg"}

    def test_sin_cantidad_usa_uno(self) -> None:
        result = unit_price({"amountBs": 50, "amountUsd": 10})
        assert result == {"unitBs": 50.0, "unitUsd": 10.0, "qty": 1, "unit": "unidad"}

    def test_cantidad_cero_o_negativa(self) -> None:
        result = unit_price({"quantity": 0, "amountBs": 100, "amountUsd": 20})
        assert result["qty"] == 1
        result = unit_price({"quantity": -1, "amountBs": 100, "amountUsd": 20})
        assert result["qty"] == 1

    def test_cantidad_como_cadena(self) -> None:
        result = unit_price(
            {"quantity": "2.5", "amountBs": "250", "amountUsd": "50", "unit": "L"}
        )
        assert result == {"unitBs": 100.0, "unitUsd": 20.0, "qty": 2.5, "unit": "L"}

    def test_unidad_por_defecto(self) -> None:
        assert unit_price({"quantity": 1, "amountBs": 1, "amountUsd": 1})["unit"] == (
            "unidad"
        )
