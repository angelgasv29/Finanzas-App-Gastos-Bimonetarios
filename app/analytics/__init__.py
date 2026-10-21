"""Motor de análisis.

Un módulo por sub-pestaña del panel de Análisis. Cada función recibe las
transacciones **ya filtradas** por el rango temporal y devuelve un diccionario
con los valores que la interfaz escribe en cada nodo (claves = ``id`` del DOM del
de referencia), más las series de los gráficos y las filas de las tablas.

Así el cálculo queda separado de NiceGUI y se puede comparar con el JavaScript
de referencia sin abrir un navegador.
"""

from .common import (
    ProductHistory,
    build_history,
    by_product,
    filtered_by_range,
    series_from_history,
)
from .inflation import analysis_a
from .categories import category_impact, payment_impact, vat_audit
from .extras import (
    budget_traffic_light,
    hierarchical_tree,
    outlier_scatter,
    pareto,
    sparklines,
)
from .frequency import frequency_view
from .pivot import pivot_view
from .projection import product_projection, rate_projection
from .variants import variants_view

__all__ = [
    "ProductHistory",
    "analysis_a",
    "budget_traffic_light",
    "build_history",
    "by_product",
    "category_impact",
    "filtered_by_range",
    "frequency_view",
    "hierarchical_tree",
    "outlier_scatter",
    "pareto",
    "payment_impact",
    "pivot_view",
    "product_projection",
    "rate_projection",
    "series_from_history",
    "sparklines",
    "variants_view",
    "vat_audit",
]
