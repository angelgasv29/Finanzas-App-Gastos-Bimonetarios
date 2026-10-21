"""Pruebas de generación de identificadores (``app/core/ids.py``)."""

from __future__ import annotations

import re
import time

import pytest

from app.core.ids import BASE36_ALPHABET, _fraction_base36, _int_base36, new_sku, now_ms, uid

BASE36 = re.compile(r"^[0-9a-z]+$")


def test_now_ms_es_entero_en_milisegundos() -> None:
    value = now_ms()
    assert isinstance(value, int)
    # Margen amplio: solo se comprueba que es "ahora", no un reloj distinto.
    assert abs(value - int(time.time() * 1000)) < 5_000


@pytest.mark.parametrize("value", [0.1, 0.5, 0.999999, 0.0])
def test_fraccion_base36_longitud_y_alfabeto(value: float) -> None:
    digits = _fraction_base36(value, 8)
    assert len(digits) == 8
    assert BASE36.match(digits)


def test_int_base36_bordes() -> None:
    assert _int_base36(0) == "0"
    assert _int_base36(-5) == "0"  # no hay negativos válidos
    assert _int_base36(35) == "z"
    assert _int_base36(36) == "10"
    assert _int_base36(1295) == "zz"
    assert set(_int_base36(123456789)) <= set(BASE36_ALPHABET)


def test_uid_estructura() -> None:
    value = uid("cat", rng=lambda: 0.5)
    assert value.startswith("cat_")
    # 8 caracteres aleatorios + hasta 4 del reloj.
    assert len(value) == 16
    assert BASE36.match(value[4:])


def test_uid_sin_prefijo_por_defecto() -> None:
    assert uid(rng=lambda: 0.5).startswith("id_")


def test_uid_determinista_con_rng_inyectado() -> None:
    clock = lambda: 1_773_577_845_000  # noqa: E731 - reloj fijo para la prueba
    assert uid("cf", rng=lambda: 0.5, clock=clock) == uid(
        "cf", rng=lambda: 0.5, clock=clock
    )


def test_uid_dos_aleatorios_distintos() -> None:
    sequence = iter([0.1, 0.9])
    first = uid("cat", rng=lambda: next(sequence))
    second = uid("cat", rng=lambda: next(sequence))
    assert first != second


@pytest.mark.parametrize("workspace,prefix", [("personal", "PROD-P-"), ("profesional", "PROD-W-")])
def test_new_sku_prefijo_por_entorno(workspace: str, prefix: str) -> None:
    sku = new_sku(workspace, rng=lambda: 0.5)
    assert sku.startswith(prefix)
    assert len(sku) == 15
    assert sku.isupper()
    assert BASE36.match(sku[len(prefix) :].lower())


def test_new_sku_entorno_desconocido_usa_profesional() -> None:
    # Cualquier valor distinto de 'personal' usa el prefijo profesional.
    assert new_sku("otro", rng=lambda: 0.5).startswith("PROD-W-")
