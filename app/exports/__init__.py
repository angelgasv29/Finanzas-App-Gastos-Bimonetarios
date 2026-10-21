"""Exportaciones: Excel de 6 hojas, CSV, respaldo JSON y acta de cierre.

Los generadores devuelven siempre **estructuras de datos** (filas como
diccionarios, textos ya formateados) y dejan la escritura de ficheros en manos de
``openpyxl`` o de quien llame. Así pueden verificarse contra la versión de referencia sin
navegador ni sistema de ficheros.
"""

from __future__ import annotations

from .csv_export import (
    CSV_FILENAME_PREFIX,
    PRODUCT_HEADERS,
    RATE_HEADERS,
    TRANSACTION_HEADERS,
    csv_filename,
    products_rows,
    rates_rows,
    to_csv,
    transaction_headers,
    transactions_rows,
)
from .acta import build_closure_act_html
from .backup import (
    BACKUP_APP,
    BACKUP_VERSION,
    LS_CONFIG_KEYS,
    backup_filename,
    backup_text,
    build_backup,
    dedupe_imported,
    import_plan,
    import_prompt,
    import_signature,
    is_valid_backup,
    plan_excel_import,
)
from .excel import (
    SHEET_NAMES,
    analysis_rows,
    build_sheets,
    catalog_rows,
    category_payment_rows,
    column_widths,
    ledger_rows,
    summary_rows,
    write_xlsx,
    xlsx_filename,
)

__all__ = [
    "BACKUP_APP",
    "BACKUP_VERSION",
    "CSV_FILENAME_PREFIX",
    "LS_CONFIG_KEYS",
    "PRODUCT_HEADERS",
    "RATE_HEADERS",
    "SHEET_NAMES",
    "TRANSACTION_HEADERS",
    "analysis_rows",
    "backup_filename",
    "backup_text",
    "build_backup",
    "build_closure_act_html",
    "build_sheets",
    "catalog_rows",
    "category_payment_rows",
    "column_widths",
    "csv_filename",
    "dedupe_imported",
    "import_plan",
    "import_prompt",
    "import_signature",
    "is_valid_backup",
    "ledger_rows",
    "plan_excel_import",
    "products_rows",
    "rates_rows",
    "summary_rows",
    "to_csv",
    "transaction_headers",
    "transactions_rows",
    "write_xlsx",
    "xlsx_filename",
]
