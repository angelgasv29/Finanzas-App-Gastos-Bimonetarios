"""Pruebas del respaldo JSON de la interfaz (sin navegador).

El punto delicado es el alcance: la versión de referencia exporta ``DB.all`` (los **dos**
entornos), no solo el workspace activo. Si se exportara solo el activo, un
respaldo parecería completo y perdería la mitad de los datos.
"""

from __future__ import annotations

from pathlib import Path

from app.domain import transactions as domain_tx
from app.ui.panels.reportes import backup_payload
from app.ui.state import open_state


def test_el_respaldo_lleva_los_dos_entornos(tmp_path: Path) -> None:
    state = open_state(tmp_path / "app.sqlite3")
    state.repo.put(
        "rates", {"date": "2026-03-15", "value": 40.0, "source": "BCV", "ts": 0}
    )
    state.refresh()

    state.repo.put(
        "products",
        {"id": "PROD-P-TEST", "workspace": "personal", "name": "Harina", "name_lower": "harina"},
    )
    state.repo.put(
        "products",
        {"id": "PROD-W-TEST", "workspace": "profesional", "name": "Resma", "name_lower": "resma"},
    )
    for workspace, product in (("personal", "Harina"), ("profesional", "Resma")):
        state.repo.add(
            "transactions",
            domain_tx.build_transaction(
                workspace=workspace,
                date="2026-03-15",
                category_id="cat-x",
                product_name=product,
                rate=state.active_rate,
                bs_amount=116,
                mode="incluido",
                timestamp=1,
            ),
        )

    payload = backup_payload(state, 123)
    workspace = state.workspace
    state.close()

    assert {tx["workspace"] for tx in payload["transactions"]} == {
        "personal",
        "profesional",
    }
    assert {product["workspace"] for product in payload["products"]} == {
        "personal",
        "profesional",
    }
    # Las 7 categorías sembradas (4 personales + 3 profesionales).
    assert len(payload["categories"]) == 7
    assert payload["meta"]["app"] == "GastosBimonetarios"
    assert payload["meta"]["workspace"] == workspace
