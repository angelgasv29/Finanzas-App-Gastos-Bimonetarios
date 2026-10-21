"""Arranca la aplicación: ``python main.py``."""

from __future__ import annotations

import argparse


def _parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gastos Bimonetarios (NiceGUI)")
    parser.add_argument("--host", default="127.0.0.1", help="interfaz de red")
    parser.add_argument("--port", type=int, default=8080, help="puerto")
    parser.add_argument("--db", default=None, help="ruta de la base SQLite")
    parser.add_argument("--workspace", default="personal", choices=("personal", "profesional"))
    parser.add_argument("--reload", action="store_true", help="recarga automática")
    return parser.parse_args()


def main() -> None:
    from app.ui.app import main as run

    args = _parse()
    run(
        args.db,
        workspace=args.workspace,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
