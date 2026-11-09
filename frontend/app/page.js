"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080"
).replace(/\/$/, "");

const CAMPOS = [
  { key: "dni", label: "DNI" },
  { key: "nombre", label: "Cliente" },
  { key: "producto", label: "Producto" },
  { key: "total_deuda", label: "Deuda total", tipo: "moneda" },
  { key: "dias_mora", label: "Días de mora" },
  { key: "segmento", label: "Segmento" },
  { key: "intencion_pago", label: "Intención de pago" },
  { key: "fecha_promesa", label: "Fecha de compromiso" },
  { key: "monto_promesa", label: "Monto comprometido", tipo: "moneda" },
  { key: "resultado_gestion", label: "Resultado" },
];

const SUGERENCIAS = [
  "Hola, quiero revisar mi deuda",
  "¿Cuáles son los canales de pago?",
  "Necesito facilidades de pago",
];

const VALORES = {
  credito_consumo: "Crédito de consumo",
  credito_hipotecario: "Crédito hipotecario",
  tarjeta_credito: "Tarjeta de crédito",
  preventiva: "Preventiva",
  temprana: "Temprana",
  media: "Media",
  tardia: "Tardía",
  pago_hoy: "Pago hoy",
  promesa_pago: "Promesa de pago",
  facilidades: "Facilidades de pago",
  no_puede_pagar: "No puede pagar",
  ya_pago: "Ya pagó",
  no_reconoce: "No reconoce la deuda",
  app: "App",
  banca_internet: "Banca por internet",
  agente: "Agente",
  ventanilla: "Ventanilla",
  transferencia: "Transferencia",
  pago_total: "Pago total",
  plan_3: "Plan 3 cuotas",
  plan_6: "Plan 6 cuotas",
  acuerdo_pago: "Acuerdo de pago",
  pago_reportado: "Pago reportado",
  sin_acuerdo: "Sin acuerdo",
  derivado: "Derivado a especialista",
};

const formatoMoneda = new Intl.NumberFormat("es-PE", {
  style: "currency",
  currency: "PEN",
  minimumFractionDigits: 2,
});

function mostrarValor(valor, tipo) {
  if (valor === null || valor === undefined || valor === "") return null;
  if (tipo === "moneda") {
    const numero = Number(valor);
    return Number.isFinite(numero) ? formatoMoneda.format(numero) : String(valor);
  }
  const texto = String(valor);
  return VALORES[texto] || texto;
}

function estadoProceso(estado) {
  if (!estado) return { texto: "Sin iniciar", tono: "idle" };
  if (estado.derivado) return { texto: "Derivado a especialista", tono: "warn" };
  if (estado.proceso_completo) {
    const textos = {
      acuerdo_pago: "Acuerdo registrado",
      pago_hoy: "Pago registrado",
      promesa_pago: "Promesa registrada",
      pago_reportado: "Pago reportado",
      sin_acuerdo: "Sin acuerdo",
    };
    return {
      texto: textos[estado.resultado_gestion] || "Gestión cerrada",
      tono: estado.resultado_gestion === "sin_acuerdo" ? "warn" : "done",
    };
  }
  return { texto: "En curso", tono: "live" };
}

function Expediente({ estado, recientes }) {
  const completados = CAMPOS.filter((c) => mostrarValor(estado?.[c.key], c.tipo)).length;
  const proceso = estadoProceso(estado);
  const detallesRef = useRef(null);

  // En escritorio el panel siempre está visible; en móvil empieza plegado.
  useEffect(() => {
    if (window.matchMedia("(min-width: 821px)").matches && detallesRef.current) {
      detallesRef.current.open = true;
    }
  }, []);

  return (
    <aside className="expediente" aria-label="Mi caso">
      <details ref={detallesRef}>
        <summary>
          <span className="exp-titulo">Mi caso</span>
          <span className="exp-conteo">
            {completados} de {CAMPOS.length} datos
          </span>
        </summary>

        <div className="exp-cuerpo">
          <div className="barra" aria-hidden="true">
            <span style={{ width: `${(completados / CAMPOS.length) * 100}%` }} />
          </div>
          <p className={`estado estado-${proceso.tono}`}>{proceso.texto}</p>

          <dl>
            {CAMPOS.map((c) => {
              const valor = mostrarValor(estado?.[c.key], c.tipo);
              return (
                <div
                  key={c.key}
                  className={`campo ${valor ? "lleno" : ""} ${recientes.includes(c.key) ? "reciente" : ""}`}
                >
                  <dt>{c.label}</dt>
                  <dd>{valor || "Pendiente"}</dd>
                </div>
              );
            })}
          </dl>
          <p className="exp-nota">
            Moroso verifica tu identidad y registra cada dato antes de continuar.
          </p>
        </div>
      </details>
    </aside>
  );
}

