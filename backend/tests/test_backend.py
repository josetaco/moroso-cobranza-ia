"""Pruebas sin llamadas a Gemini (embeddings y agente simulados)."""
import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import DeterministicFakeEmbedding

from app import cartera, main, rag
from app.rules import (
    calcular_opciones_pago,
    calcular_segmento,
    es_dni_valido,
    normalizar_valor,
)
from app.state import SESSIONS, estado_publico, nueva_sesion
from app.tools import (
    actualizar_estado,
    calcular_opciones_pago as tool_opciones,
    consultar_base_documental,
    consultar_deuda,
    finalizar_gestion,
    registrar_compromiso,
    verificar_identidad,
)


@pytest.fixture
def cartera_csv(tmp_path):
    ruta = tmp_path / "cartera.csv"
    ruta.write_text(
        "cliente_id,dni,fecha_nacimiento,nombre,producto,saldo_capital,intereses,moras,gastos,total_deuda,dias_mora,fecha_vencimiento,estado_cartera\n"
        "CLI001,12345678,1990-01-01,Ana Torres,credito_consumo,1000,100,50,50,1200,45,2026-09-15,prejudicial\n"
        "CLI002,87654321,1985-05-05,Luis Perez,credito_consumo,25000,1000,500,500,27000,150,2026-06-01,judicial\n",
        encoding="utf-8",
    )
    return ruta


@pytest.fixture(autouse=True)
def configurar_cartera(cartera_csv):
    cartera.init_cartera(cartera_csv)


@pytest.fixture
def kb_csv(tmp_path):
    ruta = tmp_path / "politicas.csv"
    ruta.write_text(
        "texto,tema,segmento,producto\n"
        "El fraccionamiento permite pagar en cuotas.,fraccionamiento,media,todos\n"
        "Los canales de pago son app y banca por internet.,canales_pago,todos,todos\n",
        encoding="utf-8",
    )
    return ruta


def cfg(sid):
    return {"configurable": {"thread_id": sid}}


def test_reglas():
    assert es_dni_valido("12345678") and not es_dni_valido("1234")
    assert normalizar_valor("intencion_pago", "Ya pagué") == "ya_pago"
    assert normalizar_valor("canal_pago", "Banca por internet") == "banca_internet"
    assert calcular_segmento(0) == "preventiva"
    assert calcular_segmento(15) == "temprana"
    assert calcular_segmento(45) == "media"
    assert calcular_segmento(120) == "tardia"

    opciones = calcular_opciones_pago({
        "total_deuda": 1200,
        "dias_mora": 45,
        "estado_cartera": "prejudicial",
    })
    assert opciones["segmento"] == "media"
    ids = [o["id"] for o in opciones["opciones"]]
    assert "plan_3" in ids
    plan = next(o for o in opciones["opciones"] if o["id"] == "plan_3")
    assert plan["monto_inicial"] == 360.0


def test_identidad_y_deuda():
    s = nueva_sesion()
    r = json.loads(verificar_identidad.invoke(
        {"dni": "12345678", "fecha_nacimiento": "01/01/1990"}, config=cfg(s)
    ))
    assert r["status"] == "ok"
    assert SESSIONS[s]["identidad_verificada"] is True
    assert SESSIONS[s]["total_deuda"] == 1200.0

    deuda = json.loads(consultar_deuda.invoke({}, config=cfg(s)))
    assert deuda["status"] == "ok" and deuda["total_deuda"] == 1200.0


def test_no_revela_deuda_sin_identidad():
    s = nueva_sesion()
    r = json.loads(consultar_deuda.invoke({}, config=cfg(s)))
    assert r["status"] == "error"


def test_tres_intentos_deriva():
    s = nueva_sesion()
    for _ in range(3):
        json.loads(verificar_identidad.invoke(
            {"dni": "00000000", "fecha_nacimiento": "01/01/1990"}, config=cfg(s)
        ))
    assert SESSIONS[s]["derivado"] is True
    assert SESSIONS[s]["proceso_completo"] is True


def test_campos_protegidos():
    s = nueva_sesion()
    r = json.loads(actualizar_estado.invoke(
        {"campo": "total_deuda", "valor": "0"}, config=cfg(s)
    ))
    assert r["status"] == "error"
    r = json.loads(actualizar_estado.invoke(
        {"campo": "intencion_pago", "valor": "inventado"}, config=cfg(s)
    ))
    assert r["status"] == "error"


def test_flujo_acuerdo():
    s = nueva_sesion()
    verificar_identidad.invoke(
        {"dni": "12345678", "fecha_nacimiento": "01/01/1990"}, config=cfg(s)
    )
    actualizar_estado.invoke(
        {"campo": "intencion_pago", "valor": "facilidades"}, config=cfg(s)
    )
    opciones = json.loads(tool_opciones.invoke({}, config=cfg(s)))
    plan = next(o for o in opciones["opciones"] if o["id"] == "plan_3")

    r = json.loads(actualizar_estado.invoke(
        {"campo": "opcion_acordada", "valor": "plan_3"}, config=cfg(s)
    ))
    assert r["status"] == "ok"

    fecha = (date.today() + timedelta(days=5)).strftime("%d/%m/%Y")
    r = json.loads(registrar_compromiso.invoke(
        {"fecha": fecha, "monto": str(plan["monto_inicial"]), "canal": "app"},
        config=cfg(s),
    ))
    assert r["status"] == "ok"

    r = json.loads(finalizar_gestion.invoke({"usuario_confirmo": True}, config=cfg(s)))
    assert r["status"] == "ok" and r["resultado_gestion"] == "acuerdo_pago"
    assert SESSIONS[s]["proceso_completo"] is True


