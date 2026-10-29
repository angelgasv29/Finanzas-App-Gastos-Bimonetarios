"""Coincidencias aproximadas para reutilizar valores existentes.

El autocompletado no puede depender de que el usuario escriba exactamente el
mismo nombre: en la práctica hay tildes, mayúsculas, puntuación y erratas. Estas
funciones normalizan el texto y puntúan qué tan parecido es a los valores que ya
viven en el catálogo o en el histórico.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Iterable

__all__ = ["best_match", "normalize_text", "similar_values", "similarity"]

_SPACES_RE = re.compile(r"\s+")
_INNER_DOT_RE = re.compile(r"(?<=\w)\.(?=\w)")
_NON_WORD_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_text(value: Any) -> str:
    """Minúsculas, sin tildes, sin puntuación y con espacios simples.

    >>> normalize_text("  Central  Madeirense, C.A. ")
    'central madeirense ca'
    >>> normalize_text("Café")
    'cafe'
    """
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.casefold()
    # «C.A.» y «P.A.N.» se leen como «ca» y «pan», no como letras sueltas.
    text = _INNER_DOT_RE.sub("", text)
    text = _NON_WORD_RE.sub(" ", text)
    return _SPACES_RE.sub(" ", text).strip()


def similarity(left: Any, right: Any) -> float:
    """Puntaje entre 0 y 1; 1 significa el mismo texto normalizado.

    >>> similarity("Central Madeirenze", "Central Madeirense") > 0.9
    True
    >>> similarity("Café", "cafe")
    1.0
    >>> similarity("", "Café")
    0.0
    """
    first = normalize_text(left)
    second = normalize_text(right)
    if not first or not second:
        return 0.0
    if first == second:
        return 1.0
    return SequenceMatcher(None, first, second).ratio()


def similar_values(
    query: Any,
    values: Iterable[Any],
    *,
    limit: int = 4,
    cutoff: float = 0.65,
    require_same_tokens: bool = False,
) -> list[tuple[str, float, int]]:
    """Valores parecidos, ordenados por puntaje y luego por frecuencia.

    Devuelve ``(valor, puntaje, veces)``. Se conserva la forma más frecuente de
    cada variante normalizada para no repetir «Café» y «cafe» como si fueran
    productos distintos.

    >>> valores = ["Central Madeirense", "Central Madeirense", "Otro"]
    >>> similar_values("central madeirense", valores)[0][0]
    'Central Madeirense'
    >>> similar_values("Central Madeirenze", valores)[0][0]
    'Central Madeirense'
    >>> similar_values("Central Madeirenze 2", valores, require_same_tokens=True)
    []
    """
    wanted = normalize_text(query)
    if not wanted:
        return []

    counts = Counter(
        str(value).strip()
        for value in values
        if str(value or "").strip()
    )
    best: dict[str, tuple[str, float, int]] = {}
    for value, count in counts.items():
        normalized = normalize_text(value)
        if not normalized:
            continue
        if require_same_tokens and len(wanted.split()) != len(normalized.split()):
            continue
        score = similarity(wanted, value)
        if score < cutoff:
            continue
        previous = best.get(normalized)
        if previous is None or count > previous[2]:
            best[normalized] = (value, score, count)

    ranked = sorted(
        best.values(),
        key=lambda item: (-item[1], -item[2], normalize_text(item[0])),
    )
    return ranked[:limit]


def best_match(
    query: Any,
    values: Iterable[Any],
    *,
    cutoff: float = 0.88,
) -> str | None:
    """El valor existente más parecido, si supera el umbral.

    Exige el mismo número de palabras para no confundir una variante comercial
    («Central Madeirense 2») con una errata de la original.
    """
    matches = similar_values(
        query,
        values,
        limit=1,
        cutoff=cutoff,
        require_same_tokens=True,
    )
    return matches[0][0] if matches else None
