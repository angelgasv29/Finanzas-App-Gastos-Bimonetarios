"""Lectura de tickets para el lote OCR.

La versión de referencia usa Tesseract.js y vuelca el texto reconocido en el importador por
lotes. Aquí el reconocimiento lo hace ``rapidocr-onnxruntime`` (sin binarios del
sistema) y este módulo se encarga de la parte **determinista**: convertir el
texto del ticket en filas candidatas (producto, cantidad e importe).

Es una heurística, no un parser de un formato concreto: los tickets venezolanos
mezclan ``1.234,56`` y ``1,234.56``, así que el importe se normaliza por la
posición del último separador. Las filas se pueden corregir en la interfaz antes
de importarlas.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["boxes_to_text", "parse_amount", "parse_receipt_text"]

#: Palabras que delatan una línea de totales o de cabecera, no de producto.
NOISE_WORDS = (
    "total",
    "subtotal",
    "iva",
    "igtf",
    "descuento",
    "cambio",
    "efectivo",
    "tarjeta",
    "debito",
    "credito",
    "pago",
    "vuelto",
    "gracias",
    "factura",
    "rif",
    "cedula",
    "caja",
    "cajero",
    "fecha",
    "hora",
    "cliente",
)

#: ``2 x``, ``2x``, ``3 kg``, ``12 und``… al principio de la línea.
_QUANTITY_PREFIX = re.compile(
    r"^\s*(?P<qty>\d{1,4})\s*(?:[xX×*]|(?:und|unid|un|kg|g|l|ml|pza|pzas|docena)\.?)\s+",
    re.IGNORECASE,
)

#: Números con separadores de miles y/o decimales.
_AMOUNT = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})|\d+(?:[.,]\d{1,2})?)(?![\d.,])")

#: Caracteres de relleno que quedan al quitar el importe.
_TRAILING = " \t.-—–*:×"


def parse_amount(text: Any) -> float | None:
    """Importe normalizado a ``float``, aceptando coma o punto decimal.

    >>> parse_amount("1.234,56"), parse_amount("1,234.56"), parse_amount("890,00")
    (1234.56, 1234.56, 890.0)
    >>> parse_amount("1.234"), parse_amount("12")
    (1234.0, 12.0)
    >>> parse_amount("no") is None
    True
    """
    token = str(text).strip().replace(" ", "")
    if not token:
        return None

    last_dot = token.rfind(".")
    last_comma = token.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        if last_dot > last_comma:
            token = token.replace(",", "")
        else:
            token = token.replace(".", "").replace(",", ".")
    elif last_comma >= 0:
        head, _, tail = token.rpartition(",")
        token = head.replace(",", "") + ("." + tail if len(tail) in (1, 2) else tail)
    elif last_dot >= 0:
        head, _, tail = token.rpartition(".")
        token = head.replace(".", "") + ("." + tail if len(tail) in (1, 2) else tail)

    try:
        return float(token)
    except ValueError:
        return None


def _is_noise(line: str) -> bool:
    lowered = line.lower()
    return any(word in lowered for word in NOISE_WORDS)


_HAS_LETTERS = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]")


def boxes_to_text(items: Any, *, tolerance: float | None = None) -> str:
    """Reconstruye líneas a partir de las cajas que devuelve RapidOCR.

    El motor entrega cada bloque de texto por separado; si el ticket deja mucho
    hueco entre el producto y el importe, llegan en dos cajas distintas. Aquí se
    agrupan por la **coordenada vertical** (misma línea visual) y se ordenan por
    la horizontal, que es lo que espera :func:`parse_receipt_text`.

    >>> cajas = [
    ...   ([[0, 0], [40, 0], [40, 10], [0, 10]], "HARINA PAN", 0.9),
    ...   ([[200, 0], [260, 0], [260, 10], [200, 10]], "1.234,56", 0.9),
    ...   ([[0, 30], [40, 30], [40, 40], [0, 40]], "TOTAL", 0.9),
    ... ]
    >>> print(boxes_to_text(cajas))
    HARINA PAN   1.234,56
    TOTAL
    >>> boxes_to_text([])
    ''
    """
    entries: list[dict[str, Any]] = []
    for item in items or []:
        try:
            box, text = item[0], item[1]
        except (TypeError, IndexError):
            continue
        label = str(text).strip()
        if not label:
            continue
        points = [point for point in (box or []) if len(point) >= 2]
        if points:
            xs = [float(point[0]) for point in points]
            ys = [float(point[1]) for point in points]
        else:
            xs, ys = [0.0], [0.0]
        entries.append(
            {
                "x": min(xs),
                "y": (min(ys) + max(ys)) / 2,
                "h": max(ys) - min(ys),
                "text": label,
            }
        )

    if not entries:
        return ""

    heights = sorted(entry["h"] for entry in entries if entry["h"] > 0)
    median_height = heights[len(heights) // 2] if heights else 10.0
    limit = tolerance if tolerance is not None else max(6.0, median_height * 0.6)

    entries.sort(key=lambda entry: (entry["y"], entry["x"]))
    lines: list[list[dict[str, Any]]] = [[entries[0]]]
    for entry in entries[1:]:
        if abs(entry["y"] - lines[-1][0]["y"]) <= limit:
            lines[-1].append(entry)
        else:
            lines.append([entry])

    rendered: list[str] = []
    for line in lines:
        line.sort(key=lambda entry: entry["x"])
        rendered.append("   ".join(entry["text"] for entry in line))
    return "\n".join(rendered)


def _clean_name(text: str) -> str:
    name = text.strip(_TRAILING)
    name = re.sub(r"\s{2,}", " ", name)
    return name.strip(_TRAILING)


def parse_receipt_text(text: Any) -> list[dict[str, Any]]:
    """Filas candidatas de un ticket (heurística, sin efectos).

    Cada fila trae ``name``, ``quantity``, ``totalBs``, ``unitBs`` y ``raw``.
    Se descartan las líneas sin importe, sin letras o de totales/cabecera.

    >>> ticket = '''EXCELSIOR GAMA, C.A.
    ... RIF: J-00000000-0
    ... HARINA PAN 1KG   1.234,56
    ... 2 x LECHE EN POLVO 900G   890,00
    ... TOTAL   2.124,56
    ... GRACIAS POR SU COMPRA'''
    >>> [(row["name"], row["quantity"], row["totalBs"])
    ...  for row in parse_receipt_text(ticket)]
    [('HARINA PAN 1KG', 1, 1234.56), ('LECHE EN POLVO 900G', 2, 890.0)]
    >>> parse_receipt_text("")
    []
    >>> parse_receipt_text("HARINA PAN 1KG\\n1.234,56")
    [{'name': 'HARINA PAN 1KG', 'quantity': 1, 'totalBs': 1234.56, 'unitBs': 1234.56, 'raw': '1.234,56'}]
    """
    rows: list[dict[str, Any]] = []
    pending = ""
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            pending = ""
            continue
        if _is_noise(line):
            pending = ""
            continue

        matches = list(_AMOUNT.finditer(line))
        last = matches[-1] if matches else None
        tail = line[last.end() :].strip(_TRAILING) if last else ""
        tail_is_currency = tail.lower().strip(".") in {"bs", "ves", "usd", "$", "€"}
        if last is None or (tail and not tail_is_currency):
            # El OCR puede dejar el importe en la línea siguiente. Solo cuenta
            # como precio el número que cierra la línea.
            pending = line if _HAS_LETTERS.search(line) else ""
            continue

        total = parse_amount(last.group(0))
        name_part = line[: last.start()]
        if not _HAS_LETTERS.search(name_part) and pending:
            name_part = pending
        pending = ""

        if not total or total <= 0:
            continue

        quantity = 1
        name_source = name_part
        prefix = _QUANTITY_PREFIX.match(name_source)
        if prefix:
            quantity = int(prefix.group("qty")) or 1
            name_source = name_source[prefix.end() :]

        name = _clean_name(name_source)
        if not name or not _HAS_LETTERS.search(name):
            continue

        rows.append(
            {
                "name": name,
                "quantity": quantity,
                "totalBs": total,
                "unitBs": round(total / quantity, 2),
                "raw": line,
            }
        )
    return rows