def test_flujo_pago_hoy():
    s = nueva_sesion()
    verificar_identidad.invoke(
        {"dni": "12345678", "fecha_nacimiento": "01/01/1990"}, config=cfg(s)
    )
    actualizar_estado.invoke(
        {"campo": "intencion_pago", "valor": "pago_hoy"}, config=cfg(s)
    )
    r = json.loads(registrar_compromiso.invoke(
        {"fecha": "hoy", "monto": "1200", "canal": "app"}, config=cfg(s)
    ))
    assert r["status"] == "ok"
    r = json.loads(finalizar_gestion.invoke({"usuario_confirmo": True}, config=cfg(s)))
    assert r["status"] == "ok" and r["resultado_gestion"] == "pago_hoy"


def test_flujo_ya_pago():
    s = nueva_sesion()
    verificar_identidad.invoke(
        {"dni": "12345678", "fecha_nacimiento": "01/01/1990"}, config=cfg(s)
    )
    actualizar_estado.invoke(
        {"campo": "intencion_pago", "valor": "ya_pago"}, config=cfg(s)
    )
    ayer = (date.today() - timedelta(days=1)).strftime("%d/%m/%Y")
    assert json.loads(actualizar_estado.invoke(
        {"campo": "fecha_pago_reportado", "valor": ayer}, config=cfg(s)
    ))["status"] == "ok"
    assert json.loads(actualizar_estado.invoke(
        {"campo": "monto_promesa", "valor": "1200"}, config=cfg(s)
    ))["status"] == "ok"
    assert json.loads(actualizar_estado.invoke(
        {"campo": "canal_pago", "valor": "app"}, config=cfg(s)
    ))["status"] == "ok"

    r = json.loads(finalizar_gestion.invoke({"usuario_confirmo": True}, config=cfg(s)))
    assert r["status"] == "ok" and r["resultado_gestion"] == "pago_reportado"


def test_derivacion_disputa():
    s = nueva_sesion()
    verificar_identidad.invoke(
        {"dni": "12345678", "fecha_nacimiento": "01/01/1990"}, config=cfg(s)
    )
    actualizar_estado.invoke(
        {"campo": "intencion_pago", "valor": "no_reconoce"}, config=cfg(s)
    )
    actualizar_estado.invoke(
        {"campo": "motivo_dificultad", "valor": "disputa"}, config=cfg(s)
    )
    r = json.loads(finalizar_gestion.invoke({"usuario_confirmo": True}, config=cfg(s)))
    assert r["status"] == "ok" and r["resultado_gestion"] == "derivado"
    assert SESSIONS[s]["derivado"] is True


def test_rag(kb_csv):
    rag.init_vector_store(
        embeddings=DeterministicFakeEmbedding(size=32), ruta_csv=kb_csv
    )
    s = nueva_sesion()
    SESSIONS[s].update({
        "identidad_verificada": True,
        "segmento": "media",
        "producto": "credito_consumo",
    })
    r = json.loads(consultar_base_documental.invoke(
        {"pregunta": "fraccionamiento"}, config=cfg(s)
    ))
    assert r["status"] == "ok" and r["resultados"]
    assert all(x["metadata"].get("segmento") in ("media", "todos") for x in r["resultados"])


def test_estado_publico():
    s = nueva_sesion()
    SESSIONS[s].update({
        "dni": "12345678",
        "total_deuda": 100,
        "intentos_verificacion": 2,
        "alertas_internas": ["x"],
    })
    publico = estado_publico(SESSIONS[s])
    assert publico["dni"] == "****5678"
    assert "intentos_verificacion" not in publico
    assert "alertas_internas" not in publico


class _Msg:
    content = "Hola, soy Moroso."


class _FakeAgent:
    def invoke(self, payload, config):
        return {"messages": [_Msg()]}


def test_api(monkeypatch):
    monkeypatch.setattr(main, "init_cartera", lambda: None)
    monkeypatch.setattr(main, "init_vector_store", lambda: None)
    monkeypatch.setattr(main, "build_agent", lambda: _FakeAgent())

    with TestClient(main.app) as client:
        assert client.get("/health").json() == {"status": "ok", "agente_listo": True}
        r = client.post("/chat", json={"message": "Hola"})
        assert r.status_code == 200
        body = r.json()
        assert body["reply"].startswith("Hola")
        assert body["session_id"] and body["proceso_completo"] is False
        assert body["estado"]["dni"] is None
        assert "intentos_verificacion" not in body["estado"]
        assert client.post("/chat", json={"message": ""}).status_code == 422
        assert client.post(
            "/chat", json={"message": "x", "session_id": body["session_id"]}
        ).json()["session_id"] == body["session_id"]
