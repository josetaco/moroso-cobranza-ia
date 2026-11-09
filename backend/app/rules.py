"""Reglas de negocio de cobranza: validaciones, segmentos, opciones y cierre.

Este módulo no depende de LangChain ni de estado global: son funciones puras,
fáciles de probar. Los parámetros son de demo y deben validarse con el negocio.
"""
import re
import unicodedata
from datetime import date, datetime, timedelta

SEGMENTOS = ["preventiva", "temprana", "media", "tardia"]
ESTADOS_CARTERA = ["prejudicial", "judicial", "castigada"]
CANALES_PAGO = ["app", "banca_internet", "agente", "ventanilla", "transferencia"]
INTENCIONES = [
    "pago_hoy",
    "promesa_pago",
    "facilidades",
    "no_puede_pagar",
    "ya_pago",
    "no_reconoce",
]
MOTIVOS = ["desempleo", "salud", "familia", "ingresos", "disputa", "otro"]
OPCIONES_PAGO = ["pago_total", "plan_3", "plan_6"]

CAMPOS_VALIDOS = {
    "intencion_pago": INTENCIONES,
    "motivo_dificultad": MOTIVOS,
    "opcion_acordada": OPCIONES_PAGO,
    "canal_pago": CANALES_PAGO,
    "fecha_promesa": None,
    "monto_promesa": None,
    "fecha_pago_reportado": None,
}

CAMPOS_PROTEGIDOS = {
    "identidad_verificada",
    "intentos_verificacion",
    "cliente_id",
    "nombre",
    "producto",
    "saldo_capital",
    "intereses",
    "moras",
    "gastos",
    "total_deuda",
    "dias_mora",
    "fecha_vencimiento",
    "segmento",
    "estado_cartera",
    "resultado_gestion",
    "derivado",
    "proceso_completo",
    "alertas_internas",
}

CUOTA_MINIMA = 100.0
MONTO_DERIVACION = 20000.0
MAX_INTENTOS = 3
DIAS_PROMESA_MAX = 30
DIAS_PROMESA_TEMPRANA = 7

NORMALIZAR_INTENCION = {
    "pago hoy": "pago_hoy",
    "pago_hoy": "pago_hoy",
    "paga_hoy": "pago_hoy",
    "promesa": "promesa_pago",
    "promesa de pago": "promesa_pago",
    "promesa_pago": "promesa_pago",
    "facilidades": "facilidades",
    "facilidades de pago": "facilidades",
    "cuotas": "facilidades",
    "no puede pagar": "no_puede_pagar",
    "no_puede_pagar": "no_puede_pagar",
    "ya pague": "ya_pago",
    "ya pago": "ya_pago",
    "ya_pago": "ya_pago",
    "no reconoce": "no_reconoce",
    "no reconoce la deuda": "no_reconoce",
    "no_reconoce": "no_reconoce",
    "disputa": "no_reconoce",
}

NORMALIZAR_CANAL = {
    "app": "app",
    "aplicativo": "app",
    "banca internet": "banca_internet",
    "banca por internet": "banca_internet",
    "banca_internet": "banca_internet",
    "agente": "agente",
    "ventanilla": "ventanilla",
    "transferencia": "transferencia",
    "transferencia interbancaria": "transferencia",
}

NORMALIZAR_MOTIVO = {
    "desempleo": "desempleo",
    "sin trabajo": "desempleo",
    "salud": "salud",
    "enfermedad": "salud",
    "familia": "familia",
    "ingresos": "ingresos",
    "disputa": "disputa",
    "no reconoce": "disputa",
    "otro": "otro",
}


def _sin_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def parse_fecha(valor) -> str | None:
    """Devuelve la fecha en ISO (YYYY-MM-DD) o None si no es válida."""
    if valor is None:
        return None
    texto = _sin_tildes(str(valor).strip().lower())
    if not texto:
        return None
    if texto in ("hoy", "ahora"):
        return date.today().isoformat()
    if texto in ("manana", "mañana"):
        return (date.today() + timedelta(days=1)).isoformat()
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            continue
    return None


