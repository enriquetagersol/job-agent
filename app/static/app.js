"use strict";

const E = { estado: null, vista: "candidaturas", filtroOf: "resultados", abierta: null, bandaVista: null };
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

// ---------- utilidades ----------
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const md = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
// Markdown sencillo a HTML (títulos, listas, tablas, negrita, cursiva, enlaces) para las notas del CV
const mdLinea = (t) => md(t).replace(/(^|[^*])\*([^*\s][^*]*?)\*/g, "$1<em>$2</em>").replace(/(^|[\s(«])_([^_\s][^_]*?)_(?=$|[\s.,;:)»])/g, "$1<em>$2</em>")
  .replace(/https?:\/\/[^\s<)]+/g, (u) => `<a href="${u}" target="_blank" rel="noopener">${u.length > 48 ? u.slice(0, 45) + "…" : u}</a>`);
function mdBloque(texto) {
  const out = [], lineas = texto.replace(/\r/g, "").split("\n");
  let lista = null;
  const cerrar = () => { if (lista) { out.push(`</${lista}>`); lista = null; } };
  for (let i = 0; i < lineas.length; i++) {
    const l = lineas[i];
    let m;
    if (/^\s*\|.*\|\s*$/.test(l)) {  // tabla: filas seguidas que empiezan y acaban por |
      cerrar();
      const filas = [];
      while (i < lineas.length && /^\s*\|.*\|\s*$/.test(lineas[i])) filas.push(lineas[i++]);
      i--;
      const celdas = (f) => f.trim().slice(1, -1).split("|").map((c) => c.trim());
      const cuerpo = filas.filter((f, k) => !(k === 1 && /^[\s|:-]+$/.test(f)));
      out.push(`<table>${cuerpo.map((f, k) => `<tr>${celdas(f).map((c) => k === 0 ? `<th>${mdLinea(c)}</th>` : `<td>${mdLinea(c)}</td>`).join("")}</tr>`).join("")}</table>`);
    } else if ((m = l.match(/^(#{1,4})\s+(.*)/))) {
      cerrar(); const n = Math.min(4, m[1].length + 2); out.push(`<h${n}>${mdLinea(m[2])}</h${n}>`);
    } else if ((m = l.match(/^\s*[-*•]\s+(.*)/))) {
      if (lista !== "ul") { cerrar(); out.push("<ul>"); lista = "ul"; } out.push(`<li>${mdLinea(m[1])}</li>`);
    } else if ((m = l.match(/^\s*\d+[.)]\s+(.*)/))) {
      if (lista !== "ol") { cerrar(); out.push("<ol>"); lista = "ol"; } out.push(`<li>${mdLinea(m[1])}</li>`);
    } else if (l.trim()) {
      cerrar(); out.push(`<p>${mdLinea(l)}</p>`);
    } else cerrar();
  }
  cerrar();
  return out.join("");
}
const enlaceSeguro = (u) => (/^https?:\/\//i.test(u || "") ? esc(u) : "");
const dias = (f) => (f ? Math.round((new Date(E.estado.hoy) - new Date(f)) / 864e5) : null);
const fechaCorta = (f) => (f ? new Date(f + "T00:00").toLocaleDateString("es-ES", { day: "numeric", month: "short" }) : "");
const cand = (id) => E.estado.candidaturas.find((c) => c.id === id);
const plural = (n, a, b) => `${n} ${n === 1 ? a : b}`;
const NOMBRE = { por_aplicar: "Por aplicar", enviada: "Aplicada", en_proceso: "Entrevistas", oferta: "Oferta", rechazada: "Rechazada", retirada: "Retirada" };

async function api(metodo, ruta, cuerpo) {
  const r = await fetch(ruta, { method: metodo, headers: { "Content-Type": "application/json" }, body: cuerpo ? JSON.stringify(cuerpo) : undefined });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
function aviso(t) { const el = $("#toast"); el.textContent = t; el.hidden = false; clearTimeout(aviso.t); aviso.t = setTimeout(() => (el.hidden = true), 2600); }
async function recargar() { E.estado = await api("GET", "/api/estado"); pintar(); vigilar(); }
async function cambiar(id, cambios, texto) {
  try { await api("PATCH", "/api/candidaturas/" + id, cambios); if (texto) aviso(texto); await recargar(); }
  catch (e) { aviso("Error: " + e.message); }
}
const moverA = async (id, estado) => {
  const c = cand(id), antes = JSON.stringify(c.proximo_paso || null);
  await cambiar(id, { estado }, `${c.empresa} → ${NOMBRE[estado]}`);
  if (!["rechazada", "retirada"].includes(estado)) esperarSugerencia(id, antes);
};

// ---------- navegación ----------
function irA(vista) {
  E.vista = vista;
  $$(".pestanas button").forEach((b) => b.classList.toggle("activa", b.dataset.vista === vista));
  $$(".vista").forEach((v) => (v.hidden = v.id !== "vista-" + vista));
  try { localStorage.setItem("ja-vista", vista); } catch (_) {}
  window.scrollTo(0, 0);
}
$$(".pestanas button").forEach((b) => b.addEventListener("click", () => irA(b.dataset.vista)));
document.addEventListener("click", (ev) => {
  const a = ev.target.closest("[data-ir]"); if (a) { ev.preventDefault(); irA(a.dataset.ir); if (a.dataset.f) filtro(a.dataset.f); }
  const o = ev.target.closest("[data-abrir]"); if (o) { ev.preventDefault(); abrirCajon(o.dataset.abrir); }
  const b = ev.target.closest("[data-buscar]"); if (b) { ev.preventDefault(); abrirBuscar(); }
});

const esNueva = (o) => !!o.lote && o.lote === E.estado.ultimo_lote && !o.decision;
const resultados = () => E.estado.ofertas.filter((o) => o.estado_analisis === "recomendada" && !o.decision);
// «Te interesa» = te interesan y aún no las has enviado. En cuanto avanzan, viven solo en Mis candidaturas.
const guardados = () => E.estado.ofertas.filter((o) => {
  if (!o.decision || o.decision.valor !== "interesa") return false;
  const c = o.candidatura_id && cand(o.candidatura_id);
  return !c || c.estado === "por_aplicar";
});

function pintar() {
  const n = resultados().length;
  const ins = $("#ins-ofertas"); ins.textContent = n; ins.hidden = !n;
  pintarBanda(); pintarOfertas(); pintarDashboard(); pintarBienvenida();
  if ($("#dlg-cv").open) pintarCvInfo();
  if ($("#dlg-cvprev").open) pintarCvPrevia();
  if (E.abierta) { const c = cand(E.abierta); c ? pintarCajon(c) : cerrarCajon(); }
}

// ---------- búsqueda ----------
// Banda superior: progreso mientras se busca y, al terminar, un aviso MOMENTÁNEO (se va solo).
// También avisa un momento cuando la revisión del correo encuentra ofertas que encajan (alertas de empleo).
const AVISO_MS = 12000, RECIENTE_MS = 10 * 60000;
const reciente = (iso) => iso && Date.now() - new Date(iso).getTime() < RECIENTE_MS;
function mostrarBanda(clave, clase, html) {
  const el = $("#banda");
  if (E.bandaVista === clave) return;
  E.bandaVista = clave;
  el.className = "banda " + clase;
  el.innerHTML = html + '<button class="icono" id="banda-x" aria-label="Cerrar">✕</button>';
  el.hidden = false;
  const cerrar = () => { if (E.bandaVista === clave) el.hidden = true; };
  $("#banda-x").addEventListener("click", cerrar);
  clearTimeout(mostrarBanda.t); mostrarBanda.t = setTimeout(cerrar, AVISO_MS);
}
function pintarBanda() {
  const b = E.estado.busqueda || {}, el = $("#banda"), btn = $("#btn-buscar");
  btn.disabled = b.estado === "buscando";
  btn.textContent = b.estado === "buscando" ? "Buscando…" : "🔍 Buscar ofertas";
  if (b.estado === "buscando") {
    const pct = b.total ? Math.round((100 * (b.hechas || 0)) / b.total) : 5;
    E.bandaVista = "buscando";
    el.className = "banda";
    el.innerHTML = `<span class="girando"></span><span>${esc(b.fase || "Buscando…")}</span><div class="progreso"><div style="width:${pct}%"></div></div>`;
    el.hidden = false;
    return;
  }
  if (E.bandaVista === "buscando") el.hidden = true;  // acaba de terminar
  const vistos = () => { try { return JSON.parse(localStorage.getItem("bandas-vistas") || "[]"); } catch { return []; } };
  const yaVisto = (k) => vistos().includes(k);
  const marcar = (k) => { try { localStorage.setItem("bandas-vistas", JSON.stringify([...vistos(), k].slice(-20))); } catch { /* sin almacenamiento: da igual */ } };
  const correo = E.estado.aviso_correo || {};
  if (b.estado === "listo" && reciente(b.fin) && !yaVisto("b" + b.fin)) {
    marcar("b" + b.fin);
    mostrarBanda("b" + b.fin, "ok", `<span>✓ ${esc(b.fase)}</span>${b.nuevas ? `<a href="#" data-ir="ofertas" data-f="resultados">Ver ofertas</a>` : ""}`);
  } else if (b.estado === "error" && reciente(b.fin || b.inicio) && !yaVisto("e" + (b.fin || b.inicio))) {
    marcar("e" + (b.fin || b.inicio));
    mostrarBanda("e" + (b.fin || b.inicio), "mal", `<span>No se pudo completar la búsqueda: ${esc(b.mensaje)}</span>`);
  } else if (correo.n && reciente(correo.cuando) && !yaVisto("c" + correo.cuando)) {
    marcar("c" + correo.cuando);
    mostrarBanda("c" + correo.cuando, "ok", `<span>✨ ${plural(correo.n, "oferta nueva", "ofertas nuevas")} de tus alertas de correo que te pueden interesar</span><a href="#" data-ir="ofertas" data-f="resultados">Ver ofertas</a>`);
  }
}
function abrirBuscar() {
  const ia = E.estado.ia || {};
  $("#buscar-aviso").hidden = ia.disponible; $("#buscar-aviso").textContent = ia.motivo || "";
  $("#buscar-ok").disabled = !ia.disponible;
  $("#dlg-buscar").returnValue = ""; $("#dlg-buscar").showModal();
}
$("#btn-buscar").addEventListener("click", abrirBuscar);
$("#dlg-buscar").addEventListener("close", async () => {
  if ($("#dlg-buscar").returnValue !== "ok") return;
  try { await api("POST", "/api/busqueda"); aviso("Búsqueda en marcha"); await recargar(); }
  catch (e) { aviso("Error: " + e.message); }
});
// Refresco mientras se genera algo (búsqueda o CV)
function vigilar() {
  clearTimeout(vigilar.t);
  const ocupado = (E.estado.busqueda || {}).estado === "buscando" || (E.estado.perfil || {}).estado === "analizando"
    || (E.estado.cv_general || {}).estado === "generando"
    || E.estado.candidaturas.some((c) => (c.cv_trabajo || {}).estado === "generando");
  const perfilAntes = (E.estado.perfil || {}).estado;
  if (!ocupado) {  // en reposo, se refresca cada minuto (novedades del correo, ofertas de alertas…)
    vigilar.t = setTimeout(() => { if (document.visibilityState === "visible") recargar(); else vigilar(); }, 60000);
    return;
  }
  const antes = JSON.stringify(E.estado.candidaturas.map((c) => [c.id, (c.cv_trabajo || {}).estado]));
  vigilar.t = setTimeout(async () => {
    const previo = new Map(JSON.parse(antes));
    await recargar();
    const pf = E.estado.perfil || {};
    if (perfilAntes === "analizando" && pf.estado === "listo") aviso("✓ Tu perfil está listo");
    if (perfilAntes === "analizando" && pf.estado === "error") aviso("No se pudo analizar el CV");
    E.estado.candidaturas.forEach((c) => {
      const st = (c.cv_trabajo || {}).estado;
      if (previo.get(c.id) === "generando" && st === "listo") aviso(`CV listo: ${c.empresa}`);
      if (previo.get(c.id) === "generando" && st === "error") aviso(`No se pudo crear el CV de ${c.empresa}`);
    });
  }, 4000);
}

// ---------- CV adaptado: crear y vista previa ----------
// «CV optimizado» abre esta ventana: si ya hay un CV para la oferta lo enseña; si no, lo crea (1-3 min) y lo enseña.
// Desde la vista previa: descargar o generar otro.
// La misma ventana sirve para el CV optimizado de una candidatura y para el CV general («general»)
function fuenteCv(id) {
  if (id === "general") {
    const g = E.estado.cv_general || {};
    return { titulo: "Tu CV general" + (g.pdf && g.idioma ? ` (${g.idioma.toUpperCase()})` : ""), estado: g.estado, mensaje: g.mensaje,
             pdf: g.pdf, notas: g.notas, tituloNotas: "📝 Qué he priorizado y qué revisar", idioma: g.idioma || "en",
             esperando: "Creando tu CV general… tarda 1-2 minutos. Puedes cerrar esta ventana: lo verás al pulsar «CV general».",
             crear: (idioma) => api("POST", "/api/cv/general", { idioma: idioma || g.idioma }) };
  }
  const c = cand(id); if (!c) return null;
  const tr = c.cv_trabajo || {};
  // Notas: las del CV actual (si el CV se hizo con Claude Code, están en la misma carpeta que el PDF)
  const notas = c.cv_adaptado && (tr.notas && c.cv_adaptado.startsWith(tr.notas.replace(/[^/]+$/, "")) ? tr.notas : c.cv_adaptado.replace(/[^/]+$/, "notas.md"));
  return { titulo: `Tu CV para ${c.puesto} · ${c.empresa}`, estado: tr.estado, mensaje: tr.mensaje, pdf: c.cv_adaptado, notas,
           tituloNotas: "📝 Qué he cambiado y qué revisar",
           esperando: "Creando tu CV adaptado a esta oferta… tarda 1-3 minutos. Puedes cerrar esta ventana: te aviso cuando esté y lo verás al pulsar «CV optimizado».",
           crear: () => api("POST", `/api/candidaturas/${id}/cv`) };
}
async function abrirCvPrevia(id) {
  const f = fuenteCv(id); if (!f) return;
  E.cvPrevia = id;
  const dlg = $("#dlg-cvprev");
  if (!dlg.open) dlg.showModal();
  if (!f.pdf && f.estado !== "generando") await crearCv(id);
  pintarCvPrevia();
}
async function crearCv(id, idioma) {
  try { await fuenteCv(id).crear(idioma); await recargar(); }
  catch (e) { aviso("Error: " + e.message); }
  pintarCvPrevia();
}
function pintarCvPrevia() {
  const dlg = $("#dlg-cvprev"), f = E.cvPrevia && fuenteCv(E.cvPrevia);
  if (!dlg.open || !f) return;
  const ia = E.estado.ia || {}, id = E.cvPrevia;
  $("#cvprev-titulo").textContent = f.titulo;
  const cuerpo = $("#cvprev-cuerpo"), botones = $("#cvprev-botones");
  if (f.estado === "generando") {
    cuerpo.innerHTML = `<p class="esperando"><span class="girando"></span>${esc(f.esperando)}</p>`;
    delete cuerpo.dataset.pdf;
    botones.innerHTML = `<button data-cerrar>Cerrar</button>`;
  } else if (f.pdf) {
    const url = "/archivo/" + encodeURI(f.pdf), nombre = f.pdf.split("/").pop();
    if (cuerpo.dataset.pdf !== url) {
      cuerpo.dataset.pdf = url;
      cuerpo.innerHTML = `<div class="cv-y-notas"><iframe class="pdf" src="${url}#view=FitH" title="Vista previa del CV"></iframe>
        <aside class="notas-cv" hidden><h3>${esc(f.tituloNotas)}</h3><div class="md"></div></aside></div>`;
      if (f.notas) fetch("/archivo/" + encodeURI(f.notas)).then((r) => (r.ok ? r.text() : "")).then((t) => {
        if (!t || cuerpo.dataset.pdf !== url) return;
        const panel = $(".notas-cv", cuerpo);
        $(".md", panel).innerHTML = mdBloque(t.replace(/^# .*\n/, ""));  // el título ya está arriba
        panel.hidden = false;
      }).catch(() => {});
    }
    const aviso_ = f.estado === "listo" && f.mensaje ? `<span class="err">⚠️ ${esc(f.mensaje)}</span>` : "";
    const otroIdioma = id === "general" ? (f.idioma === "es" ? "en" : "es") : null;
    botones.innerHTML = `${aviso_}
      <span class="hueco"></span><button data-cerrar>Cerrar</button>
      ${otroIdioma ? `<button data-idioma="${otroIdioma}" ${ia.disponible ? "" : "disabled"}>🌐 ${otroIdioma === "es" ? "En español" : "In English"}</button>` : ""}
      <button data-otro ${ia.disponible ? "" : "disabled"}>🔄 Generar otro</button>
      <a class="boton primario" href="${url}" download="${esc(nombre)}">⬇️ Descargar</a>`;
  } else {
    cuerpo.innerHTML = f.estado === "error" ? `<p class="err">No se pudo crear el CV: ${esc(f.mensaje)}</p>`
      : `<p class="err">${esc(ia.motivo || "No se pudo empezar a crear el CV.")}</p>`;
    delete cuerpo.dataset.pdf;
    botones.innerHTML = `<button data-cerrar>Cerrar</button><button class="primario" data-otro ${ia.disponible ? "" : "disabled"}>Intentar de nuevo</button>`;
  }
  $("[data-cerrar]", botones).addEventListener("click", () => dlg.close());
  const otro = $("[data-otro]", botones);
  if (otro) otro.addEventListener("click", async () => { otro.disabled = true; delete cuerpo.dataset.pdf; await crearCv(id); });
  const idi = $("[data-idioma]", botones);
  if (idi) idi.addEventListener("click", async () => { idi.disabled = true; delete cuerpo.dataset.pdf; await crearCv(id, idi.dataset.idioma); });
}
$("#dlg-cvprev").addEventListener("close", () => { E.cvPrevia = null; });

// ---------- Mi CV ----------
function pintarCvInfo() {
  const p = E.estado.perfil || {}, ia = E.estado.ia || {};
  let h = "";
  if (p.estado === "analizando") h += `<p><span class="girando"></span>Analizando tu CV… tarda 1-2 minutos. Puedes cerrar esta ventana.</p>`;
  if (p.estado === "error") h += `<p class="err">No se pudo analizar el CV: ${esc(p.mensaje)}</p>`;
  if (p.estado === "listo" && p.mensaje) h += `<p class="ok-txt">✓ ${esc(p.mensaje)}</p>`;
  if (p.hay_perfil) {
    h += `<div class="cv-actual">${p.archivo ? `<div><b>Archivo:</b> <a href="/archivo/${encodeURI(p.archivo)}" target="_blank">${esc(p.archivo.split("/").pop())}</a></div>` : ""}
      <div class="sub">Perfil actualizado el ${esc(fechaCorta(p.perfil_actualizado))}</div>
      ${p.resumen ? `<p class="resumen-perfil">${md(p.resumen)}</p>` : ""}</div>
      <p class="sub">Al subir un CV nuevo se regeneran tu perfil y tu CV maestro. Se guarda una copia de los actuales y se conserva lo que ya habías confirmado.</p>`;
  } else if (p.estado !== "analizando") {
    h += `<p>Sube tu CV (PDF, DOCX o TXT). Claude lo leerá para entender tu experiencia, tus skills y tus logros: es la base para buscarte ofertas y adaptar tus CVs.</p>`;
  }
  if (!ia.disponible) h += `<p class="err">${esc(ia.motivo)}</p>`;
  $("#cv-info").innerHTML = h;
  $("#cv-anadir").hidden = !p.hay_perfil || !ia.disponible;
  $("#cv-general-btn").hidden = !p.hay_perfil;
  $("#cv-general-btn").disabled = !ia.disponible;
  $("#cv-general-btn").innerHTML = (E.estado.cv_general || {}).estado === "generando" ? '<span class="girando"></span>Creando CV general…' : "📄 CV general";
  $("#cv-subir").disabled = !ia.disponible || p.estado === "analizando";
  $("#cv-subir").textContent = p.hay_perfil ? "Subir nuevo CV" : "Subir mi CV";
}
function abrirCv() { pintarCvInfo(); $("#cv-propuesta").innerHTML = ""; $("#dlg-cv").returnValue = ""; $("#dlg-cv").showModal(); }
// Añadir algo al CV maestro: Claude prepara los cambios, ella los ve y decide si se guardan
$("#cv-anadir-btn").addEventListener("click", async () => {
  const texto = $("#cv-anadir-texto").value.trim(), btn = $("#cv-anadir-btn"), caja = $("#cv-propuesta");
  if (texto.length < 10) { aviso("Cuéntame un poco más qué quieres añadir"); return; }
  btn.disabled = true; caja.innerHTML = `<p class="sub"><span class="girando"></span>Preparando los cambios…</p>`;
  try {
    const p = await api("POST", "/api/cv/proponer", { texto });
    caja.innerHTML = `<div class="propuesta">
      <p>${md(p.resumen_es)}</p>
      <ul>${p.lineas.map((l) => `<li>${mdLinea(l.replace(/\*(.+?)\*/g, "**$1**"))}</li>`).join("")}</ul>
      ${p.preguntas.length ? `<p class="sub">Para que quede más fuerte, podrías añadir:</p><ul class="preguntas">${p.preguntas.map((q) => `<li>${esc(q)}</li>`).join("")}</ul><p class="sub">Si quieres incluirlo, escríbelo arriba y vuelve a pulsar «Preparar cambios».</p>` : ""}
      <div class="fila-botones"><button type="button" class="primario" id="cv-aplicar">✅ Añadir a mi CV</button><button type="button" id="cv-descartar">Descartar</button></div></div>`;
    $("#cv-aplicar").addEventListener("click", async () => {
      $("#cv-aplicar").disabled = true;
      try { await api("POST", "/api/cv/aplicar", { id: p.id }); caja.innerHTML = `<p class="ok-txt">✓ Añadido a tu CV. Los próximos CV optimizados ya lo tendrán en cuenta.</p>`; $("#cv-anadir-texto").value = ""; }
      catch (e) { aviso("Error: " + e.message); $("#cv-aplicar").disabled = false; }
    });
    $("#cv-descartar").addEventListener("click", () => { caja.innerHTML = ""; });
  } catch (e) { caja.innerHTML = `<p class="err">${esc(e.message)}</p>`; }
  btn.disabled = false;
});
$("#btn-cv-perfil").addEventListener("click", abrirCv);
$("#cv-general-btn").addEventListener("click", () => { $("#dlg-cv").close(); abrirCvPrevia("general"); });
$("#cv-subir").addEventListener("click", () => $("#cv-archivo").click());
$("#cv-archivo").addEventListener("change", () => {
  const f = $("#cv-archivo").files[0]; $("#cv-archivo").value = "";
  if (!f) return;
  if (f.size > 10 * 1024 * 1024) { aviso("El archivo pesa más de 10 MB"); return; }
  const lector = new FileReader();
  lector.onload = async () => {
    try {
      await api("POST", "/api/cv", { nombre: f.name, datos_b64: String(lector.result).split(",")[1] || "" });
      aviso("CV subido. Analizando…"); await recargar();
    } catch (e) { aviso("Error: " + e.message); }
  };
  lector.readAsDataURL(f);
});
function pintarBienvenida() {
  const p = E.estado.perfil || {}, el = $("#bienvenida");
  if (p.hay_perfil) { el.hidden = true; return; }
  el.innerHTML = p.estado === "analizando"
    ? `<h2><span class="girando"></span>Analizando tu CV…</h2><p class="sub">En un par de minutos tendrás tu perfil listo.</p>`
    : `<h2>Bienvenida a Job Agent 👋</h2><p>Empieza subiendo tu CV: Claude entenderá tu experiencia y tus skills para buscarte ofertas que encajen de verdad y adaptar tu CV a cada una.</p>
       <button class="primario" id="bienvenida-cv">📄 Subir mi CV</button>`;
  el.hidden = false;
  const b = $("#bienvenida-cv"); if (b) b.addEventListener("click", abrirCv);
}

// ---------- preferencias ----------
const PREF_LISTAS = ["puestos", "ubicaciones", "mudarme_a"];          // valores libres (chips)
const PREF_CATS = ["sectores", "valoro", "evitar", "descarto"];       // lenguaje natural -> categorías fijas
const prefEdit = {}, prefFrases = {};

function pintarCampoNL(k) {
  const campo = $(`.campo-nl[data-k="${k}"]`), cat = E.estado.catalogos[k];
  if (!$(".nl-cuerpo", campo)) campo.insertAdjacentHTML("beforeend", `<div class="nl-cuerpo"></div>`);
  const sel = prefEdit[k], resto = cat.filter((c) => !sel.includes(c));
  const abierto = campo.dataset.abierto === "1";
  $(".nl-cuerpo", campo).innerHTML = `
    <div class="cats">${sel.map((c) => `<span class="cat">${esc(c)}<button type="button" data-quitar-cat="${esc(c)}" aria-label="Quitar ${esc(c)}">×</button></span>`).join("") || '<span class="sub">Nada todavía</span>'}</div>
    <div class="nl"><input placeholder="Dímelo con tus palabras: ${esc(campo.dataset.ej)}" aria-label="Escríbelo con tus palabras"><button type="button" class="peq">Añadir</button></div>
    ${resto.length ? `<button type="button" class="enlace peq ver-op">${abierto ? "Ocultar opciones" : "Ver opciones"}</button>
    <div class="cats opciones-cat" ${abierto ? "" : "hidden"}>${resto.map((c) => `<button type="button" class="cat libre" data-anadir-cat="${esc(c)}">+ ${esc(c)}</button>`).join("")}</div>` : ""}`;
  $$("[data-quitar-cat]", campo).forEach((b) => b.addEventListener("click", () => { prefEdit[k] = sel.filter((c) => c !== b.dataset.quitarCat); pintarCampoNL(k); }));
  $$("[data-anadir-cat]", campo).forEach((b) => b.addEventListener("click", () => { prefEdit[k].push(b.dataset.anadirCat); pintarCampoNL(k); }));
  const vo = $(".ver-op", campo);
  if (vo) vo.addEventListener("click", () => { campo.dataset.abierto = abierto ? "0" : "1"; pintarCampoNL(k); });
  const inp = $(".nl input", campo), btn = $(".nl button", campo);
  const enviar = async () => {
    const texto = inp.value.trim(); if (!texto) return;
    btn.disabled = true; btn.textContent = "…";
    try {
      const r = await api("POST", "/api/preferencias/interpretar", { campo: k, texto });
      const nuevas = r.categorias.filter((c) => !prefEdit[k].includes(c));
      prefEdit[k].push(...nuevas);
      (prefFrases[k] = prefFrases[k] || []).push(texto);
      aviso(r.categorias.length ? `Entendido: ${r.categorias.join(", ")}` : "No he encontrado una categoría para eso; lo guardo como matiz");
      pintarCampoNL(k);
    } catch (e) { aviso("Error: " + e.message); btn.disabled = false; btn.textContent = "Añadir"; }
  };
  btn.addEventListener("click", enviar);
  inp.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); enviar(); } });
}
function pintarChips(k) {
  const caja = $(`.campo-chips[data-k="${k}"] .chips-edit`);
  caja.innerHTML = prefEdit[k].map((v, i) => `<span class="chip-ed">${esc(v)}<button type="button" data-k="${k}" data-i="${i}" aria-label="Quitar ${esc(v)}">×</button></span>`).join("")
    + `<input data-k="${k}" placeholder="Añadir…" aria-label="Añadir a ${k}">`;
  $$("button", caja).forEach((b) => b.addEventListener("click", () => { prefEdit[k].splice(+b.dataset.i, 1); pintarChips(k); }));
  const inp = $("input", caja);
  inp.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" || ev.key === ",") {
      ev.preventDefault();
      const v = inp.value.trim().replace(/,$/, "");
      if (v && !prefEdit[k].includes(v)) { prefEdit[k].push(v); pintarChips(k); $(`.campo-chips[data-k="${k}"] input`).focus(); }
    } else if (ev.key === "Backspace" && !inp.value && prefEdit[k].length) { prefEdit[k].pop(); pintarChips(k); $(`.campo-chips[data-k="${k}"] input`).focus(); }
  });
}
$("#btn-pref").addEventListener("click", () => {
  const p = E.estado.preferencias, f = $("#form-pref");
  PREF_LISTAS.forEach((k) => {
    prefEdit[k] = [...(p[k] || [])];
    const campo = $(`.campo-chips[data-k="${k}"]`);
    if (!$(".chips-edit", campo)) campo.insertAdjacentHTML("beforeend", '<div class="chips-edit"></div>');
    pintarChips(k);
  });
  PREF_CATS.forEach((k) => {
    prefEdit[k] = [...(p[k] || [])]; prefFrases[k] = [...((p.frases || {})[k] || [])];
    $(`.campo-nl[data-k="${k}"]`).dataset.abierto = "0"; pintarCampoNL(k);
  });
  f.modalidad.value = p.modalidad || "Híbrido"; f.salario_minimo.value = p.salario_minimo || ""; f.salario_objetivo.value = p.salario_objetivo || "";
  $("#dlg-pref").returnValue = ""; $("#dlg-pref").showModal();
});
$("#form-pref").addEventListener("keydown", (ev) => { if (ev.key === "Enter" && ev.target.matches(".chips-edit input, .nl input")) ev.preventDefault(); });
$("#dlg-pref").addEventListener("close", async () => {
  if ($("#dlg-pref").returnValue !== "ok") return;
  const f = $("#form-pref");
  PREF_LISTAS.forEach((k) => { const v = $(`.campo-chips[data-k="${k}"] input`).value.trim(); if (v && !prefEdit[k].includes(v)) prefEdit[k].push(v); });
  try {
    await api("PUT", "/api/preferencias", { ...prefEdit, frases: prefFrases, modalidad: f.modalidad.value, salario_minimo: f.salario_minimo.value, salario_objetivo: f.salario_objetivo.value });
    aviso("Preferencias guardadas ✓"); recargar();
  } catch (e) { aviso("Error: " + e.message); }
});

