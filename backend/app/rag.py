"""Ingesta de políticas y vector store (RAG) con Gemini."""
import logging
import os
from pathlib import Path

import pandas as pd
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings

logger = logging.getLogger("moroso.rag")

DEFAULT_KB_PATH = Path(__file__).resolve().parent.parent / "data" / "politicas_cobranza.csv"

_vector_store = None


def cargar_documentos(ruta_csv) -> list[Document]:
    """Lee el CSV y convierte cada fila en un Document con metadata genérica."""
    df = pd.read_csv(ruta_csv)
    documentos = []
    for _, fila in df.iterrows():
        metadata = {}
        for columna in df.columns:
            if columna == "texto":
                continue
            if pd.notna(fila[columna]) and str(fila[columna]).strip():
                metadata[columna] = str(fila[columna]).strip()
        documentos.append(Document(page_content=str(fila["texto"]), metadata=metadata))
    return documentos


def _embeddings():
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Falta GOOGLE_API_KEY (o GEMINI_API_KEY). "
            "Copia backend/.env.example a backend/.env y completa la clave."
        )
    return GoogleGenerativeAIEmbeddings(
        model=os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001"),
        google_api_key=api_key,
    )


def init_vector_store(embeddings=None, ruta_csv=None):
    """Construye el vector store en memoria. Se llama una vez al arrancar."""
    global _vector_store
    ruta = Path(ruta_csv or os.getenv("KB_PATH", DEFAULT_KB_PATH))
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encontró la base de conocimiento en {ruta}. "
            "Copia tu politicas_cobranza.csv a backend/data/."
        )
    embeddings = embeddings or _embeddings()
    documentos = cargar_documentos(ruta)
    _vector_store = InMemoryVectorStore(embeddings)
    ids = _vector_store.add_documents(documents=documentos)
    logger.info("Vector store listo: %d documentos desde %s", len(ids), ruta.name)
    return _vector_store


def get_vector_store():
    if _vector_store is None:
        raise RuntimeError("El vector store no está inicializado.")
    return _vector_store