def es_dni_valido(valor: str) -> bool:
    """DNI peruano: exactamente 8 dígitos."""
    return bool(re.fullmatch(r"\d{8}", str(valor).strip()))


def es_monto_valido(valor) -> bool:
    try:
        return float(str(valor).replace(",", ".").replace("S/", "").strip()) > 0
    except (TypeError, ValueError):
        return False


def normalizar_valor(campo: str, valor: str) -> str:
    """Convierte variantes (tildes, género, espacios) al valor canónico."""
    v = _sin_tildes(str(valor).strip().lower()).replace("-", "_")
    if campo == "intencion_pago":
        return NORMALIZAR_INTENCION.get(v, v)
    if campo == "canal_pago":
        return NORMALIZAR_CANAL.get(v, v)
    if campo == "motivo_dificultad":
        return NORMALIZAR_MOTIVO.get(v, v)
    if campo == "opcion_acordada":
        return v.replace(" ", "_")
    return v


def calcular_segmento(dias_mora: int) -> str:
    dias = int(dias_mora)
    if dias <= 0:
        return "preventiva"
    if dias <= 30:
        return "temprana"
    if dias <= 90:
        return "media"
    return "tardia"


def calcular_opciones_pago(estado: dict) -> dict:
    """Devuelve las opciones autorizadas según segmento y deuda."""
    total = estado.get("total_deuda")
    dias = estado.get("dias_mora")
    cartera = estado.get("estado_cartera")

    if total is None or dias is None:
        return {"status": "error", "mensaje": "No hay deuda cargada para este cliente."}

    total = float(total)
    dias = int(dias)
    segmento = calcular_segmento(dias)

    if cartera in ("judicial", "castigada"):
        return {
            "status": "ok",
            "segmento": segmento,
            "opciones": [],
            "alertas": [f"cartera_{cartera}"],
            "derivado": True,
        }

    if total > MONTO_DERIVACION:
        return {
            "status": "ok",
            "segmento": segmento,
            "opciones": [],
            "alertas": ["monto_supera_umbral"],
            "derivado": True,
        }

    opciones = [{
        "id": "pago_total",
        "descripcion": "Pago total hoy",
        "cuotas": 1,
        "monto_inicial": round(total, 2),
        "monto_cuota": round(total, 2),
    }]

    if total >= 500 and segmento in ("media", "tardia"):
        planes = [(3, 0.30)] if segmento == "media" else [(3, 0.30), (6, 0.20)]
        for cuotas, inicial_pct in planes:
            inicial = round(total * inicial_pct, 2)
            cuota = round((total - inicial) / (cuotas - 1), 2)
            if cuota >= CUOTA_MINIMA:
                opciones.append({
                    "id": f"plan_{cuotas}",
                    "descripcion": f"{cuotas} cuotas",
                    "cuotas": cuotas,
                    "monto_inicial": inicial,
                    "monto_cuota": cuota,
                })

    return {
        "status": "ok",
        "segmento": segmento,
        "opciones": opciones,
        "alertas": [],
        "derivado": False,
    }


def campos_requeridos(estado: dict) -> list[str]:
    """Campos que deben estar completos antes de cerrar la gestión."""
    requeridos = ["identidad_verificada", "intencion_pago"]
    intencion = estado.get("intencion_pago")

    if intencion in ("pago_hoy", "promesa_pago"):
        requeridos += ["fecha_promesa", "monto_promesa", "canal_pago"]
    elif intencion == "facilidades":
        requeridos += ["opcion_acordada", "fecha_promesa", "monto_promesa", "canal_pago"]
    elif intencion == "ya_pago":
        requeridos += ["fecha_pago_reportado", "monto_promesa", "canal_pago"]
    elif intencion in ("no_puede_pagar", "no_reconoce"):
        requeridos += ["motivo_dificultad"]

    return requeridos


