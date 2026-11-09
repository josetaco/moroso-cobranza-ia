"""Adaptador de cartera: simula el core bancario con un CSV ficticio.

En producción este módulo se reemplaza por el cliente de la API real.
"""
import logging
import os
from pathlib import Path

import pandas as pd

from .rules import parse_fecha

logger = logging.getLogger("moroso.cartera")

DEFAULT_CARTERA_PATH = Path(__file__).resolve().parent.parent / "data" / "cartera_demo.csv"

_clientes: list[dict] | None = None


def init_cartera(ruta_csv=None) -> list[dict]:
    """Carga la cartera demo en memoria. Se llama una vez al arrancar."""
    global _clientes
    ruta = Path(ruta_csv or os.getenv("CARTERA_PATH", DEFAULT_CARTERA_PATH))
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encontró la cartera en {ruta}. "
            "Copia tu cartera_demo.csv a backend/data/."
        )
    df = pd.read_csv(ruta, dtype={"dni": str})
    _clientes = df.to_dict("records")

    for cliente in _clientes:
        cliente["dni"] = str(cliente["dni"]).strip()
        cliente["fecha_nacimiento"] = str(cliente["fecha_nacimiento"]).strip()
        cliente["fecha_vencimiento"] = str(cliente["fecha_vencimiento"]).strip()
        cliente["dias_mora"] = int(cliente["dias_mora"])
        for campo in ("saldo_capital", "intereses", "moras", "gastos", "total_deuda"):
            cliente[campo] = float(cliente[campo])

    logger.info("Cartera demo lista: %d clientes desde %s", len(_clientes), ruta.name)
    return _clientes


def cargar_clientes() -> list[dict]:
    if _clientes is None:
        raise RuntimeError("La cartera no está inicializada.")
    return _clientes


def buscar_cliente(dni: str, fecha_nacimiento: str) -> dict | None:
    """Busca por DNI y fecha de nacimiento normalizada (YYYY-MM-DD)."""
    fecha = parse_fecha(fecha_nacimiento)
    if not fecha:
        return None
    for cliente in cargar_clientes():
        if cliente["dni"] == str(dni).strip() and cliente["fecha_nacimiento"] == fecha:
            return dict(cliente)
    return None


def obtener_cliente(cliente_id: str) -> dict | None:
    for cliente in cargar_clientes():
        if cliente["cliente_id"] == cliente_id:
            return dict(cliente)
    return None