// ---------- OFERTAS ----------
function tarjetaOferta(o) {
  const s = o.sencillo || {};
  const nivel = o.encaje >= 70 ? "alto" : o.encaje >= 55 ? "medio" : "bajo";
  const secciones = [["que_harias", "Qué harías", ""], ["por_que_encaja", "Por qué encaja", "si"], ["por_que_no_encaja", "Por qué no encaja", "no"]]
    .map(([k, t, cls]) => `<div class="${cls}"><b>${t}</b>${md(s[k] || (k === "por_que_no_encaja" ? s.gaps : "") || "—")}</div>`).join("");
  let pie;
  if (o.decision && o.decision.valor === "interesa") {
    // «Te interesa»: CV optimizado (vista previa), marcarla como aplicada o descartarla
    const c = o.candidatura_id && cand(o.candidatura_id), tr = (c && c.cv_trabajo) || {};
    const creando = c && tr.estado === "generando";
    pie = `<div class="decision">
      ${c ? `<button class="primario" data-cv="${c.id}">${creando ? '<span class="girando"></span>Creando tu CV…' : "📄 CV optimizado"}</button>
             <button class="aplicada" data-aplicada="${c.id}">✅ Aplicada</button>` : ""}
      <button class="no-interesa" data-quitar="${o.id}">👎 Ya no me interesa</button></div>`;
  } else {
    pie = `<div class="decidir"><button class="si" data-decidir="${o.id}" data-v="interesa">👍 Me interesa</button>
      <button class="no" data-decidir="${o.id}" data-v="no interesa">👎 No me interesa</button></div>`;
  }
  return `<article class="oferta" id="of-${o.id}">
    <div class="of-cab"><div class="encaje ${nivel}" title="Encaje con tu perfil y tus preferencias (0-100)"><span class="et">Encaje</span><span class="n">${o.encaje ?? "–"}<small>/100</small></span></div>
      <div><div class="of-tit">${esc(o.puesto)}${esNueva(o) ? ' <span class="nueva">Nueva</span>' : ""}</div>
      <div class="of-emp">${esc(o.empresa)}${enlaceSeguro(o.url) ? ` · <a href="${enlaceSeguro(o.url)}" target="_blank" rel="noopener">Ver oferta ↗</a>` : ""}</div>
      ${o.datos ? `<div class="of-datos">${esc(o.datos)}</div>` : ""}</div></div>
    <div class="sencillo">${o.empresa_desc ? `<div class="empresa-desc"><b>La empresa</b>${md(o.empresa_desc)}</div>` : ""}${secciones}</div>${pie}</article>`;
}
function pintarOfertas() {
  const res = resultados(), gua = guardados();
  $$("#filtro-ofertas button").forEach((b) => {
    b.classList.toggle("activa", b.dataset.f === E.filtroOf);
    b.textContent = b.dataset.f === "resultados" ? `Resultados de búsqueda (${res.length})` : `Te interesa (${gua.length})`;
  });
  // Las nuevas primero; dentro de cada grupo, por encaje
  const os = (E.filtroOf === "resultados" ? res : gua).sort((a, b) => (esNueva(b) - esNueva(a)) || ((b.encaje ?? -1) - (a.encaje ?? -1)));
  const vacio = E.filtroOf === "resultados"
    ? `No hay ofertas nuevas por revisar.<br><button class="primario" data-buscar>🔍 Buscar ofertas</button>`
    : "Aún no hay ofertas aquí. Pulsa «👍 Me interesa» en los resultados.";
  $("#lista-ofertas").innerHTML = os.length ? os.map(tarjetaOferta).join("") : `<div class="vacio">${vacio}</div>`;
  $$("[data-decidir]").forEach((b) => b.addEventListener("click", () => pedirMotivo(b.dataset.decidir, b.dataset.v)));
  $$("[data-quitar]").forEach((b) => b.addEventListener("click", () => pedirMotivo(b.dataset.quitar, "no interesa")));
  $$("[data-cv]").forEach((b) => b.addEventListener("click", () => abrirCvPrevia(b.dataset.cv)));
  $$("[data-aplicada]").forEach((b) => b.addEventListener("click", async () => {
    const c = cand(b.dataset.aplicada);
    await moverA(c.id, "enviada");  // sale de «Te interesa» y pasa al tracker como Aplicada
    aviso(`✅ ${c.empresa}: aplicada. Ahora está en Mis candidaturas.`);
  }));
}
function filtro(f) { E.filtroOf = f; pintarOfertas(); }
$$("#filtro-ofertas button").forEach((b) => b.addEventListener("click", () => filtro(b.dataset.f)));