def calcular_resultado_gestion(estado: dict) -> tuple[str, list[str], bool]:
    """Devuelve (resultado, alertas, derivado)."""
    if not estado.get("identidad_verificada"):
        return "derivado", ["identidad_no_verificada"], True

    if estado.get("estado_cartera") in ("judicial", "castigada"):
        return "derivado", [f"cartera_{estado['estado_cartera']}"], True

    if estado.get("total_deuda") and float(estado["total_deuda"]) > MONTO_DERIVACION:
        return "derivado", ["monto_supera_umbral"], True

    intencion = estado.get("intencion_pago")
    if intencion == "no_reconoce":
        return "derivado", ["disputa_del_cliente"], True
    if intencion == "no_puede_pagar":
        if estado.get("motivo_dificultad") == "salud":
            return "derivado", ["caso_vulnerable"], True
        return "sin_acuerdo", ["sin_capacidad_de_pago"], False
    if intencion == "pago_hoy":
        return "pago_hoy", [], False
    if intencion == "promesa_pago":
        return "promesa_pago", [], False
    if intencion == "facilidades":
        return "acuerdo_pago", [], False
    if intencion == "ya_pago":
        return "pago_reportado", [], False
    return "sin_acuerdo", ["intencion_no_definida"], False


def validar_compromiso(estado: dict, fecha, monto, canal) -> tuple[bool, str, dict]:
    """Valida fecha, monto y canal de un compromiso de pago."""
    if not estado.get("identidad_verificada"):
        return False, "Primero verifica la identidad.", {}

    fecha_iso = parse_fecha(fecha)
    if not fecha_iso:
        return False, "La fecha no es válida. Usa el formato DD/MM/AAAA.", {}

    try:
        monto_f = float(str(monto).replace(",", ".").replace("S/", "").strip())
    except (TypeError, ValueError):
        return False, "El monto no es válido.", {}

    if monto_f <= 0:
        return False, "El monto debe ser mayor a cero.", {}

    total = float(estado.get("total_deuda") or 0)
    if monto_f > total + 0.01:
        return False, "El monto no puede superar la deuda total.", {}

    canal_n = normalizar_valor("canal_pago", canal)
    if canal_n not in CANALES_PAGO:
        return False, f"Canal no válido. Opciones: {', '.join(CANALES_PAGO)}.", {}

    hoy = date.today()
    fecha_d = date.fromisoformat(fecha_iso)
    if fecha_d < hoy:
        return False, "La fecha no puede ser anterior a hoy.", {}

    max_dias = DIAS_PROMESA_MAX
    if estado.get("intencion_pago") == "promesa_pago" and estado.get("segmento") == "temprana":
        max_dias = DIAS_PROMESA_TEMPRANA
    if fecha_d > hoy + timedelta(days=max_dias):
        return False, f"La fecha no puede superar {max_dias} días.", {}

    if estado.get("intencion_pago") == "pago_hoy" and fecha_d != hoy:
        return False, "Para pago hoy, la fecha debe ser hoy.", {}

    if estado.get("intencion_pago") == "pago_hoy" and abs(monto_f - total) > 0.01:
        return False, "Para pago hoy debes registrar el monto total de la deuda.", {}

    if estado.get("intencion_pago") == "facilidades":
        opcion = estado.get("opcion_acordada")
        disponibles = calcular_opciones_pago(estado).get("opciones", [])
        elegida = next((o for o in disponibles if o["id"] == opcion), None)
        if not elegida:
            return False, "Primero elige una opción de pago válida.", {}
        if abs(monto_f - elegida["monto_inicial"]) > 0.01:
            return (
                False,
                f"El pago inicial de esta opción es S/ {elegida['monto_inicial']:.2f}.",
                {},
            )

    return True, "Compromiso válido.", {
        "fecha": fecha_iso,
        "monto": round(monto_f, 2),
        "canal": canal_n,
    }
