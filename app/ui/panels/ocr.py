"""Panel 8 · OCR: importación de tickets (fase 9).

El reconocimiento lo hace ``rapidocr-onnxruntime`` (ONNX, sin binarios del
sistema). Si la dependencia no está instalada, el panel sigue siendo útil: se
puede pegar el texto del ticket y usar el mismo importador.

El lote se crea con ``rateSource = 'OCR·lote'`` y la subcategoría provisional
``'Importado OCR'``, y después se sincroniza con los metadatos del SKU — la
misma regla que aplica el ajuste de ``batchImportOcrRows``
(:func:`app.domain.ocr.sync_ocr_sku_metadata`).
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Callable

from nicegui import run, ui

from ...core.constants import VAT_MODES
from ...domain import ocr as domain_ocr
from ...domain import ocr_ticket
from ...domain import transactions as domain_tx
from ...domain.errors import DomainError
from .. import components as c
from ..state import AppState

__all__ = ["render"]

VAT_LABELS = {"exento": "Exento", "incluido": "IVA incluido", "mas_iva": "IVA + 16%"}

_ENGINE: Any = None


def _get_engine() -> Any:
    """Crea (una sola vez) el motor de RapidOCR."""
    global _ENGINE
    if _ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR

        _ENGINE = RapidOCR()
    return _ENGINE


def ocr_available() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def read_image_text(data: bytes) -> tuple[str, str]:
    """Reconoce el texto de una imagen. Devuelve ``(texto, error)``."""
    try:
        import io

        import numpy as np
        from PIL import Image

        image = Image.open(io.BytesIO(data)).convert("RGB")
        array = np.array(image)
        result, _elapsed = _get_engine()(array)
        return ocr_ticket.boxes_to_text(result), ""
    except Exception as exc:  # noqa: BLE001
        return "", f"{type(exc).__name__}: {exc}"


def _build(
    state: AppState, rows: list[dict[str, Any]], refresh: Callable[[], None]
) -> None:
    with ui.column().classes("w-full gap-4 p-4"):
        with c.card():
            c.section_title(
                "Importar tickets",
                c.chip_html("RapidOCR" if ocr_available() else "OCR no instalado",
                            "ok" if ocr_available() else "warn"),
            )
            if not ocr_available():
                ui.html(
                    '<div class="muted">Instala el motor con '
                    '<code>pip install rapidocr-onnxruntime</code>. Mientras tanto '
                    "puedes pegar el texto del ticket abajo.</div>"
                )

            status = ui.html("").classes("muted")

            async def on_upload(event: Any) -> None:
                name = getattr(event, "name", "imagen")
                data = await event.file.read()
                status.content = f"Reconociendo <b>{name}</b>…"
                text, error = await run.io_bound(read_image_text, data)
                if error:
                    status.content = f"No se pudo leer {name}: {error}"
                    ui.notify("Error de OCR.", type="negative")
                    return
                parsed = ocr_ticket.parse_receipt_text(text)
                rows.extend(parsed)
                status.content = (
                    f"{name}: {len(parsed)} líneas de producto reconocidas."
                )
                refresh()

            upload = ui.upload(
                on_upload=on_upload, auto_upload=True, multiple=True
            ).props("accept=image/*").classes("w-full")
            upload.props("label=Subir imágenes de tickets")

            text_area = ui.textarea(
                "…o pega aquí el texto del ticket",
                placeholder="HARINA PAN 1KG   1.234,56",
            ).classes("w-full")

            def parse_pasted() -> None:
                parsed = ocr_ticket.parse_receipt_text(text_area.value or "")
                if not parsed:
                    ui.notify("No se reconoció ninguna línea de producto.", type="warning")
                    return
                rows.extend(parsed)
                text_area.value = ""
                status.content = f"{len(parsed)} líneas añadidas."
                refresh()

            ui.button("Añadir texto pegado", on_click=parse_pasted).props("outline")

        with c.card():
            c.section_title("Lote a importar", c.chip_html(f"{len(rows)} líneas"))
            if not rows:
                ui.html(
                    c.empty_html(
                        "Sube una imagen o pega el texto de un ticket para empezar."
                    )
                )
            else:
                _editor(state, rows, refresh)

        with c.card():
            c.section_title("Cómo se importa")
            ui.html(
                '<div class="muted">Cada línea crea una compra con la tasa activa, '
                "``rateSource = OCR·lote`` y la subcategoría ``Importado OCR``. "
                "Después se sincronizan categoría, unidad, marca y comercio con el "
                "SKU correspondiente.</div>"
            )


def _editor(
    state: AppState, rows: list[dict[str, Any]], refresh: Callable[[], None]
) -> None:
    now_date = dt.date.today().isoformat()
    category_options = {cat["id"]: cat["name"] for cat in state.categories}
    if not category_options:
        ui.html(c.empty_html("Crea al menos una categoría antes de importar el lote."))
        return
    first_category = next(iter(category_options))

    with ui.row().classes("grid grid-cols-2 md:grid-cols-4 gap-3 w-full items-end"):
        date = ui.input("Fecha", value=now_date).props("type=date").classes("w-full")
        category = ui.select(
            category_options, value=first_category, label="Categoría"
        ).classes("w-full")
        mode = ui.select(VAT_LABELS, value="incluido", label="Modalidad IVA").classes(
            "w-full"
        )
        provider = ui.input("Comercio").classes("w-full")

    with ui.column().classes("w-full gap-1"):
        for index, row in enumerate(list(rows)):
            _row_editor(row, index, rows, refresh)

    def import_batch() -> None:
        if not state.active_rate:
            ui.notify("No hay tasa activa: regístrala antes de importar.", type="warning")
            return
        ocr_rate = {
            **state.active_rate,
            "source": domain_ocr.OCR_RATE_SOURCE,
        }
        created: list[dict[str, Any]] = []
        try:
            for row in rows:
                domain_tx.validate(
                    category.value, date.value, row.get("name"), row.get("totalBs")
                )
                product_id, product = domain_tx.resolve_product(
                    state.products,
                    state.workspace,
                    row["name"],
                    category_id=category.value,
                    provider=provider.value or "",
                )
                if product is not None:
                    state.repo.put("products", product)
                record = domain_tx.build_transaction(
                    workspace=state.workspace,
                    date=date.value,
                    category_id=category.value,
                    product_name=row["name"],
                    rate=ocr_rate,
                    bs_amount=row["totalBs"],
                    mode=mode.value or "incluido",
                    product_id=product_id,
                    quantity=row.get("quantity"),
                    provider=provider.value or "",
                    subcategory=domain_ocr.OCR_SUBCATEGORY,
                )
                new_id = state.repo.add("transactions", record)
                created.append({**record, "id": new_id})
        except DomainError as exc:
            ui.notify(str(exc), type="warning")
            return

        # ``APP.products.push``: el catálogo en memoria ya incluye los SKU nuevos.
        state.refresh()
        # Ajuste: el lote hereda los metadatos del SKU.
        for updated in domain_ocr.sync_ocr_sku_metadata(created, state.products):
            state.repo.put("transactions", updated)

        rows.clear()
        state.notify()
        refresh()
        ui.notify(f"Lote importado: {len(created)} compras.", type="positive")

    with ui.row().classes("gap-2 mt-2"):
        ui.button(
            f"Importar {len(rows)} compras", on_click=import_batch
        ).props("color=primary unelevated")
        ui.button("Vaciar lote", on_click=lambda: _clear(rows, refresh)).props("flat")


def _clear(rows: list[dict[str, Any]], refresh: Callable[[], None]) -> None:
    rows.clear()
    refresh()


def _row_editor(
    row: dict[str, Any],
    index: int,
    rows: list[dict[str, Any]],
    refresh: Callable[[], None],
) -> None:
    with ui.row().classes("row w-full items-center gap-2").style(
        "border-bottom:1px solid var(--line-soft); padding:3px 0"
    ):
        name = ui.input(value=row["name"]).classes("col-grow").props("dense")
        quantity = ui.number(value=row.get("quantity") or 1, min=1).props("dense").style(
            "max-width:90px"
        )
        total = ui.number(value=row.get("totalBs") or 0, min=0, format="%.2f").props(
            "dense"
        ).style("max-width:130px")

        def commit() -> None:
            row["name"] = (name.value or "").strip()
            row["quantity"] = int(quantity.value or 1)
            row["totalBs"] = float(total.value or 0)
            row["unitBs"] = round(row["totalBs"] / row["quantity"], 2) if row["quantity"] else 0

        for widget in (name, quantity, total):
            widget.on_value_change(lambda _e=None: commit())

        def remove() -> None:
            if 0 <= index < len(rows):
                rows.pop(index)
            refresh()

        ui.button(icon="delete", on_click=remove).props("flat dense color=negative")


def render(state: AppState) -> None:
    rows: list[dict[str, Any]] = []

    @ui.refreshable
    def content() -> None:
        _build(state, rows, content.refresh)

    content()
    state.subscribe(content.refresh)
