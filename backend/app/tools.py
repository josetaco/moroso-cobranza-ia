"""Herramientas del agente Moroso."""
import json
from datetime import date

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from .cartera import buscar_cliente
from .rag import get_vector_store
from .rules import (
    CAMPOS_PROTEGIDOS,
    CAMPOS_VALIDOS,
    MAX_INTENTOS,
    calcular_opciones_pago as _calcular_opciones_pago,
    calcular_resultado_gestion,
    calcular_segmento,
    campos_requeridos,
    es_dni_valido,
    es_monto_valido,
    normalizar_valor,
    parse_fecha,
    validar_compromiso,
)
from .state import obtener_estado

_PRODUCTO_KB = {
    "credito_consumo": "consumo",
    "credito_hipotecario": "hipotecario",
    "tarjeta_credito": "tarjeta",
}


def _error(mensaje: str) -> str:
    return json.dumps({"status": "error", "mensaje": mensaje}, ensure_ascii=False)


@tool
def verificar_identidad(dni: str, fecha_nacimiento: str, config: RunnableConfig) -> str:
    """
    Verifica la identidad del cliente con DNI (8 dígitos) y fecha de nacimiento
    (DD/MM/AAAA). No revela datos de deuda hasta que la verificación sea exitosa.
    """
    try:
        estado = obtener_estado(config)
        if estado.get("identidad_verificada"):
            return json.dumps({"status": "ok", "mensaje": "La identidad ya está verificada."})

        intentos = int(estado.get("intentos_verificacion") or 0) + 1
        estado["intentos_verificacion"] = intentos

        def fallo(mensaje: str) -> str:
            if intentos >= MAX_INTENTOS:
                estado["derivado"] = True
                estado["resultado_gestion"] = "derivado"
                estado["proceso_completo"] = True
                return json.dumps({
                    "status": "error",
                    "derivado_a_asesor": True,
                    "mensaje": "No fue posible verificar la identidad. Un asesor "
                               "continuará la gestión. No reveles datos de deuda.",
                }, ensure_ascii=False)
            return json.dumps({
                "status": "error",
                "mensaje": mensaje,
                "intentos_restantes": MAX_INTENTOS - intentos,
            }, ensure_ascii=False)

        if not es_dni_valido(dni):
            return fallo("El DNI debe tener exactamente 8 dígitos. Pide que lo repita.")

        fecha = parse_fecha(fecha_nacimiento)
        if not fecha:
            return fallo("La fecha no es válida. Pide que la repita en formato DD/MM/AAAA.")

        cliente = buscar_cliente(dni, fecha)
        if not cliente:
            return fallo("No pudimos verificar los datos. Pide que los revise y los repita.")

        estado.update({
            "dni": str(dni).strip(),
            "fecha_nacimiento": fecha,
            "identidad_verificada": True,
            "cliente_id": cliente["cliente_id"],
            "nombre": cliente["nombre"],
            "producto": cliente["producto"],
            "saldo_capital": cliente["saldo_capital"],
            "intereses": cliente["intereses"],
            "moras": cliente["moras"],
            "gastos": cliente["gastos"],
            "total_deuda": cliente["total_deuda"],
            "dias_mora": cliente["dias_mora"],
            "fecha_vencimiento": cliente["fecha_vencimiento"],
            "segmento": calcular_segmento(cliente["dias_mora"]),
            "estado_cartera": cliente["estado_cartera"],
        })
        return json.dumps({
            "status": "ok",
            "nombre": cliente["nombre"],
            "mensaje": "Identidad verificada. Ahora consulta la deuda antes de continuar.",
        }, ensure_ascii=False)
    except Exception as e:
        return _error(f"Error interno: {e}")


@tool
def consultar_deuda(config: RunnableConfig) -> str:
    """Devuelve el detalle de la deuda. Solo funciona con identidad verificada."""
    estado = obtener_estado(config)
    if not estado.get("identidad_verificada"):
        return _error("Primero verifica la identidad. No reveles datos de deuda.")
    return json.dumps({
        "status": "ok",
        "producto": estado.get("producto"),
        "saldo_capital": estado.get("saldo_capital"),
        "intereses": estado.get("intereses"),
        "moras": estado.get("moras"),
        "gastos": estado.get("gastos"),
        "total_deuda": estado.get("total_deuda"),
        "dias_mora": estado.get("dias_mora"),
        "fecha_vencimiento": estado.get("fecha_vencimiento"),
        "segmento": estado.get("segmento"),
        "estado_cartera": estado.get("estado_cartera"),
    }, ensure_ascii=False)


