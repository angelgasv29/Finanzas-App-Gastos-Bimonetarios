"""Implementación de Python de la aplicación "Gastos Bimonetarios".

Origen: la referencia (8021 líneas, 1 archivo, 0 backend).

El paquete está organizado por capas, de dentro hacia fuera:

``core``       Constantes, formato de moneda, estadística, períodos temporales.
``data``       Persistencia (SQLite en lugar de IndexedDB).
``domain``     Reglas de negocio contables (IVA, transacciones, tasas, cierres).
``analytics``  Motor de análisis (precios, pivote, frecuencia, proyecciones).
``exports``    Excel, CSV, respaldo JSON, acta de cierre.
``ocr``        Reconocimiento de facturas.
``ui``         Interfaz NiceGUI (reconstrucción visual).
"""

__version__ = "0.1.0"
