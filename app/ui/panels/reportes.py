"""Panel 6 · Reportes: exportación e importación de datos.

Toda la generación vive en :mod:`app.exports` (Excel de 6 hojas, los tres CSV, el
respaldo JSON y el acta de cierre). Aquí solo se recogen las opciones y se
entrega el fichero al navegador con ``ui.download``.
"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from ...core.ids import now_ms
from ...domain import closures as domain_closures
from ...exports import (
    backup_filename,
    backup_text,
    build_backup,
    build_closure_act_html,
    build_sheets,
    csv_filename,
    import_plan,
    import_signature,
    is_valid_backup,
    products_rows,
    rates_rows,
    to_csv,
    transaction_headers,
    transactions_rows,
    write_xlsx,
    xlsx_filename,
)
from .. import components as c
from ..state import AppState

__all__ = ["render"]


def backup_payload(state: AppState, stamp: float | None = None) -> dict[str, Any]:
    """Respaldo JSON con **todos** los entornos.

    La versión de referencia usa ``DB.all`` para las cinco tiendas, no
    ``APP.transactions``: el respaldo no depende del entorno activo.
    """
    return build_backup(
        transactions=state.repo.all("transactions"),
        products=state.repo.all("products"),
        categories=state.repo.all("categories"),
        rates=state.rate_cache,
        closures=state.repo.all("closures"),
        workspace=state.workspace,
        fiscal_year=state.fiscal_year,
        ls_config={
            "theme": state.theme,
            "workspace": state.workspace,
            "fiscalYear": state.fiscal_year,
            "decimals": state.decimals,
            "currency": state.currency,
        },
        now_ms=now_ms() if stamp is None else stamp,
    )


def _build(state: AppState) -> None:
    with ui.column().classes("w-full gap-4 p-4"):
        with c.card():
            c.section_title("Exportar")
            year_txs = state.year_transactions()
            ui.html(
                f'<div class="row wrap" style="gap:8px">'
                f'{c.chip_html(f"{len(year_txs)} movimientos en {state.fiscal_year}")}'
                f'{c.chip_html(f"{len(state.products)} SKU")}'
                f'{c.chip_html(f"{len(state.categories)} categorías")}'
                f"</div>"
            )

            def export_xlsx() -> None:
                stamp = now_ms()
                sheets = build_sheets(
                    year_txs,
                    workspace=state.workspace,
                    year=state.fiscal_year,
                    products=state.products,
                    categories=state.categories,
                    rates=state.rate_cache,
                    now_ms=stamp,
                )
                filename = xlsx_filename(state.workspace, state.fiscal_year, stamp)
                import tempfile
                from pathlib import Path

                target = Path(tempfile.mkdtemp()) / filename
                write_xlsx(target, sheets)
                ui.download(target.read_bytes(), filename)
                ui.notify(f"Excel generado: {filename}", type="positive")

            def export_csv(kind: str) -> None:
                stamp = now_ms()
                if kind == "tx":
                    rows = transactions_rows(year_txs, state.categories)
                    headers = transaction_headers(rows)
                elif kind == "prod":
                    rows = products_rows(state.products)
                    headers = list(rows[0].keys()) if rows else []
                else:
                    rows = rates_rows(state.rate_cache)
                    headers = list(rows[0].keys()) if rows else []
                filename = csv_filename(kind, stamp)
                ui.download(to_csv(rows, headers).encode("utf-8"), filename)
                ui.notify(f"CSV generado: {filename}", type="positive")

            with ui.row().classes("gap-2 wrap"):
                ui.button("Excel (6 hojas)", on_click=export_xlsx).props(
                    "color=primary unelevated"
                )
                ui.button("CSV · movimientos", on_click=lambda: export_csv("tx")).props("outline")
                ui.button("CSV · catálogo", on_click=lambda: export_csv("prod")).props("outline")
                ui.button("CSV · tasas", on_click=lambda: export_csv("rates")).props("outline")

            def export_backup() -> None:
                stamp = now_ms()
                data = backup_payload(state, stamp)
                filename = backup_filename(stamp)
                ui.download(backup_text(data).encode("utf-8"), filename)
                ui.notify(f"Respaldo generado: {filename}", type="positive")

            ui.button("Respaldo JSON completo", on_click=export_backup).props("outline")

        with c.card():
            c.section_title("Importar respaldo JSON")
            ui.html(
                '<div class="muted">Importa un respaldo generado por esta aplicación. '
                "Las compras duplicadas (misma firma entorno/fecha/producto/importe) "
                "se descartan.</div>"
            )

            def on_upload(event: Any) -> None:
                import json

                try:
                    payload = json.loads(event.content.read().decode("utf-8"))
                except Exception:  # noqa: BLE001
                    ui.notify("El fichero no es un JSON válido.", type="negative")
                    return
                if not is_valid_backup(payload):
                    ui.notify("El fichero no es un respaldo de esta aplicación.", type="negative")
                    return
                plan = import_plan(
                    payload,
                    existing_product_ids={p.get("id") for p in state.repo.all("products")},
                    existing_category_ids={
                        c_.get("id") for c_ in state.repo.all("categories")
                    },
                    existing_closure_ids={c_.get("id") for c_ in state.repo.all("closures")},
                )
                existing_signatures = {
                    import_signature(tx) for tx in state.repo.all("transactions")
                }
                imported = 0
                for record in plan["transactions"]:
                    signature = import_signature(
                        {**record, "workspace": record.get("workspace") or state.workspace}
                    )
                    if signature in existing_signatures:
                        continue
                    existing_signatures.add(signature)
                    state.repo.add("transactions", record)
                    imported += 1
                for product in plan["products"]:
                    state.repo.put("products", product)
                for category in plan["categories"]:
                    state.repo.put("categories", category)
                for rate in plan["rates"]:
                    state.repo.put("rates", rate)
                for closure in plan["closures"]:
                    state.repo.put("closures", closure)
                state.refresh()
                state.notify()
                ui.notify(
                    f"Importados {imported} movimientos, "
                    f"{len(plan['products'])} SKU y {len(plan['categories'])} categorías.",
                    type="positive",
                )

            ui.upload(on_upload=on_upload, auto_upload=True).props('accept=.json').classes("w-full")

        with c.card():
            c.section_title("Acta de cierre del ejercicio")
            snapshot = domain_closures.build_closure_snapshot(
                state.transactions(),
                workspace=state.workspace,
                year=state.fiscal_year,
                categories=state.categories,
                rates=state.rate_cache,
            )
            if snapshot is None:
                ui.html(
                    c.empty_html(
                        f"No hay movimientos en {state.fiscal_year} para emitir el acta."
                    )
                )
            else:
                ui.html(
                    f'<div class="row wrap" style="gap:8px">'
                    f'{c.chip_html(f"{snapshot['txCount']} movimientos", "brand")}'
                    f'{c.chip_html("Total " + state.fmt(snapshot["totalUsd"], snapshot["totalBs"]))}'
                    f'{c.chip_html("IVA " + f"Bs. {snapshot['ivaTotal']:.2f}")}'
                    f'{c.chip_html("Devaluación " + f"{snapshot['rateDelta']:+.2f}%", "warn")}'
                    f'{c.chip_html("Inflación micro " + f"{snapshot['inflationAvg']:.2f}%")}'
                    f"</div>"
                )

                def download_acta() -> None:
                    stamp = now_ms()
                    html = build_closure_act_html({**snapshot, "notes": ""}, now_ms=stamp)
                    ui.download(
                        html.encode("utf-8"),
                        f"Acta_Cierre_{state.fiscal_year}_{state.workspace}.html",
                    )
                    ui.notify("Acta generada.", type="positive")

                with ui.row().classes("gap-2"):
                    ui.button("Descargar acta (HTML)", on_click=download_acta).props(
                        "color=primary unelevated"
                    )
                    ui.button(
                        "Cerrar y archivar ejercicio",
                        on_click=lambda: _close_year(state, snapshot),
                    ).props("outline color=negative")


def _close_year(state: AppState, snapshot: dict[str, Any]) -> None:
    with ui.dialog() as dialog, c.card():
        c.section_title(f"Cerrar ejercicio {snapshot['year']}")
        ui.html(
            "<div>Se archivará el snapshot del ejercicio como registro histórico. "
            "El catálogo, las categorías y las tasas se conservan.</div>"
        )
        clean = ui.checkbox(
            f"Limpiar transacciones de {snapshot['year']} tras archivar el Acta"
        )

        def confirm() -> None:
            state.repo.put("closures", snapshot)
            if clean.value:
                for tx in domain_closures.year_transactions(
                    state.transactions(), workspace=state.workspace, year=state.fiscal_year
                ):
                    state.repo.delete("transactions", tx.get("id"))
            state.refresh()
            state.notify()
            dialog.close()
            ui.notify(f"Ejercicio {snapshot['year']} cerrado y archivado.", type="positive")

        with ui.row().classes("gap-2 mt-2"):
            ui.button("Cerrar y archivar", on_click=confirm).props("color=negative unelevated")
            ui.button("Cancelar", on_click=dialog.close).props("flat")
    dialog.open()


def render(state: AppState) -> None:
    @ui.refreshable
    def content() -> None:
        _build(state)

    content()
    state.subscribe(content.refresh)