@tool
def actualizar_estado(campo: str, valor: str, config: RunnableConfig) -> str:
    """
    Guarda un dato de la gestión. Campos válidos: intencion_pago,
    motivo_dificultad, opcion_acordada, canal_pago, fecha_promesa,
    monto_promesa y fecha_pago_reportado. Rechaza campos protegidos.
    """
    try:
        estado = obtener_estado(config)

        if campo in CAMPOS_PROTEGIDOS:
            return _error(f"El campo '{campo}' es protegido y no puede modificarse manualmente.")
        if campo not in CAMPOS_VALIDOS:
            return _error(f"Campo '{campo}' no reconocido.")

        if not estado.get("identidad_verificada"):
            return _error("Primero verifica la identidad del cliente.")

        if campo in ("fecha_promesa", "fecha_pago_reportado"):
            fecha = parse_fecha(valor)
            if not fecha:
                return _error("La fecha no es válida. Usa el formato DD/MM/AAAA.")
            if campo == "fecha_pago_reportado" and date.fromisoformat(fecha) > date.today():
                return _error("La fecha del pago reportado no puede ser futura.")
            estado[campo] = fecha
            return json.dumps({"status": "ok", "campo_actualizado": campo, "valor": fecha})

        if campo == "monto_promesa":
            if not es_monto_valido(valor):
                return _error("El monto debe ser un número mayor a cero.")
            monto = float(str(valor).replace(",", ".").replace("S/", "").strip())
            estado[campo] = round(monto, 2)
            return json.dumps({"status": "ok", "campo_actualizado": campo, "valor": estado[campo]})

        valor_n = normalizar_valor(campo, valor)
        opciones = CAMPOS_VALIDOS[campo]
        if opciones and valor_n not in opciones:
            return _error(f"Valor '{valor}' no válido para '{campo}'. Opciones: {opciones}.")

        if campo == "opcion_acordada":
            disponibles = _calcular_opciones_pago(estado).get("opciones", [])
            if valor_n not in [o["id"] for o in disponibles]:
                return _error("La opción no está disponible para este caso. Llama a calcular_opciones_pago.")

        estado[campo] = valor_n
        return json.dumps({
            "status": "ok",
            "campo_actualizado": campo,
            "valor": valor_n,
        }, ensure_ascii=False)
    except Exception as e:
        return _error(f"Error interno: {e}")


@tool
def calcular_opciones_pago(config: RunnableConfig) -> str:
    """Calcula las opciones de pago autorizadas. Llamar antes de ofrecer cuotas."""
    estado = obtener_estado(config)
    if not estado.get("identidad_verificada"):
        return _error("Primero verifica la identidad.")
    return json.dumps(_calcular_opciones_pago(estado), ensure_ascii=False)


@tool
def registrar_compromiso(fecha: str, monto: str, canal: str, config: RunnableConfig) -> str:
    """Registra la fecha, el monto y el canal del compromiso de pago."""
    estado = obtener_estado(config)
    ok, mensaje, datos = validar_compromiso(estado, fecha, monto, canal)
    if not ok:
        return _error(mensaje)
    estado.update({
        "fecha_promesa": datos["fecha"],
        "monto_promesa": datos["monto"],
        "canal_pago": datos["canal"],
    })
    return json.dumps({
        "status": "ok",
        "compromiso": datos,
        "mensaje": "Compromiso registrado.",
    }, ensure_ascii=False)


@tool
def resumen_gestion(config: RunnableConfig) -> str:
    """Devuelve el resumen real de la gestión. Llamar SIEMPRE antes de finalizar."""
    estado = obtener_estado(config)
    return json.dumps({
        "nombre": estado.get("nombre"),
        "producto": estado.get("producto"),
        "total_deuda": estado.get("total_deuda"),
        "dias_mora": estado.get("dias_mora"),
        "segmento": estado.get("segmento"),
        "intencion_pago": estado.get("intencion_pago"),
        "opcion_acordada": estado.get("opcion_acordada"),
        "fecha_promesa": estado.get("fecha_promesa"),
        "monto_promesa": estado.get("monto_promesa"),
        "canal_pago": estado.get("canal_pago"),
        "fecha_pago_reportado": estado.get("fecha_pago_reportado"),
    }, ensure_ascii=False)


def _siguientes_pasos(resultado: str) -> list[str]:
    if resultado == "pago_hoy":
        return [
            "Realiza el pago hoy por el canal elegido.",
            "Conserva el comprobante y envíalo si te lo solicitan.",
        ]
    if resultado == "promesa_pago":
        return [
            "Realiza el pago en la fecha acordada.",
            "Recibirás un recordatorio antes del vencimiento.",
        ]
    if resultado == "acuerdo_pago":
        return [
            "Realiza el pago inicial en la fecha acordada.",
            "El saldo restante se distribuirá en las cuotas del plan.",
        ]
    if resultado == "pago_reportado":
        return [
            "Enviaremos tu pago a validación.",
            "La validación puede tardar hasta 48 horas hábiles.",
        ]
    if resultado == "sin_acuerdo":
        return [
            "Puedes volver a comunicarte para revisar nuevas alternativas.",
        ]
    return [
        "Un especialista revisará tu caso y se pondrá en contacto.",
    ]


