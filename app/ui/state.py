"""Estado de la aplicación.

Cada pestaña del navegador tiene su propio :class:`AppState`, igual que el
original guardaba ``APP`` en una global de la página. Sustituye a ese objeto
(líneas 2627-2640) y a la caché de tasas (``ratesCache``), pero **sin** variable
global: se pasa explícitamente a los paneles.

Los datos son compartidos (un solo fichero SQLite, como el IndexedDB del
original); lo que no se comparte es la configuración en memoria: entorno, año
fiscal, moneda, decimales, tema y tasa de sesión. Las preferencias sí se
persisten, así que una pestaña nueva arranca con lo último guardado.

Deliberadamente no importa NiceGUI: así puede probarse sin navegador. Cuando algo
cambia, avisa a quien se haya suscrito (``subscribe``/``notify``) para que los
paneles se vuelvan a pintar.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..core.constants import LS_KEYS, STORES
from ..core.ids import new_sku
from ..core.money import MoneyContext, fmt_money
from ..data.db import Database, default_db_path
from ..data.repo import Repository
from ..data.seed import seed_categories_if_empty
from ..domain import rates as domain_rates

__all__ = ["AppState", "open_state"]

#: Entornos del original (``initWorkspace``, línea 3042).
WORKSPACES = ("personal", "profesional")


def open_state(
    path: str | Path | None = None, *, workspace: str = "personal"
) -> AppState:
    """Abre (o crea) la base de datos y devuelve el estado listo para usar.

    La semilla de categorías se comprueba en cada apertura, igual que el arranque
    del original (``seedCategoriesIfEmpty``): si un entorno quedó vacío, se
    vuelve a sembrar.

    >>> import tempfile
    >>> from pathlib import Path
    >>> state = open_state(Path(tempfile.mkdtemp()) / "app.sqlite3")
    >>> state.workspace, state.currency
    ('personal', 'USD')
    >>> len(state.categories) >= 1
    True
    """
    database = Database(path if path is not None else default_db_path()).initialize()
    repo = Repository(database)
    seed_categories_if_empty(repo)
    return AppState(repo=repo, workspace=workspace)


@dataclass
class AppState:
    """Estado de la sesión: entorno, año fiscal, moneda, decimales y cachés."""

    repo: Repository
    workspace: str = "personal"
    fiscal_year: int = field(default_factory=lambda: dt.date.today().year)
    currency: str = "USD"
    decimals: int = 2
    theme: str = "dark"

    #: Tasa fijada a mano para la sesión. Si es ``None`` se usa la más reciente.
    session_rate: dict[str, Any] | None = None

    categories: list[dict[str, Any]] = field(default_factory=list)
    products: list[dict[str, Any]] = field(default_factory=list)
    rate_cache: list[dict[str, Any]] = field(default_factory=list)
    #: Contexto que se conserva al registrar compras consecutivas (fecha,
    #: categoría y tasa de IVA). Vive solo en la sesión, no en la base.
    register_context: dict[str, Any] = field(default_factory=dict)

    _active_rate: dict[str, Any] | None = None
    _listeners: list[Callable[[], None]] = field(default_factory=list, repr=False)

    # -- ciclo de vida -----------------------------------------------------

    def __post_init__(self) -> None:
        self.load_config()
        self.refresh()

    def close(self) -> None:
        self.repo.db.close()

    @property
    def db(self) -> Database:
        return self.repo.db

    # -- cachés ------------------------------------------------------------

    def refresh(self) -> None:
        """Recarga las cachés del entorno (``loadWorkspaceData``/``refreshRatesCache``)."""
        self.categories = self.repo.categories_for(self.workspace)
        self.products = self.repo.products_for(self.workspace)
        self.rate_cache = self.repo.rates_desc()
        self._active_rate = domain_rates.pick_active_rate(
            self.rate_cache, self.session_rate, session_locked=bool(self.session_rate)
        )

    @property
    def active_rate(self) -> dict[str, Any] | None:
        """Tasa activa (``APP.rate``): la de sesión o la más reciente."""
        return self._active_rate

    @property
    def rate_value(self) -> float | None:
        return domain_rates.rate_value_of(self._active_rate)

    @property
    def money(self) -> MoneyContext:
        """Contexto de formateo con la moneda, los decimales y la tasa activa."""
        return MoneyContext(self.currency, self.decimals, self.rate_value)

    def fmt(self, usd: Any, bs: Any, decimals: int | None = None) -> str:
        """``fmtMoney(usd, bs, decimales)`` con el estado actual."""
        return fmt_money(usd, bs, self.money, decimals)

    def category_name(self, category_id: Any) -> str:
        for category in self.categories:
            if category.get("id") == category_id:
                return str(category.get("name") or "")
        return ""

    def category_color(self, category_id: Any, fallback: str = "#2563EB") -> str:
        for category in self.categories:
            if category.get("id") == category_id:
                return str(category.get("color") or fallback)
        return fallback

    def find_product(self, product_id: Any) -> dict[str, Any] | None:
        for product in self.products:
            if product.get("id") == product_id:
                return product
        return None

    # -- datos -------------------------------------------------------------

    def transactions(self) -> list[dict[str, Any]]:
        """Todas las compras del entorno."""
        return self.repo.transactions_for_workspace(self.workspace)

    def year_transactions(self) -> list[dict[str, Any]]:
        """Compras del año fiscal del entorno."""
        return self.repo.transactions_for_year(self.workspace, self.fiscal_year)

    def audit_now(self) -> dt.datetime:
        """Reloj que se pasa a las funciones del dominio (``new Date()``)."""
        return dt.datetime.now()

    # -- configuración persistida -----------------------------------------

    def load_config(self) -> None:
        """Lee las preferencias guardadas (``localStorage`` → tabla ``config``)."""
        workspace = self.repo.get_config(LS_KEYS["workspace"])
        if workspace in WORKSPACES:
            self.workspace = workspace
        currency = self.repo.get_config(LS_KEYS["currency"])
        if currency in ("USD", "VES"):
            self.currency = currency
        theme = self.repo.get_config(LS_KEYS["theme"])
        if theme in ("dark", "light"):
            self.theme = theme
        decimals = self.repo.get_config(LS_KEYS["decimals"])
        if decimals is not None and str(decimals).isdigit():
            self.decimals = int(decimals)
        year = self.repo.get_config(LS_KEYS["fiscal_year"])
        if year is not None and str(year).isdigit():
            self.fiscal_year = int(year)

        # La tasa de sesión se guardaba en ``localStorage`` (``gb_session_rate``)
        # y se restauraba al arrancar (líneas 7440-7442).
        raw_rate = self.repo.get_config(LS_KEYS["session_rate"])
        if raw_rate and raw_rate != "null":
            try:
                stored = json.loads(raw_rate)
            except (TypeError, ValueError):
                stored = None
            if isinstance(stored, dict) and stored.get("value"):
                try:
                    self.session_rate = {
                        "value": float(stored["value"]),
                        "date": str(stored.get("date") or dt.date.today().isoformat()),
                        "source": str(stored.get("source") or "Manual"),
                    }
                except (TypeError, ValueError):
                    self.session_rate = None

    def save_config(self) -> None:
        self.repo.set_config(LS_KEYS["workspace"], self.workspace)
        self.repo.set_config(LS_KEYS["currency"], self.currency)
        self.repo.set_config(LS_KEYS["theme"], self.theme)
        self.repo.set_config(LS_KEYS["decimals"], self.decimals)
        self.repo.set_config(LS_KEYS["fiscal_year"], self.fiscal_year)

    # -- mutadores ---------------------------------------------------------

    def set_workspace(self, workspace: str) -> None:
        """Cambia de entorno: recarga sus datos y siembra si está vacío."""
        self.workspace = workspace
        seed_categories_if_empty(self.repo, workspaces=(workspace,))
        self.save_config()
        self.refresh()
        self.notify()

    def set_fiscal_year(self, year: int) -> None:
        self.fiscal_year = int(year)
        self.save_config()
        self.notify()

    def set_currency(self, currency: str) -> None:
        self.currency = "VES" if currency == "VES" else "USD"
        self.save_config()
        self.notify()

    def set_theme(self, theme: str) -> None:
        self.theme = "light" if theme == "light" else "dark"
        self.save_config()
        self.notify()

    def set_decimals(self, decimals: int) -> None:
        self.decimals = max(0, min(6, int(decimals)))
        self.save_config()
        self.notify()

    def lock_session_rate(self, value: Any, date: str | None = None) -> None:
        """Fija la tasa de la sesión (``saveManualRate``).

        Se persiste como ``gb_session_rate`` para que sobreviva a una recarga,
        igual que el original con ``localStorage``.
        """
        stamp = date or dt.date.today().isoformat()
        self.session_rate = {"value": float(value), "date": stamp, "source": "Manual"}
        self.repo.set_config(
            LS_KEYS["session_rate"], json.dumps(self.session_rate)
        )
        self.refresh()
        self.notify()

    def clear_session_rate(self) -> None:
        self.session_rate = None
        self.repo.remove_config(LS_KEYS["session_rate"])
        self.refresh()
        self.notify()

    # -- avisos ------------------------------------------------------------

    def subscribe(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Registra un panel para que se repinte. Devuelve la función para darse de baja."""
        self._listeners.append(callback)

        def unsubscribe() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return unsubscribe

    def notify(self) -> None:
        for callback in list(self._listeners):
            try:
                callback()
            except RuntimeError:
                # Pestaña cerrada: su slot ya no existe. Se descarta el oyente.
                if callback in self._listeners:
                    self._listeners.remove(callback)
            except Exception:  # noqa: BLE001 - un panel roto no debe tumbar el resto
                logging.exception("Fallo al repintar un panel")

    # -- utilidades --------------------------------------------------------

    def new_product_id(self) -> str:
        """``newSKU()`` con el prefijo del entorno."""
        return new_sku(self.workspace)

    def storage_stats(self) -> dict[str, int]:
        return self.repo.storage_stats()

    def counts(self) -> dict[str, int]:
        return {store: self.repo.count(store) for store in STORES}
