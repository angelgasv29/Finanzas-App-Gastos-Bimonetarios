"""Reglas de negocio.

El motor de la versión de referencia está incrustado en funciones que también dibujan la
interfaz. Aquí se separa: estas funciones de Python **calculan** y devuelven
datos; la interfaz (``app/ui``) solo los muestra.

Módulos:

- :mod:`errors`        Errores de dominio con el mensaje de la versión de referencia.
- :mod:`vat`           Los 3 modos de IVA.
- :mod:`rates`         Caché de tasas y selección por fecha.
- :mod:`transactions`  Alta, edición y conversión bidireccional Bs↔USD.
- :mod:`filters`       Filtros y orden de la lista de movimientos.
- :mod:`runrate`       Ritmo de gasto del mes (run-rate).
- :mod:`breakeven`     Gasto fijo vs. variable (punto de equilibrio).
- :mod:`recurring`     Compromisos recurrentes pendientes.
- :mod:`prices`        Alerta de sobreprecio frente al histórico del SKU.
- :mod:`products`      Propagación del nombre de un SKU a sus compras.
- :mod:`closures`      Qué compras se retiran en el cierre anual.
- :mod:`ocr`           Metadatos de SKU que hereda un lote OCR.
- :mod:`demo`          Dataset de demostración y sus retoques.
"""

from .breakeven import BreakEven, break_even_view, compute_break_even
from .closures import build_closure_snapshot, count_by_year, year_transactions
from .demo import DEMO_ORIGINS, build_demo_dataset, fix_demo_dataset
from .errors import DomainError, MissingRateError, ValidationError
from .filters import filter_transactions, sort_transactions_desc
from .ocr import sync_ocr_sku_metadata
from .prices import PriceAlert, compute_price_alert, price_alert_for_form, price_alert_view
from .products import rename_product_transactions
from .rates import get_rate_for_date, pick_active_rate, rate_value_of, sort_rates_desc
from .recurring import (
    RecurringCommitment,
    find_recurring_commitments,
    recurring_view,
)
from .runrate import RunRate, compute_run_rate, run_rate_view
from .transactions import (
    apply_edit,
    build_transaction,
    editor_recalc,
    recalc_bs_usd,
    repeat_transaction,
    require_rate,
    resolve_edited_bs,
    resolve_product,
    validate,
)
from .vat import VatAmounts, compute_vat, rounded_vat, vat_preview

__all__ = [
    "BreakEven",
    "DEMO_ORIGINS",
    "DomainError",
    "MissingRateError",
    "PriceAlert",
    "RecurringCommitment",
    "RunRate",
    "ValidationError",
    "VatAmounts",
    "apply_edit",
    "break_even_view",
    "build_closure_snapshot",
    "build_demo_dataset",
    "build_transaction",
    "compute_break_even",
    "compute_price_alert",
    "compute_run_rate",
    "compute_vat",
    "count_by_year",
    "editor_recalc",
    "filter_transactions",
    "find_recurring_commitments",
    "fix_demo_dataset",
    "get_rate_for_date",
    "pick_active_rate",
    "price_alert_for_form",
    "price_alert_view",
    "rate_value_of",
    "recalc_bs_usd",
    "recurring_view",
    "rename_product_transactions",
    "repeat_transaction",
    "require_rate",
    "resolve_edited_bs",
    "resolve_product",
    "rounded_vat",
    "run_rate_view",
    "sort_rates_desc",
    "sort_transactions_desc",
    "sync_ocr_sku_metadata",
    "validate",
    "vat_preview",
    "year_transactions",
]