// ¿Por qué? (opcional, al pulsar el botón)
const MOTIVOS = {
  "interesa": ["El tipo de puesto", "La empresa o el producto", "Ubicación o modalidad", "El sueldo", "Lo que aprendería", "Encaja con mi experiencia"],
  "no interesa": ["No me atrae el puesto", "Piden experiencia que no tengo", "Demasiado técnico", "Mudanza o ubicación", "Mucha presencialidad o viajes", "Sueldo", "La empresa o el sector", "Tiene parte comercial o cuota"],
};
let decisionPendiente = null;
function pedirMotivo(id, valor) {
  decisionPendiente = { id, valor };
  const o = E.estado.ofertas.find((x) => x.id === id);
  $("#motivo-titulo").textContent = valor === "interesa" ? `¿Qué te gusta de ${o.empresa}?` : `¿Por qué no te interesa ${o.empresa}?`;
  $("#motivo-opciones").innerHTML = MOTIVOS[valor].map((m) => `<label class="opcion"><input type="checkbox" value="${esc(m)}"> ${esc(m)}</label>`).join("");
  $("#motivo-texto").value = "";
  $("#dlg-motivo").returnValue = ""; $("#dlg-motivo").showModal();
}
$("#dlg-motivo").addEventListener("close", async () => {
  if (!decisionPendiente || !["ok", "omitir"].includes($("#dlg-motivo").returnValue)) { decisionPendiente = null; return; }
  const { id, valor } = decisionPendiente; decisionPendiente = null;
  const partes = $("#dlg-motivo").returnValue === "ok"
    ? [...$$("#motivo-opciones input:checked").map((i) => i.value), $("#motivo-texto").value.trim()].filter(Boolean) : [];
  try {
    const o = await api("POST", `/api/ofertas/${id}/decision`, { valor, motivo: partes.join("; ") });
    aviso(valor === "interesa" ? `👍 ${o.empresa} está en «Te interesa»` : "👎 Anotado. No volverá a aparecer");
    await recargar();
  } catch (e) { aviso("Error: " + e.message); }
});
// Cerrar con Esc/fuera = cancelar (no decide)
$("#dlg-motivo").addEventListener("cancel", () => { decisionPendiente = null; });

