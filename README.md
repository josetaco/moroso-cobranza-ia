# Moroso

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/Google-Gemini-4285F4?logo=google&logoColor=white)](https://ai.google.dev/)
[![LangChain](https://img.shields.io/badge/LangChain-1.x-1C3C3C?logo=langchain&logoColor=white)](https://python.langchain.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
![Tests](https://img.shields.io/badge/tests-12%20passed-brightgreen)
![Demo](https://img.shields.io/badge/demo-local-blue)

Asistente virtual de **cobranza y recuperación de cartera** con IA generativa. Verifica la identidad del cliente, le informa su situación de deuda, ofrece alternativas de pago autorizadas, registra compromisos y deriva los casos complejos a un especialista.

> Demo con datos ficticios. No procesa pagos reales ni toma decisiones legales. Antes de usarlo en producción hay que validar las políticas con el negocio, integrar el core bancario y cumplir la normativa aplicable.

| | Enlace |
|---|---|
| **Repositorio** | [github.com/josetaco/moroso-cobranza-ia](https://github.com/josetaco/moroso-cobranza-ia) |
| API local | http://localhost:8080 |
| Documentación interactiva | http://localhost:8080/docs |
| Frontend local | http://localhost:3000 |
| API key de Gemini | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |

---

## Qué puede hacer Moroso

- **Verificar identidad** con DNI y fecha de nacimiento antes de revelar cualquier dato de deuda.
- **Consultar y explicar** el saldo, intereses, moras, gastos, días de atraso y vencimiento.
- **Clasificar la intención** del cliente: pago hoy, promesa, facilidades, ya pagó, no puede pagar o no reconoce la deuda.
- **Ofrecer solo alternativas autorizadas** por reglas de negocio: pago total, promesa o planes de 3/6 cuotas.
- **Registrar compromisos** con fecha, monto y canal validados.
- **Responder dudas de política** con RAG: canales, derechos, intereses, fraccionamiento, privacidad y casos especiales.
- **Derivar a un especialista** ante disputas, fraude, vulnerabilidad, cartera judicial/castigada o montos altos.
- **Proteger la información**: DNI enmascarado, estado público sin PII sensible y sin alertas internas.

### Demo rápida

Ejecuta el proyecto en local y prueba con:

| Cliente | DNI | Fecha de nacimiento | Caso |
|---|---|---|---|
| Ana Torres | `70123456` | `15/03/1987` | Mora media, deuda S/ 3,780.50, plan de 3 cuotas |

Más casos en [Datos de prueba](#datos-de-prueba).

---

## Problema que resuelve

La cobranza manual repite las mismas preguntas, no siempre aplica las mismas alternativas de pago y deja sin trazabilidad los compromisos. Moroso automatiza el primer contacto: verifica identidad, explica la deuda, ofrece solo las opciones permitidas por política, registra el compromiso y deriva los casos que requieren criterio humano.

**Público objetivo:**
- Clientes con créditos de consumo, hipotecario o tarjeta en mora.
- Equipos de cobranza que reciben casos ya clasificados.

---


## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Modelo de lenguaje | [Google Gemini](https://ai.google.dev/) (`gemini-3.6-flash` por defecto) |
| Embeddings | [Google Gemini](https://ai.google.dev/gemini-api/docs/embeddings) (`models/gemini-embedding-001`) |
| Agente | [LangChain](https://python.langchain.com/) 1.x (`create_agent`) + [LangGraph](https://langchain-ai.github.io/langgraph/) (`InMemorySaver`) |
| RAG | [LangChain](https://python.langchain.com/) (`GoogleGenerativeAIEmbeddings`, `InMemoryVectorStore`) |
| Backend | [Python](https://www.python.org/) 3.11+, [FastAPI](https://fastapi.tiangolo.com/), Uvicorn, Pandas |
| Frontend | [Next.js](https://nextjs.org/) 16, React 19, react-markdown |
| Despliegue | [Google Cloud Run](https://cloud.google.com/run), Secret Manager, [Vercel](https://vercel.com/) |
| Pruebas | [Pytest](https://docs.pytest.org/) (sin llamadas a Gemini: embeddings y agente simulados) |

---

## Estructura del código

```
moroso-cobranza-ia/
├── backend/
│   ├── app/
│   │   ├── main.py               API FastAPI: /chat y /health
│   │   ├── agent.py              Prompt del sistema y construcción del agente
│   │   ├── tools.py              Herramientas del agente
│   │   ├── cartera.py            Adaptador de cartera (simula el core bancario)
│   │   ├── rag.py                Ingesta del CSV y vector store
│   │   ├── rules.py              Segmentos, validaciones, opciones y derivación
│   │   └── state.py              Estado del caso por sesión y estado público
│   ├── data/
│   │   ├── cartera_demo.csv      Clientes y deudas ficticias
│   │   └── politicas_cobranza.csv Base de conocimiento (RAG)
│   ├── tests/test_backend.py     Pruebas automáticas
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── page.js               Chat, historial y panel Mi caso
│   │   ├── layout.js
│   │   └── globals.css           Estilos (modo claro/oscuro y móvil)
│   └── package.json
```

---

## Flujo conversacional

1. **Saludo y aviso:** el agente se presenta como asistente de cobranza.
2. **Verificación:** pide DNI y fecha de nacimiento (DD/MM/AAAA). No revela la deuda hasta verificar. Máximo 3 intentos.
3. **Deuda:** muestra producto, deuda total, días de mora y vencimiento.
4. **Diagnóstico:** el cliente indica si ya pagó, puede pagar hoy, necesita facilidades, no puede pagar o no reconoce la deuda.
5. **Alternativas:**
   - Pago hoy: canales y registro del compromiso.
   - Promesa: fecha, monto y canal validados.
   - Facilidades: opciones calculadas por reglas, con pago inicial y cuotas.
   - Ya pagó: registra fecha, monto y canal; queda en validación.
   - No puede pagar: captura el motivo; si hay vulnerabilidad, deriva.
   - No reconoce: detiene la cobranza y deriva a disputa.
6. **Resumen:** muestra los datos reales guardados y pide confirmación.
7. **Cierre:** resultado de la gestión, compromiso y siguientes pasos.

---

## Herramientas

| Herramienta | Qué hace |
|---|---|
| `verificar_identidad` | Valida DNI + fecha de nacimiento contra la cartera. No revela deuda si falla. |
| `consultar_deuda` | Devuelve saldo, intereses, moras, gastos, vencimiento y segmento. |
| `actualizar_estado` | Guarda intención, motivo, canal, fechas y montos. Rechaza campos protegidos. |
| `calcular_opciones_pago` | Devuelve solo las opciones autorizadas para el segmento. |
| `registrar_compromiso` | Valida fecha, monto y canal; registra la promesa o el acuerdo. |
| `resumen_gestion` | Devuelve el resumen real antes de cerrar. |
| `finalizar_gestion` | Cierra la gestión y devuelve resultado, compromiso y próximos pasos. |
| `derivar_a_asesor` | Deriva disputas, fraude, vulnerabilidad o solicitud del cliente. |
| `fuera_de_dominio` | Responde temas ajenos y retoma la conversación. |
| `consultar_base_documental` | RAG sobre políticas, canales, derechos y casos especiales. |

### Reglas de negocio (demo)

| Segmento | Días de mora | Opciones |
|---|---|---|
| Preventiva | 0 | Pago total |
| Temprana | 1–30 | Pago total o promesa dentro de 7 días |
| Media | 31–90 | Pago total o hasta 3 cuotas, inicial ≥ 30% |
| Tardía | > 90 | Hasta 6 cuotas, inicial ≥ 20% |

- Cuota mínima: S/ 100.
- Deuda mayor a S/ 20,000: derivar.
- Cartera judicial o castigada: derivar.
- Los parámetros están en `rules.py` y deben validarse con el negocio.

---

## Base de conocimiento y cartera

- `backend/data/cartera_demo.csv`: clientes ficticios con producto, saldo, intereses, moras, gastos, días de mora y estado de cartera.
- `backend/data/politicas_cobranza.csv`: políticas de canales de pago, intereses, fraccionamiento, derechos, privacidad, reclamos, vulnerabilidad, fraude y cobranza judicial.

`rag.py` convierte todas las columnas del CSV (excepto `texto`) en metadata y filtra por `segmento` y `producto`.

---

## API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | `{"status": "ok", "agente_listo": true}` |
| `POST` | `/chat` | Envía un mensaje al agente |
| `GET` | `/docs` | Swagger |

**Petición:**
```json
{ "message": "Hola, quiero revisar mi deuda" }
```

**Respuesta:**
```json
{
  "session_id": "3f2a9c1e-...",
  "reply": "Hola, soy Moroso...",
  "estado": {
    "dni": null,
    "nombre": null,
    "producto": null,
    "total_deuda": null,
    "dias_mora": null,
    "segmento": null,
    "intencion_pago": null,
    "fecha_promesa": null,
    "monto_promesa": null,
    "resultado_gestion": null,
    "derivado": false,
    "proceso_completo": false
  },
  "proceso_completo": false
}
```

El estado público no incluye fecha de nacimiento, alertas internas ni el DNI completo (se enmascara como `****5678`).

---

## Ejecución local

### Requisitos

- Python 3.11 o superior
- Node.js 20.9 o superior
- Una API key de Google AI Studio / Gemini

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # En Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env               # Completa GOOGLE_API_KEY
uvicorn app.main:app --reload --port 8080
```

La API queda en http://localhost:8080 y la documentación en http://localhost:8080/docs.

> Si no tienes la API key, las pruebas igual funcionan porque usan embeddings y agente simulados. Para levantar la app sí necesitas `GOOGLE_API_KEY`.
>
> La capa gratuita de Gemini limita a 5 solicitudes por minuto. Si recibes un error `429`, espera un minuto o habilita facturación. El modelo por defecto es `gemini-3.6-flash`; puedes cambiarlo a `gemini-3.8-flash` si está disponible en tu cuenta.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local         # NEXT_PUBLIC_API_URL=http://localhost:8080
npm run dev
```

La interfaz queda en http://localhost:3000.

### Pruebas

```bash
cd backend
pytest -q
```

---

## Estado del proyecto

- Backend y frontend funcionales.
- Flujo completo validado con Gemini: identificación, deuda, RAG, plan de 3 cuotas y cierre como `acuerdo_pago`.
- 12 pruebas automáticas aprobadas.
- Demo local con datos ficticios; el despliegue público queda pendiente.
- Para producción: autenticación, rate limiting, persistencia, auditoría y revisión legal.

---

## Datos de prueba

| Cliente | DNI | Fecha de nacimiento | Caso |
|---|---|---|---|
| Ana Torres | 70123456 | 15/03/1987 | Mora media, plan de 3 cuotas |
| Luis Pérez | 71234567 | 02/11/1979 | Mora tardía, plan de 3 o 6 cuotas |
| María Gómez | 72345678 | 21/07/1992 | Mora temprana, pago total |
| Carlos Ruiz | 73456789 | 10/01/1985 | Preventiva, sin mora |
| José Díaz | 74567890 | 25/05/1990 | Mora tardía, opciones de pago |
| Rosa Vargas | 75678901 | 30/09/1982 | Cartera judicial, derivar |
| Diego Flores | 76789012 | 05/12/1995 | Deuda menor a S/ 500, solo pago total |
| Patricia Rojas | 77890123 | 18/04/1975 | Cartera castigada, derivar |

---

## Despliegue

### Backend en Google Cloud Run

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com

tr -d ' \r\n' < api_key.txt | gcloud secrets create google-api-key --data-file=-

PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding google-api-key \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud run deploy moroso-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-secrets GOOGLE_API_KEY=google-api-key:latest \
  --set-env-vars "MODEL_NAME=gemini-3.6-flash,EMBEDDING_MODEL=models/gemini-embedding-001,ALLOWED_ORIGIN_REGEX=https://.*\.vercel\.app" \
  --memory 1Gi --timeout 120 \
  --min-instances 1 --max-instances 1
```

- `--max-instances 1`: el estado de cada conversación vive en memoria.
- `--min-instances 1`: evita arranques en frío y recalcular embeddings.

### Frontend en Vercel

1. Importar el repositorio en Vercel.
2. **Root Directory:** `frontend`.
3. **Variable de entorno:** `NEXT_PUBLIC_API_URL` con la URL de Cloud Run.
4. **Deploy.**

---

## Seguridad y límites

- Verificar identidad antes de mencionar cualquier deuda.
- No revelar información a terceros ni pedir contraseñas, OTP o número completo de tarjeta.
- No amenazar, no hostigar y respetar horarios y frecuencia de contacto.
- Ofrecer solo las opciones que devuelve la herramienta.
- Detener la gestión ante disputa, fraude, fallecimiento, suplantación o vulnerabilidad.
- Enmascarar DNI y no registrar PII en logs.
- Para producción: autenticación, rate limiting, expiración de sesión, auditoría, cifrado y revisión legal.
- El estado y el vector store viven en memoria; para escalar usar Redis/Postgres y un vector store persistente.
- La cartera CSV es una simulación; en producción se reemplaza por la API del core bancario.

---

## Roadmap

- Integración con WhatsApp Business y traspaso a la bandeja del ejecutivo.
- Panel para ejecutivos con casos derivados y su estado.
- Validación automática de comprobantes de pago.
- Estado persistente en Firestore/Redis.
- Vector store persistente (pgvector, Vertex AI Vector Search o Chroma).
- Métricas: contacto efectivo, promesas, cumplimiento y derivaciones.

---

## Autor

**@josetaco** — [github.com/josetaco](https://github.com/josetaco)

## Licencia

Proyecto publicado como demo educativa. Todos los derechos reservados. Para uso comercial o adaptación a producción, contacta al autor.