@tool
def finalizar_gestion(usuario_confirmo: bool, config: RunnableConfig) -> str:
    """
    Cierra la gestión y devuelve el resultado. Acción sensible: solo llamar
    con usuario_confirmo=True, después de mostrar el resumen.
    """
    try:
        estado = obtener_estado(config)

        if not usuario_confirmo:
            return json.dumps({
                "status": "pendiente",
                "mensaje": "Falta confirmación explícita del usuario.",
            }, ensure_ascii=False)

        if not estado.get("identidad_verificada"):
            return _error("Primero verifica la identidad del cliente.")

        faltantes = [
            c for c in campos_requeridos(estado)
            if estado.get(c) in (None, False, "")
        ]
        if faltantes:
            return json.dumps({
                "status": "error",
                "mensaje": f"Faltan datos por guardar: {faltantes}. Pide esos datos y "
                           "usa actualizar_estado o registrar_compromiso antes de reintentar.",
            }, ensure_ascii=False)

        resultado, alertas, derivado = calcular_resultado_gestion(estado)
        estado["resultado_gestion"] = resultado
        estado["derivado"] = derivado
        estado["proceso_completo"] = True
        estado["alertas_internas"] = alertas

        compromiso = None
        if resultado in ("pago_hoy", "promesa_pago", "acuerdo_pago"):
            compromiso = {
                "fecha": estado.get("fecha_promesa"),
                "monto": estado.get("monto_promesa"),
                "canal": estado.get("canal_pago"),
            }
        elif resultado == "pago_reportado":
            compromiso = {
                "fecha": estado.get("fecha_pago_reportado"),
                "monto": estado.get("monto_promesa"),
                "canal": estado.get("canal_pago"),
            }

        return json.dumps({
            "status": "ok",
            "resultado_gestion": resultado,
            "compromiso": compromiso,
            "siguientes_pasos": _siguientes_pasos(resultado),
            "alertas_internas": alertas,
            "derivado_a_asesor": derivado,
        }, ensure_ascii=False)
    except Exception as e:
        return _error(f"Error al finalizar: {e}")


@tool
def derivar_a_asesor(motivo: str, config: RunnableConfig) -> str:
    """Deriva el caso a un especialista humano. Usar ante disputa, fraude o vulnerabilidad."""
    estado = obtener_estado(config)
    estado["derivado"] = True
    estado["resultado_gestion"] = "derivado"
    estado["proceso_completo"] = True
    estado["alertas_internas"] = list(estado.get("alertas_internas") or []) + [
        f"derivacion: {motivo}"
    ]
    return json.dumps({
        "status": "ok",
        "derivado_a_asesor": True,
        "mensaje": "Un especialista continuará la gestión. No reveles más datos de deuda.",
    }, ensure_ascii=False)


@tool
def fuera_de_dominio(consulta_usuario: str) -> str:
    """Usar cuando el mensaje del usuario no tiene relación con la cobranza."""
    return json.dumps({
        "mensaje_fallback": "Entiendo tu consulta, pero por ahora solo puedo ayudarte con la "
                            "gestión de tu crédito. Para otros temas, un asesor podrá contactarte. "
                            "¿Retomamos?"
    }, ensure_ascii=False)


@tool
def consultar_base_documental(pregunta: str, config: RunnableConfig) -> str:
    """
    Busca en la base de políticas de cobranza (RAG): canales de pago, derechos,
    intereses, fraccionamiento, reestructuración, casos especiales y normativa.
    """
    try:
        estado = obtener_estado(config)
        segmento = estado.get("segmento")
        producto = _PRODUCTO_KB.get(estado.get("producto"), estado.get("producto"))

        def _filtro(doc):
            if segmento and doc.metadata.get("segmento") not in (segmento, "todos"):
                return False
            if producto and doc.metadata.get("producto") not in (producto, "todos"):
                return False
            return True

        filtro = _filtro if (segmento or producto) else None
        resultados = get_vector_store().similarity_search(pregunta, k=3, filter=filtro)
        if not resultados:
            return json.dumps({"status": "sin_resultados"}, ensure_ascii=False)

        contenido = [
            {"texto": r.page_content, "metadata": r.metadata}
            for r in resultados
        ]
        return json.dumps({"status": "ok", "resultados": contenido}, ensure_ascii=False)
    except Exception as e:
        return _error(f"Error en búsqueda RAG: {e}")


TOOLS = [
    verificar_identidad,
    consultar_deuda,
    actualizar_estado,
    calcular_opciones_pago,
    registrar_compromiso,
    resumen_gestion,
    finalizar_gestion,
    derivar_a_asesor,
    fuera_de_dominio,
    consultar_base_documental,
]