// ---------- MIS CANDIDATURAS: dashboard (solo lectura; se edita en el detalle) ----------
function sinRespuesta(c) {
  const d = dias(c.fecha_actualizacion);
  return ["enviada", "en_proceso"].includes(c.estado) && (d === null || d >= E.estado.seguimiento.umbral_dias);
}
const lista = (xs) => xs.length <= 1 ? xs.join("") : xs.slice(0, -1).join(", ") + " y " + xs[xs.length - 1];
const ORDEN_ESTADO = ["oferta", "en_proceso", "enviada", "por_aplicar", "rechazada", "retirada"];

const cerradaC = (c) => ["rechazada", "retirada"].includes(c.estado);
const recorta = (t, n) => (t.length > n ? t.slice(0, n - 1).trimEnd() + "…" : t);
// Última novedad: el último evento del historial (los cambios de etapa se leen «Pasa a …»)
function ultimaNovedad(c) { const ev = c.eventos || []; return ev.length ? ev[ev.length - 1] : null; }
const esDelCorreo = (e) => e.origen === "correo" || /\((del|según el) correo/i.test(e.texto || "");
function textoEvento(e) {
  if (e.tipo !== "estado") return e.texto.replace(/\*\*/g, "").replace(/\s*\((del|según el) correo[^)]*\)/gi, "");
  const m = e.texto.match(/→\s*(.+)$/); if (!m) return e.texto;
  const clave = Object.keys(E.estado.etiquetas_estado).find((k) => E.estado.etiquetas_estado[k] === m[1].trim());
  return "Pasa a " + (clave ? NOMBRE[clave] : m[1]);
}

