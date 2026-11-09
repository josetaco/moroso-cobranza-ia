"""Estado de la gestión de cobranza por conversación (clave = session_id / thread_id).

Limitación conocida: vive en memoria del proceso. Para escalar a varias
instancias habría que moverlo a Redis/Postgres.
"""
import uuid

from langchain_core.runnables import RunnableConfig

SESSIONS: dict = {}

CAMPOS_PUBLICOS = [
    "nombre",
    "producto",
    "total_deuda",
    "dias_mora",
    "segmento",
    "intencion_pago",
    "opcion_acordada",
    "fecha_promesa",
    "monto_promesa",
    "canal_pago",
    "resultado_gestion",
    "derivado",
    "proceso_completo",
]


def nuevo_estado() -> dict:
    return {
        # Verificación
        "dni": None,
        "fecha_nacimiento": None,
        "identidad_verificada": False,
        "intentos_verificacion": 0,
        # Cliente y deuda (solo los escribe la cartera/herramientas)
        "cliente_id": None,
        "nombre": None,
        "producto": None,
        "saldo_capital": None,
        "intereses": None,
        "moras": None,
        "gastos": None,
        "total_deuda": None,
        "dias_mora": None,
        "fecha_vencimiento": None,
        "segmento": None,
        "estado_cartera": None,
        # Gestión
        "intencion_pago": None,
        "motivo_dificultad": None,
        "opcion_acordada": None,
        "fecha_promesa": None,
        "monto_promesa": None,
        "canal_pago": None,
        "fecha_pago_reportado": None,
        # Resultado
        "resultado_gestion": None,
        "derivado": False,
        "proceso_completo": False,
        "alertas_internas": [],
    }


def nueva_sesion() -> str:
    sid = str(uuid.uuid4())
    SESSIONS[sid] = nuevo_estado()
    return sid


def obtener_estado(config: RunnableConfig) -> dict:
    """Recupera el estado de la conversación actual a partir del thread_id."""
    sid = config["configurable"]["thread_id"]
    return SESSIONS.setdefault(sid, nuevo_estado())


def enmascarar_dni(dni) -> str | None:
    if not dni:
        return None
    texto = str(dni).strip()
    return "****" + texto[-4:] if len(texto) >= 4 else "****"


def estado_publico(estado: dict) -> dict:
    """Estado seguro para enviar al frontend: sin PII sensible ni alertas internas."""
    publico = {campo: estado.get(campo) for campo in CAMPOS_PUBLICOS}
    publico["dni"] = enmascarar_dni(estado.get("dni"))
    return publico
