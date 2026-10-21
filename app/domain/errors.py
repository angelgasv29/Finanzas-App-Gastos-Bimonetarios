"""Errores de dominio.

La versión de referencia no lanza excepciones en el flujo de guardado: muestra un aviso con
``toast(mensaje, nivel)`` y aborta. Aquí se lanza una excepción con el mismo
mensaje y nivel, para que la interfaz lo traduzca a un aviso. Así la regla vive
en el dominio y la presentación solo la muestra.
"""

from __future__ import annotations

__all__ = ["DomainError", "ValidationError", "MissingRateError"]


class DomainError(Exception):
    """Error esperado de las reglas de negocio, ya redactado para el usuario.

    >>> err = DomainError("Completa los campos obligatorios.", "warn")
    >>> err.message, err.level
    ('Completa los campos obligatorios.', 'warn')
    >>> str(err)
    'Completa los campos obligatorios.'
    """

    def __init__(self, message: str, level: str = "err") -> None:
        super().__init__(message)
        self.message = message
        self.level = level


class ValidationError(DomainError):
    """Faltan campos obligatorios."""


class MissingRateError(DomainError):
    """No hay tasa disponible para la fecha."""