// Ordenar por prioridad: arrastrar el asa ⠿ (ratón o dedo) o flechas ↑/↓ sobre ella (teclado)
function guardarOrden() {
  const ids = $$("#tabla-cand tbody tr[data-mov]").map((tr) => tr.dataset.id);
  ids.forEach((id, i) => { const c = cand(id); if (c) c.prioridad = i; });
  api("POST", "/api/candidaturas/orden", { ids }).catch((e) => aviso("Error: " + e.message));
}
function activarArrastre() {
  const cuerpo = $("#tabla-cand tbody");
  $$("tr[data-mov]", cuerpo).forEach((tr) => {
    const asa = $(".asa", tr);
    asa.addEventListener("click", (ev) => ev.stopPropagation());
    // Ratón o dedo: se arrastra desde el asa ⠿
    asa.addEventListener("pointerdown", (ev) => {
      ev.preventDefault();  // escuchamos en window: mover la fila en el DOM anula la captura del puntero
      tr.classList.add("arrastrando"); let movida = false;
      const mover = (e) => {
        const otras = $$("tr[data-mov]", cuerpo).filter((x) => x !== tr);
        const antes = otras.find((x) => { const r = x.getBoundingClientRect(); return e.clientY < r.top + r.height / 2; });
        const destino = antes || (otras.length ? otras[otras.length - 1].nextSibling : null);
        if (destino !== tr.nextSibling && destino !== tr) { cuerpo.insertBefore(tr, destino); movida = true; }
      };
      const soltar = () => {
        window.removeEventListener("pointermove", mover); window.removeEventListener("pointerup", soltar); window.removeEventListener("pointercancel", soltar);
        tr.classList.remove("arrastrando"); if (movida) guardarOrden();
      };
      window.addEventListener("pointermove", mover); window.addEventListener("pointerup", soltar); window.addEventListener("pointercancel", soltar);
    });
    // Teclado: flechas ↑/↓ sobre el asa
    asa.addEventListener("keydown", (ev) => {
      if (ev.key !== "ArrowUp" && ev.key !== "ArrowDown") return;
      ev.preventDefault(); ev.stopPropagation();
      const otro = ev.key === "ArrowUp" ? tr.previousElementSibling : tr.nextElementSibling;
      if (!otro || !otro.hasAttribute("data-mov")) return;
      cuerpo.insertBefore(tr, ev.key === "ArrowUp" ? otro : otro.nextSibling);
      asa.focus(); guardarOrden();
    });
  });
}

