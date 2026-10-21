"""Pruebas del estado de la interfaz (sin NiceGUI)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ui.state import open_state


@pytest.fixture()
def state(tmp_path: Path):
    app_state = open_state(tmp_path / "app.sqlite3")
    yield app_state
    app_state.close()


def test_notify_repinta_todos_los_oyentes(state) -> None:
    calls: list[str] = []
    state.subscribe(lambda: calls.append("a"))
    state.subscribe(lambda: calls.append("b"))

    state.notify()

    assert calls == ["a", "b"]


def test_unsubscribe_quita_el_oyente(state) -> None:
    calls: list[int] = []
    unsubscribe = state.subscribe(lambda: calls.append(1))
    state.notify()
    unsubscribe()
    state.notify()

    assert calls == [1]


def test_un_oyente_roto_no_detiene_a_los_demas(state) -> None:
    calls: list[str] = []

    def broken() -> None:
        raise ValueError("panel roto")

    state.subscribe(broken)
    state.subscribe(lambda: calls.append("sigue"))

    state.notify()

    assert calls == ["sigue"]


def test_un_slot_cerrado_se_descarta(state) -> None:
    calls: list[str] = []

    def closed_tab() -> None:
        raise RuntimeError("slot cerrado")

    state.subscribe(closed_tab)
    state.subscribe(lambda: calls.append("vivo"))

    state.notify()
    state.notify()

    assert calls == ["vivo", "vivo"]
    assert len(state._listeners) == 1


def test_cambiar_entorno_recarga_categorias(state) -> None:
    assert {cat["workspace"] for cat in state.categories} == {"personal"}

    state.set_workspace("profesional")

    assert state.workspace == "profesional"
    assert state.categories
    assert {cat["workspace"] for cat in state.categories} == {"profesional"}


def test_la_tasa_manual_manda_sobre_la_del_bcv(state) -> None:
    """La versión de referencia fija la tasa manual como «de sesión» hasta sincronizar."""
    state.repo.put(
        "rates", {"date": "2026-01-01", "value": 40.0, "source": "BCV", "ts": 0}
    )
    state.refresh()
    assert state.rate_value == 40.0

    state.lock_session_rate(150.0, "2025-12-31")
    assert state.rate_value == 150.0
    assert state.session_rate is not None

    state.clear_session_rate()
    assert state.rate_value == 40.0
    assert state.session_rate is None


def test_la_tasa_de_sesion_sobrevive_a_reabrir(tmp_path: Path) -> None:
    """``gb_session_rate``: la tasa manual se restaura al arrancar."""
    path = tmp_path / "app.sqlite3"

    first = open_state(path)
    first.repo.put(
        "rates", {"date": "2026-01-01", "value": 40.0, "source": "BCV", "ts": 0}
    )
    first.lock_session_rate(150.0, "2025-12-31")
    first.close()

    second = open_state(path)
    try:
        assert second.session_rate == {
            "value": 150.0,
            "date": "2025-12-31",
            "source": "Manual",
        }
        assert second.rate_value == 150.0
        second.clear_session_rate()
    finally:
        second.close()

    third = open_state(path)
    try:
        assert third.session_rate is None
        assert third.rate_value == 40.0
    finally:
        third.close()


def test_cada_pestana_tiene_su_propio_estado(tmp_path: Path) -> None:
    """Dos pestañas no comparten configuración en memoria (el ``APP`` de la versión de referencia)."""
    path = tmp_path / "app.sqlite3"
    first = open_state(path)
    second = open_state(path)

    first.set_fiscal_year(2020)
    first.set_workspace("profesional")

    assert second.fiscal_year != 2020
    assert second.workspace == "personal"

    # Las preferencias sí se persisten: una pestaña nueva arranca con lo último.
    third = open_state(path)
    assert third.fiscal_year == 2020
    assert third.workspace == "profesional"

    for app_state in (first, second, third):
        app_state.close()


def test_cerrar_una_pestana_no_afecta_a_la_otra(tmp_path: Path) -> None:
    path = tmp_path / "app.sqlite3"
    first = open_state(path)
    second = open_state(path)

    first.close()

    second.set_fiscal_year(2019)
    assert second.fiscal_year == 2019
    assert second.repo.count("categories") > 0
    second.close()
