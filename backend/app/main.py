"""API FastAPI de Moroso."""
import logging
import os
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

from .agent import build_agent  # noqa: E402
from .cartera import init_cartera  # noqa: E402
from .rag import init_vector_store  # noqa: E402
from .state import SESSIONS, estado_publico, nuevo_estado  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("moroso")

resources: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Falla rápido si falta la API key o alguno de los CSV.
    init_cartera()
    init_vector_store()
    resources["agent"] = build_agent()
    logger.info("Moroso listo.")
    yield
    resources.clear()


app = FastAPI(title="Moroso API", version="1.0.0", lifespan=lifespan)

origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=os.getenv("ALLOWED_ORIGIN_REGEX") or None,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, max_length=64)


class ChatOut(BaseModel):
    session_id: str
    reply: str
    estado: dict
    proceso_completo: bool


def _texto(content) -> str:
    """El contenido del mensaje puede ser str o una lista de bloques."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return str(content or "")


@app.get("/")
def root():
    return {"servicio": "Moroso API", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {"status": "ok", "agente_listo": "agent" in resources}


@app.post("/chat", response_model=ChatOut)
def chat(body: ChatIn):
    agent = resources.get("agent")
    if agent is None:
        raise HTTPException(status_code=503, detail="El agente aún no está listo.")

    sid = body.session_id or str(uuid.uuid4())
    estado = SESSIONS.setdefault(sid, nuevo_estado())

    try:
        resultado = agent.invoke(
            {"messages": [{"role": "user", "content": body.message}]},
            config={"configurable": {"thread_id": sid}},
        )
    except Exception:
        logger.exception("Error invocando al agente (session=%s)", sid)
        raise HTTPException(status_code=502, detail="Error procesando tu mensaje. Intenta nuevamente.")

    reply = _texto(resultado["messages"][-1].content).strip()
    if not reply:
        reply = "Disculpa, no logré generar una respuesta clara. ¿Puedes reformular tu mensaje?"

    return ChatOut(
        session_id=sid,
        reply=reply,
        estado=estado_publico(estado),
        proceso_completo=bool(estado.get("proceso_completo")),
    )