function pintarDashboard() {
  const m = E.estado.metricas, cs = E.estado.candidaturas, s = E.estado.seguimiento;
  // Usuario nuevo: solo la bienvenida (sin resumen, cifras ni tablas vacías)
  const vacio = !cs.length;
  $("#para-hoy").hidden = vacio && !(E.estado.perfil || {}).hay_perfil;
  ["#kpis", "#embudo", "#tabla-cand"].forEach((sel) => { const el = $(sel).closest(".panel") || $(sel); el.hidden = vacio; });

  // Para hoy: resumen en texto
  const nNuevas = resultados().filter(esNueva).length;
  const nRes = resultados().length, nEnviar = s.por_aplicar.length, nSin = s.sin_novedad.length;
  const partes = [
    nRes && `<strong>${plural(nRes, "oferta", "ofertas")}</strong> por revisar${nNuevas ? ` (${nNuevas === nRes ? (nNuevas === 1 ? "es nueva" : "todas nuevas") : `${nNuevas} ${nNuevas === 1 ? "nueva" : "nuevas"}`})` : ""}`,
    nEnviar && `<strong>${plural(nEnviar, "candidatura", "candidaturas")}</strong> por enviar`,
    nSin && `<strong>${nSin}</strong> sin respuesta desde hace más de ${s.umbral_dias} días`,
  ].filter(Boolean);
  let txt = partes.length ? `Tienes ${lista(partes)}.` : "Todo al día.";
  if (s.proximos.length) {
    const c = s.proximos[0];
    txt += ` Próximo paso: <strong>${esc(c.empresa)}</strong>, ${esc(c.proximo_paso.texto.charAt(0).toLowerCase() + c.proximo_paso.texto.slice(1))}${c.proximo_paso.fecha ? ` (${esc(fechaCorta(c.proximo_paso.fecha))})` : ""}${s.proximos.length > 1 ? ` y ${s.proximos.length - 1} más` : ""}.`;
  }
  const masAntigua = s.sin_novedad.find((c) => c.dias !== null);
  if (masAntigua) txt += ` La que más tiempo lleva esperando es <strong>${esc(masAntigua.empresa)}</strong> (${masAntigua.dias} días).`;
  $("#para-hoy").innerHTML = `<span class="hoy-tit">Para hoy</span><p>${txt}</p>`;

  // Cifras
  $("#kpis").innerHTML = [
    [m.total_aplicadas, "Enviadas"], [m.tasa_respuesta + " %", "Con respuesta"],
    [m.por_estado.en_proceso, "En entrevistas"], [m.por_estado.oferta, m.por_estado.oferta === 1 ? "Oferta" : "Ofertas"],
  ].map(([v, l]) => `<div class="kpi"><div class="v">${esc(v)}</div><div class="l">${esc(l)}</div></div>`).join("");

  // Candidaturas por etapa: una sola serie (un solo color), valor rotulado y tooltip al pasar
  const etapas = E.estado.etapas.map((e) => ({ ...e, n: cs.filter((c) => e.estados.includes(c.estado)).length }));
  const total = Math.max(1, cs.length), max = Math.max(1, ...etapas.map((e) => e.n));
  $("#embudo").innerHTML = etapas.map((e) => {
    const pct = Math.round((100 * e.n) / total);
    return `<div class="fila-embudo" tabindex="0" title="${esc(e.nombre)}: ${e.n} (${pct} % del total)">
      <span class="et">${esc(e.nombre)}</span>
      <span class="pista"><span class="relleno-embudo" style="width:${Math.max(e.n ? 2 : 0, (100 * e.n) / max)}%"></span></span>
      <span class="val">${e.n}</span></div>`;
  }).join("");

  // Tabla de situación: abiertas por la prioridad que ella elige (arrastrando); cerradas al final
  const auto = (a, b) => (ORDEN_ESTADO.indexOf(a.estado) - ORDEN_ESTADO.indexOf(b.estado))
    || (sinRespuesta(b) - sinRespuesta(a)) || (a.fecha_actualizacion || "").localeCompare(b.fecha_actualizacion || "");
  const prio = (c) => (c.prioridad ?? Infinity);
  const abiertas = cs.filter((c) => !cerradaC(c)).sort((a, b) => (prio(a) - prio(b)) || auto(a, b));
  const cerradas = cs.filter(cerradaC).sort((a, b) => (b.fecha_actualizacion || "").localeCompare(a.fecha_actualizacion || ""));
  $("#tabla-cand tbody").innerHTML = [...abiertas, ...cerradas].map((c) => {
    const d = dias(c.fecha_actualizacion), tr = c.cv_trabajo || {}, ev = ultimaNovedad(c);
    const cuando = d === null ? "" : d === 0 ? "Hoy" : d === 1 ? "Ayer" : fechaCorta(c.fecha_actualizacion);
    const novedad = (ev ? `<div>${esc(recorta(textoEvento(ev), 90))}</div>` : "")
      + `<div class="cuando ${sinRespuesta(c) ? "tarde" : ""}">${cuando || "Sin fecha"}${sinRespuesta(c) && d !== null ? ` · ${d} días sin respuesta` : ""}</div>`;
    const pp = c.proximo_paso;
    let paso = pp && pp.texto ? `<div>${pp.sugerido ? '<span class="bombilla" title="Sugerido por Job Agent">💡</span> ' : ""}${esc(pp.texto)}</div>`
      + (pp.fecha ? `<div class="cuando ${pp.fecha < E.estado.hoy ? "tarde" : ""}">${esc(fechaCorta(pp.fecha))}</div>` : "") : "";
    if (!paso && c.estado === "por_aplicar" && tr.estado === "generando") paso = "Creando tu CV…";
    const cerrada = cerradaC(c);
    return `<tr class="${cerrada ? "cerrada" : ""}" data-abrir="${c.id}" data-id="${c.id}" tabindex="0" ${cerrada ? "" : "data-mov"}>
      <td class="asa-col">${cerrada ? "" : `<button type="button" class="asa" aria-label="Mover ${esc(c.empresa)} (flechas arriba/abajo)" title="Arrastra para ordenar">⠿</button>`}</td>
      <td class="t-emp">${esc(c.empresa)}</td><td>${esc(c.puesto)}</td>
      <td><span class="etapa e-${c.estado}">${NOMBRE[c.estado]}</span></td>
      <td class="t-nov">${novedad}</td><td class="t-paso">${paso || "—"}</td></tr>`;
  }).join("");
  activarArrastre();
  $$("#tabla-cand tbody tr").forEach((tr) => tr.addEventListener("keydown", (ev) => { if (ev.key === "Enter") abrirCajon(tr.dataset.abrir); }));
}
$("#btn-nueva").addEventListener("click", () => { $("#form-nueva").reset(); $("#dlg-nueva").returnValue = ""; $("#dlg-nueva").showModal(); });
$("#dlg-nueva").addEventListener("close", async () => {
  if ($("#dlg-nueva").returnValue !== "ok") return;
  const f = $("#form-nueva");
  try {
    const c = await api("POST", "/api/candidaturas", { empresa: f.empresa.value.trim(), puesto: f.puesto.value.trim(), url: f.url.value.trim(), estado: f.estado.value });
    aviso("Añadida"); await recargar(); abrirCajon(c.id);
  } catch (e) { aviso("Error: " + e.message); }
});

