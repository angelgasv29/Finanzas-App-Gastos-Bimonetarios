"""Pruebas de las coincidencias aproximadas del autocompletado."""

from __future__ import annotations

from app.core.suggestions import best_match, normalize_text, similar_values


def test_normaliza_tildes_puntuacion_y_espacios() -> None:
    assert normalize_text("  Central  Madeirense, C.A. ") == "central madeirense ca"
    assert normalize_text("Café") == "cafe"


def test_una_errata_sugiere_el_valor_existente() -> None:
    values = ["Central Madeirense", "Central Madeirense", "Otro"]
    first = similar_values("Central Madeirenze", values, limit=1)[0]
    assert first[0] == "Central Madeirense"
    assert first[1] > 0.9
    assert first[2] == 2


def test_no_confunde_una_variante_con_una_errata() -> None:
    values = ["Central Madeirense"]
    assert best_match("Central Madeirenze", values) == "Central Madeirense"
    assert best_match("Central Madeirense 2", values) is None