export default function Home() {
  const [mensajes, setMensajes] = useState([]);
  const [texto, setTexto] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [estado, setEstado] = useState(null);
  const [recientes, setRecientes] = useState([]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState(null);
  const finRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [mensajes, cargando]);

  async function enviar(contenido) {
    const mensaje = (contenido ?? texto).trim();
    if (!mensaje || cargando) return;

    setError(null);
    setTexto("");
    setMensajes((prev) => [...prev, { rol: "usuario", texto: mensaje }]);
    setCargando(true);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(sessionId ? { message: mensaje, session_id: sessionId } : { message: mensaje }),
      });

      if (!res.ok) {
        const detalle = await res.json().catch(() => ({}));
        throw new Error(detalle?.detail || `El servidor respondió con el código ${res.status}.`);
      }

      const data = await res.json();
      setSessionId(data.session_id);

      const cambiados = CAMPOS.map((c) => c.key).filter(
        (k) => mostrarValor(data.estado?.[k], CAMPOS.find((c) => c.key === k)?.tipo) && data.estado?.[k] !== estado?.[k]
      );
      setRecientes(cambiados);
      setEstado(data.estado);
      setMensajes((prev) => [...prev, { rol: "agente", texto: data.reply }]);
    } catch (e) {
      const sinConexion = e instanceof TypeError;
      setError({
        texto: sinConexion
          ? "No se pudo conectar con el servidor de Moroso. Revisa tu conexión y vuelve a enviar el mensaje."
          : e.message,
        mensaje,
      });
      setMensajes((prev) => prev.slice(0, -1));
      setTexto(mensaje);
    } finally {
      setCargando(false);
      inputRef.current?.focus();
    }
  }

  function nuevaConversacion() {
    setMensajes([]);
    setSessionId(null);
    setEstado(null);
    setRecientes([]);
    setError(null);
    setTexto("");
    inputRef.current?.focus();
  }

  function alPresionarTecla(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      enviar();
    }
  }

  const terminado = estado?.proceso_completo;

  return (
    <div className="app">
      <header className="cabecera">
        <div className="marca">
          <span className="logo" aria-hidden="true">
            <svg viewBox="0 0 32 32" width="32" height="32">
              <path
                d="M16 3l10 4v7c0 6.2-4.2 11.5-10 13-5.8-1.5-10-6.8-10-13V7l10-4z"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinejoin="round"
              />
              <path
                d="M11 16.5l3.2 3.2L21 12.5"
                fill="none"
                stroke="var(--accent)"
                strokeWidth="2.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <div>
            <h1>Moroso</h1>
            <p>Recuperación y acuerdos de pago</p>
          </div>
        </div>
        <button type="button" className="btn-secundario" onClick={nuevaConversacion} disabled={cargando}>
          Nueva conversación
        </button>
      </header>

      <main className="contenido">
        <section className="chat" aria-label="Conversación con Moroso">
          <div className="mensajes" role="log" aria-live="polite">
            {mensajes.length === 0 && (
              <div className="vacio">
                <h2>Empieza la conversación</h2>
                <p>
                  Moroso te pedirá tu DNI y fecha de nacimiento para verificar tu identidad.
                  Luego podrás revisar tu deuda, tus opciones de pago y registrar un compromiso.
                </p>
                <div className="sugerencias">
                  {SUGERENCIAS.map((s) => (
                    <button key={s} type="button" onClick={() => enviar(s)} disabled={cargando}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {mensajes.map((m, i) => (
              <div key={i} className={`burbuja ${m.rol}`}>
                {m.rol === "agente" ? <ReactMarkdown>{m.texto}</ReactMarkdown> : <p>{m.texto}</p>}
              </div>
            ))}

            {cargando && (
              <div className="burbuja agente escribiendo" aria-label="Moroso está escribiendo">
                <span />
                <span />
                <span />
              </div>
            )}
            <div ref={finRef} />
          </div>

          {error && (
            <div className="error" role="alert">
              <p>{error.texto}</p>
              <button type="button" onClick={() => enviar(error.mensaje)}>
                Reintentar
              </button>
            </div>
          )}

          {terminado && (
            <p className="aviso-fin">
              Esta gestión terminó. Usa «Nueva conversación» para empezar otra.
            </p>
          )}

          <form
            className="compositor"
            onSubmit={(e) => {
              e.preventDefault();
              enviar();
            }}
          >
            <label htmlFor="mensaje" className="sr-only">
              Escribe tu mensaje
            </label>
            <textarea
              id="mensaje"
              ref={inputRef}
              rows={1}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              onKeyDown={alPresionarTecla}
              placeholder="Escribe tu mensaje…"
              maxLength={2000}
              disabled={cargando}
            />
            <button type="submit" className="btn-enviar" disabled={cargando || !texto.trim()}>
              Enviar
            </button>
          </form>
        </section>

        <Expediente estado={estado} recientes={recientes} />
      </main>
    </div>
  );
}