// ---------- detalle de candidatura ----------
const form = $("#form-cand");
function abrirCajon(id) {
  const c = cand(id); if (!c) return;
  E.abierta = id;
  const ev = ultimaNovedad(c);
  E.novOriginal = { texto: ev ? textoEvento(ev) : "", fecha: ev ? ev.fecha || "" : "" };
  form.novedad_texto.value = E.novOriginal.texto; form.novedad_fecha.value = E.novOriginal.fecha || E.estado.hoy;
  form.novedad_fecha.max = E.estado.hoy;
  E.editando = { fecha: false, paso: false };
  form.proximo_fecha.value = (c.proximo_paso && c.proximo_paso.fecha) || "";
  form.proximo_texto.value = (c.proximo_paso && c.proximo_paso.texto) || "";
  $("#cajon-sugerido").textContent = "💡 sugerido por Job Agent";
  $("#cajon-sugerido").hidden = !(c.proximo_paso && c.proximo_paso.sugerido);
  pintarCajon(c);
  $("#cajon").hidden = false; $("#velo").hidden = false;
}
function pintarCajon(c) {
  $("#cajon-titulo").textContent = c.empresa;
  $("#cajon-sub").textContent = c.puesto;
  $("#cajon-etapas").innerHTML = Object.keys(NOMBRE).map((e) => `<button type="button" class="${c.estado === e ? "activa" : ""}" data-e="${e}">${NOMBRE[e]}</button>`).join("");
  $$("#cajon-etapas button").forEach((b) => b.addEventListener("click", () => { if (b.dataset.e !== c.estado) moverA(c.id, b.dataset.e); }));
  if (enlaceSeguro(c.url)) $("#cajon-sub").insertAdjacentHTML("beforeend", ` · <a href="${enlaceSeguro(c.url)}" target="_blank" rel="noopener">Ver oferta ↗</a>`);
  const ev = ultimaNovedad(c), origen = $("#cajon-nov-origen");
  origen.textContent = !ev ? "" : esDelCorreo(ev) ? "📧 desde tu correo" : ev.tipo === "estado" ? "cambio de etapa" : "";
  origen.hidden = !origen.textContent;
  $("#eventos").innerHTML = [...c.eventos].reverse().map((e) => `<li class="${e.tipo}"><div class="f">${esc(fechaCorta(e.fecha) || "")}${esDelCorreo(e) ? " · 📧 correo" : ""}</div>${e.tipo === "estado" ? esc(textoEvento(e)) : md(e.texto.replace(/\s*\((del|según el) correo[^)]*\)/gi, ""))}</li>`).join("");
  pintarBloqueCv(c);
}
function cerrarCajon() { $("#cajon").hidden = true; $("#velo").hidden = true; E.abierta = null; }
$("#cajon-cerrar").addEventListener("click", cerrarCajon);
$("#velo").addEventListener("click", cerrarCajon);
document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && !$("#cajon").hidden) cerrarCajon(); });
// Si cambia el próximo paso, pasa a ser suyo (deja de ser una sugerencia)
function pasoSiCambia() {
  const c = cand(E.abierta), pp = (c && c.proximo_paso) || {};
  const texto = form.proximo_texto.value.trim(), fecha = form.proximo_fecha.value;
  if (texto === (pp.texto || "") && fecha === (pp.fecha || "")) return {};
  return { proximo_paso: texto ? { fecha, texto } : null };
}
// Una novedad nueva es de hoy salvo que se elija otra fecha; no pisar el próximo paso si lo está editando
form.novedad_fecha.addEventListener("input", () => { E.editando.fecha = true; });
form.novedad_texto.addEventListener("input", () => {
  if (!E.editando.fecha) form.novedad_fecha.value = form.novedad_texto.value.trim() !== (E.novOriginal || {}).texto ? E.estado.hoy : (E.novOriginal || {}).fecha;
});
[form.proximo_texto, form.proximo_fecha].forEach((el) => el.addEventListener("input", () => { E.editando.paso = true; }));
form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const id = E.abierta, cambios = { ...pasoSiCambia() };
  const t = form.novedad_texto.value.trim(), f = form.novedad_fecha.value || E.estado.hoy, o = E.novOriginal || {};
  const nueva = t && t !== o.texto;
  if (nueva) Object.assign(cambios, { nota: t, fecha_nota: f });
  else if (t && f !== o.fecha) cambios.corregir_fecha_novedad = f;  // misma novedad, otra fecha
  if (!Object.keys(cambios).length) { aviso("No hay cambios"); return; }
  const antes = JSON.stringify((cand(id) || {}).proximo_paso || null);
  await cambiar(id, cambios, "Guardado ✓");
  if (E.abierta === id) abrirCajon(id);
  if (nueva && !("proximo_paso" in cambios)) esperarSugerencia(id, antes);
});

