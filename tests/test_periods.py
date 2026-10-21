"""Pruebas de los rangos temporales.

Incluye los casos de desbordamiento de JavaScript, que son contraintuitivos pero
deben reproducirse: en JS, el 31 de marzo menos un mes es el **3 de marzo**,
no el 28 de febrero.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.core.periods import (
    TemporalState,
    date_to_iso,
    filter_by_range,
    format_temporal_label,
    get_temporal_range,
    shift_temporal,
    today_iso,
)


def state(mode: str, ref: str, **kwargs) -> TemporalState:
    return TemporalState(mode=mode, ref_date=datetime.fromisoformat(ref), **kwargs)


class TestDateToIso:
    def test_desde_datetime(self) -> None:
        assert date_to_iso(datetime(2026, 3, 7, 23, 59, 59)) == "2026-03-07"

    def test_desde_cadena(self) -> None:
        assert date_to_iso("2026-03-07T10:00:00") == "2026-03-07"

    def test_hoy(self) -> None:
        assert len(today_iso()) == 10


class TestGetTemporalRange:
    def test_mes(self) -> None:
        start, end = get_temporal_range(state("month", "2026-02-15T12:00:00"))
        assert (date_to_iso(start), date_to_iso(end)) == ("2026-02-01", "2026-02-28")

    def test_mes_febrero_bisiesto(self) -> None:
        start, end = get_temporal_range(state("month", "2024-02-10T12:00:00"))
        assert date_to_iso(end) == "2024-02-29"

    def test_ano(self) -> None:
        start, end = get_temporal_range(state("year", "2026-06-15T12:00:00"))
        assert (date_to_iso(start), date_to_iso(end)) == ("2026-01-01", "2026-12-31")

    def test_semana_empieza_en_lunes(self) -> None:
        # 2026-01-01 es jueves → la semana va del lunes 29/12/2025 al domingo 04/01/2026.
        start, end = get_temporal_range(state("week", "2026-01-01T12:00:00"))
        assert (date_to_iso(start), date_to_iso(end)) == ("2025-12-29", "2026-01-04")

    def test_semana_domingo_pertenece_a_la_anterior(self) -> None:
        # getDay() === 0 (domingo) → offset 6, sigue en la semana del lunes previo.
        start, end = get_temporal_range(state("week", "2026-01-04T12:00:00"))
        assert (date_to_iso(start), date_to_iso(end)) == ("2025-12-29", "2026-01-04")

    @pytest.mark.parametrize(
        ("ref", "expected_start", "expected_end"),
        [
            ("2026-01-10T12:00:00", "2026-01-01", "2026-02-28"),  # bimestre 1
            ("2026-03-10T12:00:00", "2026-03-01", "2026-04-30"),  # bimestre 2
            ("2026-11-10T12:00:00", "2026-11-01", "2026-12-31"),  # bimestre 6
        ],
    )
    def test_bimestre(self, ref: str, expected_start: str, expected_end: str) -> None:
        start, end = get_temporal_range(state("bimester", ref))
        assert (date_to_iso(start), date_to_iso(end)) == (expected_start, expected_end)

    @pytest.mark.parametrize(
        ("ref", "expected_start", "expected_end"),
        [
            ("2026-01-15T12:00:00", "2026-01-01", "2026-03-31"),
            ("2026-05-15T12:00:00", "2026-04-01", "2026-06-30"),
            ("2026-12-15T12:00:00", "2026-10-01", "2026-12-31"),
        ],
    )
    def test_trimestre(self, ref: str, expected_start: str, expected_end: str) -> None:
        start, end = get_temporal_range(state("quarter", ref))
        assert (date_to_iso(start), date_to_iso(end)) == (expected_start, expected_end)

    def test_cuatrimestre_ultimo(self) -> None:
        start, end = get_temporal_range(state("quadrimester", "2026-12-15T12:00:00"))
        assert (date_to_iso(start), date_to_iso(end)) == ("2026-09-01", "2026-12-31")

    @pytest.mark.parametrize(
        ("ref", "expected_start", "expected_end"),
        [
            ("2026-07-01T12:00:00", "2026-07-01", "2026-12-31"),
            ("2026-12-31T12:00:00", "2026-07-01", "2026-12-31"),
        ],
    )
    def test_semestre(self, ref: str, expected_start: str, expected_end: str) -> None:
        start, end = get_temporal_range(state("semester", ref))
        assert (date_to_iso(start), date_to_iso(end)) == (expected_start, expected_end)

    def test_personalizado(self) -> None:
        start, end = get_temporal_range(
            state(
                "custom",
                "2026-06-15T12:00:00",
                custom_start=datetime(2026, 3, 1),
                custom_end=datetime(2026, 4, 15, 23, 59, 59),
            )
        )
        assert (date_to_iso(start), date_to_iso(end)) == ("2026-03-01", "2026-04-15")

    def test_personalizado_sin_fechas_cae_a_mes(self) -> None:
        start, end = get_temporal_range(state("custom", "2026-06-15T12:00:00"))
        assert (date_to_iso(start), date_to_iso(end)) == ("2026-06-01", "2026-06-30")

    def test_fin_del_rango_a_235959(self) -> None:
        _, end = get_temporal_range(state("month", "2026-02-15T12:00:00"))
        assert (end.hour, end.minute, end.second) == (23, 59, 59)


class TestShiftTemporal:
    def test_mes_normal(self) -> None:
        assert date_to_iso(shift_temporal(state("month", "2026-01-15T12:00:00"), 1).ref_date) == (
            "2026-02-15"
        )
        assert date_to_iso(shift_temporal(state("month", "2026-12-15T12:00:00"), 1).ref_date) == (
            "2027-01-15"
        )

    def test_mes_desborda_hacia_adelante(self) -> None:
        # JS: 31 de enero + 1 mes → 31 de febrero → 3 de marzo.
        assert date_to_iso(shift_temporal(state("month", "2026-01-31T12:00:00"), 1).ref_date) == (
            "2026-03-03"
        )

    def test_mes_desborda_hacia_atras(self) -> None:
        # JS: 31 de marzo - 1 mes → 31 de febrero → 3 de marzo.
        assert date_to_iso(shift_temporal(state("month", "2026-03-31T12:00:00"), -1).ref_date) == (
            "2026-03-03"
        )

    def test_semana(self) -> None:
        assert date_to_iso(shift_temporal(state("week", "2026-01-01T12:00:00"), 1).ref_date) == (
            "2026-01-08"
        )
        assert date_to_iso(shift_temporal(state("week", "2026-01-01T12:00:00"), -1).ref_date) == (
            "2025-12-25"
        )

    def test_bimestre(self) -> None:
        # 31 de enero + 2 meses = 31 de marzo: día válido, sin desbordamiento.
        assert date_to_iso(
            shift_temporal(state("bimester", "2026-01-31T12:00:00"), 1).ref_date
        ) == "2026-03-31"

    def test_bimestre_desborda(self) -> None:
        # 31 de diciembre + 2 meses → 31 de febrero → 3 de marzo de 2027.
        assert date_to_iso(
            shift_temporal(state("bimester", "2026-12-31T12:00:00"), 1).ref_date
        ) == "2027-03-03"

    def test_trimestre_desborda(self) -> None:
        # 30 de noviembre + 3 meses → 30 de febrero → 2 de marzo de 2027.
        assert date_to_iso(
            shift_temporal(state("quarter", "2026-11-30T12:00:00"), 1).ref_date
        ) == "2027-03-02"

    def test_ano(self) -> None:
        assert date_to_iso(shift_temporal(state("year", "2026-06-15T12:00:00"), -2).ref_date) == (
            "2024-06-15"
        )

    def test_ano_desde_29_de_febrero(self) -> None:
        # 2024-02-29 + 1 año: 29 de febrero de 2025 no existe → 1 de marzo.
        assert date_to_iso(shift_temporal(state("year", "2024-02-29T12:00:00"), 1).ref_date) == (
            "2025-03-01"
        )

    def test_personalizado_no_cambia(self) -> None:
        base = state("custom", "2026-06-15T12:00:00")
        assert shift_temporal(base, 1).ref_date == base.ref_date

    def test_no_muta_el_estado_previo(self) -> None:
        base = state("month", "2026-01-15T12:00:00")
        shift_temporal(base, 1)
        assert date_to_iso(base.ref_date) == "2026-01-15"


class TestFormatTemporalLabel:
    def test_etiqueta_de_mes(self) -> None:
        assert format_temporal_label(state("month", "2026-03-15T12:00:00")) == (
            "Mes: 2026-03-01 → 2026-03-31"
        )

    def test_etiqueta_de_ano(self) -> None:
        assert format_temporal_label(state("year", "2026-06-15T12:00:00")) == (
            "Año: 2026-01-01 → 2026-12-31"
        )


class TestFilterByRange:
    TXS = [
        {"date": "2026-01-01", "amountUsd": 1},
        {"date": "2026-02-15", "amountUsd": 2},
        {"date": "2026-02-28", "amountUsd": 3},
        {"date": "2026-03-01", "amountUsd": 4},
    ]

    def test_rango_inclusivo(self) -> None:
        start, end = get_temporal_range(state("month", "2026-02-10T12:00:00"))
        result = filter_by_range(self.TXS, start, end)
        assert [t["amountUsd"] for t in result] == [2, 3]

    def test_rango_que_no_cruza(self) -> None:
        start, end = get_temporal_range(state("month", "2025-06-10T12:00:00"))
        assert filter_by_range(self.TXS, start, end) == []

    def test_filtra_por_dia_exacto(self) -> None:
        start = datetime(2026, 3, 1)
        end = datetime(2026, 3, 1, 23, 59, 59)
        assert len(filter_by_range(self.TXS, start, end)) == 1
