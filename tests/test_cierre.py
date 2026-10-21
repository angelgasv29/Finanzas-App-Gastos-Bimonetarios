"""Pruebas del snapshot de cierre anual (``runCloseWizard``)."""

from __future__ import annotations

from app.domain import closures


def _tx(**overrides):
    base = {
        "workspace": "personal",
        "year": 2026,
        "date": "2026-01-10",
        "categoryId": "c1",
        "productId": "p1",
        "productName": "Harina",
        "quantity": 1,
        "amountUsd": 10.0,
        "amountBs": 400.0,
        "ivaMonto": 55.17,
        "baseImponible": 344.83,
    }
    base.update(overrides)
    return base


def test_snapshot_is_none_without_transactions() -> None:
    assert (
        closures.build_closure_snapshot(
            [], workspace="personal", year=2026, categories=[], rates=[]
        )
        is None
    )
    other = [_tx(workspace="profesional")]
    assert (
        closures.build_closure_snapshot(
            other, workspace="personal", year=2026, categories=[], rates=[]
        )
        is None
    )


def test_snapshot_sums_and_ranking() -> None:
    txs = [
        _tx(categoryId="c1", amountUsd=10.0, amountBs=400.0),
        _tx(categoryId="c2", amountUsd=30.0, amountBs=1200.0),
        _tx(categoryId="c2", amountUsd=5.0, amountBs=200.0),
        _tx(categoryId="c1", amountUsd=1.0, amountBs=40.0),
    ]
    categories = [
        {"id": "c1", "name": "Comida", "color": "#111111"},
        {"id": "c2", "name": "Salud", "color": "#222222"},
    ]
    snapshot = closures.build_closure_snapshot(
        txs,
        workspace="personal",
        year=2026,
        categories=categories,
        rates=[],
        timestamp=1000,
        id_factory=lambda prefix: f"{prefix}-1",
    )

    assert snapshot is not None
    assert snapshot["id"] == "closure-1"
    assert snapshot["closedAt"] == 1000
    assert snapshot["txCount"] == 4
    assert snapshot["totalUsd"] == 46.0
    assert snapshot["totalBs"] == 1840.0
    assert snapshot["ivaTotal"] == 220.68
    # Orden por gasto: c2 (35) antes que c1 (11).
    assert [row["name"] for row in snapshot["topCategories"]] == ["Salud", "Comida"]
    assert snapshot["topCategories"][0]["count"] == 2
    assert snapshot["topExpenses"][0]["amountUsd"] == 30.0
    assert snapshot["rateStart"] is None
    assert snapshot["rateDelta"] == 0.0
    assert snapshot["inflationAvg"] == 0.0
    assert snapshot["notes"] == ""


def test_snapshot_rate_delta_and_micro_inflation() -> None:
    txs = [
        _tx(date="2026-01-10", quantity=2, amountUsd=10.0),
        _tx(date="2026-04-10", quantity=2, amountUsd=20.0),
    ]
    rates = [
        {"date": "2025-12-31", "value": 35.0},
        {"date": "2026-06-01", "value": 44.0},
        {"date": "2026-01-01", "value": 40.0},
    ]
    snapshot = closures.build_closure_snapshot(
        txs,
        workspace="personal",
        year=2026,
        categories=[{"id": "c1", "name": "Comida", "color": "#2563EB"}],
        rates=rates,
        timestamp=1,
        id_factory=lambda prefix: f"{prefix}-2",
    )

    assert snapshot is not None
    assert snapshot["rateStart"] == 40.0
    assert snapshot["rateEnd"] == 44.0
    assert snapshot["rateStartDate"] == "2026-01-01"
    assert snapshot["rateDelta"] == 10.0
    # El precio unitario pasa de 5 a 10 USD en 90 días → CAGR positivo.
    assert snapshot["inflationAvg"] > 0
    assert snapshot["topCategories"][0]["color"] == "#2563EB"


def test_snapshot_uses_no_category_bucket() -> None:
    txs = [_tx(categoryId=None, productId=None, amountUsd=7.0)]
    snapshot = closures.build_closure_snapshot(
        txs,
        workspace="personal",
        year=2026,
        categories=[],
        rates=[],
        timestamp=1,
        id_factory=lambda prefix: f"{prefix}-3",
    )

    assert snapshot is not None
    assert snapshot["topCategories"][0]["name"] == "Sin categoría"
    assert snapshot["topCategories"][0]["color"] == "#6B7280"
    assert snapshot["topExpenses"][0]["productName"] == "Harina"
    assert snapshot["inflationAvg"] == 0.0