// Tras una novedad o un cambio de etapa, Job Agent sugiere el próximo paso (tarda unos segundos):
// se indica en el detalle y se actualiza en cuanto llega, salvo que ella esté escribiendo uno.
async function esperarSugerencia(id, antes) {
  const marca = () => { if (E.abierta === id && !E.editando.paso) { $("#cajon-sugerido").hidden = false; $("#cajon-sugerido").textContent = "💡 pensando el próximo paso…"; } };
  marca();
  for (let i = 0; i < 20; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    await recargar();
    const c = cand(id);
    if (!c) return;
    if (JSON.stringify(c.proximo_paso || null) !== antes) break;
    marca();
  }
  if (E.abierta === id && !E.editando.paso) abrirCajon(id);
}

// CV adaptado (API de Claude): solo en candidaturas por aplicar
function pintarBloqueCv(c) {
  const el = $("#cajon-cv");
  if (c.estado !== "por_aplicar") { el.hidden = true; return; }
  const creando = (c.cv_trabajo || {}).estado === "generando";
  el.innerHTML = `<div class="tit">Tu CV para esta oferta</div>
    <div class="fila-botones"><button type="button" class="primario" id="btn-cv">${creando ? '<span class="girando"></span>Creando tu CV…' : "📄 CV optimizado"}</button></div>
    <div class="sub">Claude adapta tu CV a esta oferta sin inventar nada. Lo verás antes de descargarlo.</div>`;
  el.hidden = false;
  $("#btn-cv", el).addEventListener("click", () => abrirCvPrevia(c.id));
}

// ---------- arranque ----------
(async () => {
  let v = "candidaturas"; try { v = localStorage.getItem("ja-vista") || v; } catch (_) {}
  if (!["ofertas", "candidaturas"].includes(v)) v = "candidaturas";
  await recargar(); irA(v);
  // Enlaces directos: ?vista=ofertas&filtro=guardados · ?candidatura=c001 · ?cv=c010 (vista previa del CV)
  const q = new URLSearchParams(location.search);
  if (q.get("vista")) irA(q.get("vista"));
  if (q.get("filtro")) filtro(q.get("filtro"));
  if (q.get("candidatura")) abrirCajon(q.get("candidatura"));
  if (q.get("cv")) abrirCvPrevia(q.get("cv"));
  window.addEventListener("focus", () => { if ($("#cajon").hidden && !$("dialog[open]")) recargar(); });
  setInterval(() => { if ($("#cajon").hidden && !$("dialog[open]") && document.visibilityState === "visible") recargar(); }, 60000);
})();
