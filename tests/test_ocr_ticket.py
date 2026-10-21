"""Pruebas del lector de tickets del lote OCR."""

from __future__ import annotations

from app.domain import ocr_ticket


def test_parse_amount_accepts_both_separators() -> None:
    assert ocr_ticket.parse_amount("1.234,56") == 1234.56
    assert ocr_ticket.parse_amount("1,234.56") == 1234.56
    assert ocr_ticket.parse_amount("890,00") == 890.0
    assert ocr_ticket.parse_amount("890.00") == 890.0
    assert ocr_ticket.parse_amount("1.234") == 1234.0
    assert ocr_ticket.parse_amount("12") == 12.0
    assert ocr_ticket.parse_amount("") is None
    assert ocr_ticket.parse_amount("n/a") is None


def test_parse_receipt_skips_totals_and_headers() -> None:
    ticket = "\n".join(
        [
            "EXCELSIOR GAMA, C.A.",
            "RIF: J-00000000-0",
            "FECHA 19/10/2026",
            "HARINA PAN 1KG   1.234,56",
            "2 x LECHE EN POLVO 900G   890,00",
            "SUBTOTAL   2.124,56",
            "IVA 16%   339,93",
            "TOTAL   2.464,49",
            "GRACIAS POR SU COMPRA",
        ]
    )
    rows = ocr_ticket.parse_receipt_text(ticket)

    assert [(row["name"], row["quantity"], row["totalBs"]) for row in rows] == [
        ("HARINA PAN 1KG", 1, 1234.56),
        ("LECHE EN POLVO 900G", 2, 890.0),
    ]
    assert rows[1]["unitBs"] == 445.0


def test_parse_receipt_keeps_unit_prefixes() -> None:
    rows = ocr_ticket.parse_receipt_text("3 kg ARROZ BLANCO   120,00")

    assert len(rows) == 1
    assert rows[0]["name"] == "ARROZ BLANCO"
    assert rows[0]["quantity"] == 3
    assert rows[0]["unitBs"] == 40.0


def test_parse_receipt_ignores_lines_without_amount_or_letters() -> None:
    assert ocr_ticket.parse_receipt_text("") == []
    assert ocr_ticket.parse_receipt_text("123456\n***\n") == []
    # Un importe sin nombre de producto tampoco entra.
    assert ocr_ticket.parse_receipt_text("1.234,56") == []


def test_parse_receipt_does_not_mutate_input() -> None:
    text = "CAFÉ MOLIDO 500G   65,50"
    before = text
    rows = ocr_ticket.parse_receipt_text(text)

    assert text == before
    assert rows[0]["raw"] == "CAFÉ MOLIDO 500G   65,50"
