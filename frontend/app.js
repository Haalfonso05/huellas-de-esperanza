const { MASCOTAS_API_URL, ADOPCIONES_API_URL } = window.CONFIG;

const $ = (selector) => document.querySelector(selector);

const DESPERTANDO = "Cargando. Si los servicios estaban inactivos, puede tardar hasta un minuto.";

// ---------- Utilidades ----------

function escapar(texto) {
  const div = document.createElement("div");
  div.textContent = texto ?? "";
  return div.innerHTML;
}

async function pedir(url, opciones = {}) {
  let respuesta;
  try {
    respuesta = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...opciones,
    });
  } catch {
    throw new Error("No se pudo conectar con el servicio. Revisa tu conexión e inténtalo de nuevo.");
  }
  const datos = await respuesta.json().catch(() => null);
  if (!respuesta.ok) {
    throw new Error(mensajeDeError(datos, respuesta.status));
  }
  return datos;
}

function mensajeDeError(datos, codigo) {
  if (typeof datos?.detail === "string") return datos.detail;
  if (Array.isArray(datos?.detail)) {
    const campo = datos.detail[0]?.loc?.at(-1);
    return `Revisa el campo "${String(campo).replaceAll("_", " ")}".`;
  }
  return `El servicio respondió con un error (${codigo}).`;
}

let temporizadorToast;
function avisar(mensaje) {
  const toast = $("#toast");
  toast.textContent = mensaje;
  toast.classList.add("visible");
  clearTimeout(temporizadorToast);
  temporizadorToast = setTimeout(() => toast.classList.remove("visible"), 4000);
}

function formatearEdad(meses) {
  if (meses === null || meses === undefined) return null;
  if (meses < 12) return `${meses} ${meses === 1 ? "mes" : "meses"}`;
  const anios = Math.floor(meses / 12);
  return `${anios} ${anios === 1 ? "año" : "años"}`;
}

const TAMANOS = { pequeno: "Pequeño", mediano: "Mediano", grande: "Grande" };
const ESPECIES = { perro: "Perro", gato: "Gato", otro: "Otra especie" };

function tonoDe(id) {
  let suma = 0;
  for (const caracter of id) suma += caracter.charCodeAt(0);
  return suma % 4;
}

function urlSegura(url) {
  return /^https?:\/\//i.test(url ?? "") ? url : null;
}

function datosDelFormulario(form) {
  const datos = {};
  for (const [clave, valor] of new FormData(form)) {
    const limpio = valor.trim();
    datos[clave] = limpio === "" ? null : limpio;
  }
  return datos;
}

async function enviarFormulario(form, accion) {
  const error = form.querySelector(".error");
  const boton = form.querySelector('[type="submit"]');
  error.textContent = "";
  boton.disabled = true;
  try {
    await accion();
  } catch (e) {
    error.textContent = e.message;
  } finally {
    boton.disabled = false;
  }
}

// ---------- Mascotas ----------

async function cargarMascotas() {
  const estado = $("#estado-mascotas");
  const muro = $("#muro");
  estado.className = "aviso";
  estado.textContent = DESPERTANDO;
  muro.innerHTML = "";

  const parametros = new URLSearchParams();
  if ($("#filtro-especie").value) parametros.set("especie", $("#filtro-especie").value);
  if ($("#filtro-estado").value) parametros.set("estado", $("#filtro-estado").value);

  try {
    const mascotas = await pedir(`${MASCOTAS_API_URL}/mascotas?${parametros}`);
    estado.textContent = mascotas.length ? "" : "No hay mascotas con estos filtros. Prueba con otra especie o estado.";
    muro.innerHTML = mascotas.map(cartelDeMascota).join("");
  } catch (e) {
    estado.className = "aviso es-error";
    estado.textContent = e.message;
  }
}

function cartelDeMascota(m) {
  const datos = [
    ESPECIES[m.especie],
    m.raza,
    m.sexo === "macho" ? "Macho" : m.sexo === "hembra" ? "Hembra" : null,
    formatearEdad(m.edad_meses),
    TAMANOS[m.tamano],
  ].filter(Boolean).join(", ");

  const foto = urlSegura(m.foto_url);
  const adoptada = m.estado === "adoptada";

  return `
    <article class="cartel ${adoptada ? "cartel-adoptada" : ""}" data-tono="${tonoDe(m.id)}">
      ${foto ? `<img class="cartel-foto" src="${escapar(foto)}" alt="Foto de ${escapar(m.nombre)}" loading="lazy">` : ""}
      ${adoptada ? `<span class="sello">Adoptada</span>` : ""}
      <div class="cartel-cuerpo">
        <h2 class="cartel-nombre">${escapar(m.nombre)}</h2>
        <p class="cartel-datos">${escapar(datos)}</p>
        ${m.descripcion ? `<p class="cartel-descripcion">${escapar(m.descripcion)}</p>` : ""}
      </div>
      ${adoptada ? "" : `
        <button type="button" class="tiras" data-solicitar="${escapar(m.id)}" data-nombre="${escapar(m.nombre)}">
          <span>Solicitar adopción</span>
        </button>`}
    </article>`;
}

$("#muro").addEventListener("click", (evento) => {
  const boton = evento.target.closest("[data-solicitar]");
  if (!boton) return;
  const form = $("#form-solicitud");
  form.reset();
  form.querySelector(".error").textContent = "";
  form.elements.mascota_id.value = boton.dataset.solicitar;
  $("#solicitud-nombre").textContent = boton.dataset.nombre;
  $("#dialogo-solicitud").showModal();
});

$("#form-solicitud").addEventListener("submit", (evento) => {
  evento.preventDefault();
  const form = evento.target;
  enviarFormulario(form, async () => {
    await pedir(`${ADOPCIONES_API_URL}/solicitudes`, {
      method: "POST",
      body: JSON.stringify(datosDelFormulario(form)),
    });
    $("#dialogo-solicitud").close();
    avisar(`Solicitud enviada para ${$("#solicitud-nombre").textContent}.`);
    cargarMascotas();
  });
});

$("#abrir-registro").addEventListener("click", () => {
  const form = $("#form-registro");
  form.reset();
  form.querySelector(".error").textContent = "";
  $("#dialogo-registro").showModal();
});

$("#form-registro").addEventListener("submit", (evento) => {
  evento.preventDefault();
  const form = evento.target;
  enviarFormulario(form, async () => {
    const datos = datosDelFormulario(form);
    datos.edad_meses = datos.edad_meses === null ? null : Number(datos.edad_meses);
    const mascota = await pedir(`${MASCOTAS_API_URL}/mascotas`, {
      method: "POST",
      body: JSON.stringify(datos),
    });
    $("#dialogo-registro").close();
    avisar(`Mascota registrada: ${mascota.nombre}.`);
    cargarMascotas();
  });
});

// ---------- Solicitudes ----------

async function cargarSolicitudes() {
  const estado = $("#estado-solicitudes");
  const lista = $("#lista-solicitudes");
  estado.className = "aviso";
  estado.textContent = DESPERTANDO;
  lista.innerHTML = "";

  const filtro = $("#filtro-solicitud").value;
  const parametros = filtro ? `?estado=${filtro}` : "";

  try {
    // El frontend combina los datos de los dos servicios para mostrar el nombre.
    const [solicitudes, mascotas] = await Promise.all([
      pedir(`${ADOPCIONES_API_URL}/solicitudes${parametros}`),
      pedir(`${MASCOTAS_API_URL}/mascotas`),
    ]);
    const nombres = new Map(mascotas.map((m) => [m.id, m.nombre]));
    estado.textContent = solicitudes.length ? "" : "No hay solicitudes con este estado.";
    lista.innerHTML = solicitudes
      .map((s) => filaDeSolicitud(s, nombres.get(s.mascota_id) ?? "Mascota no encontrada"))
      .join("");
  } catch (e) {
    estado.className = "aviso es-error";
    estado.textContent = e.message;
  }
}

function filaDeSolicitud(s, nombreMascota) {
  const fecha = new Date(s.creada_en).toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric" });
  const estados = { pendiente: "Pendiente", aprobada: "Aprobada", rechazada: "Rechazada" };
  return `
    <article class="solicitud">
      <div>
        <h3>${escapar(nombreMascota)}</h3>
        <span class="etiqueta etiqueta-${s.estado}">${estados[s.estado]}</span>
      </div>
      <div>
        <p><strong>${escapar(s.solicitante_nombre)}</strong></p>
        <p class="contacto">${escapar(s.solicitante_email)}, ${escapar(s.solicitante_telefono)}</p>
        <p class="contacto">${escapar(s.direccion)}. Recibida el ${fecha}.</p>
        <p class="motivo">${escapar(s.motivo)}</p>
        ${s.observacion ? `<p class="observacion">Observación: ${escapar(s.observacion)}</p>` : ""}
      </div>
      ${s.estado === "pendiente" ? `
        <div class="solicitud-acciones">
          <button type="button" class="boton" data-decidir="aprobar" data-id="${s.id}" data-mascota="${escapar(nombreMascota)}" data-persona="${escapar(s.solicitante_nombre)}">Aprobar</button>
          <button type="button" class="boton boton-peligro" data-decidir="rechazar" data-id="${s.id}" data-mascota="${escapar(nombreMascota)}" data-persona="${escapar(s.solicitante_nombre)}">Rechazar</button>
        </div>` : ""}
    </article>`;
}

let decisionActual = null;

$("#lista-solicitudes").addEventListener("click", (evento) => {
  const boton = evento.target.closest("[data-decidir]");
  if (!boton) return;
  const { decidir, id, mascota, persona } = boton.dataset;
  decisionActual = { accion: decidir, id, mascota };

  const form = $("#form-decision");
  form.reset();
  form.querySelector(".error").textContent = "";
  const aprobar = decidir === "aprobar";
  $("#decision-titulo").textContent = aprobar ? `Aprobar la adopción de ${mascota}` : `Rechazar la solicitud de ${persona}`;
  $("#decision-detalle").textContent = aprobar
    ? `La adopción de ${mascota} quedará a nombre de ${persona} y se rechazarán las demás solicitudes pendientes.`
    : `La solicitud para adoptar a ${mascota} quedará rechazada.`;
  const confirmar = $("#decision-confirmar");
  confirmar.textContent = aprobar ? "Aprobar" : "Rechazar";
  $("#dialogo-decision").showModal();
});

$("#form-decision").addEventListener("submit", (evento) => {
  evento.preventDefault();
  const form = evento.target;
  enviarFormulario(form, async () => {
    const { accion, id, mascota } = decisionActual;
    await pedir(`${ADOPCIONES_API_URL}/solicitudes/${id}/${accion}`, {
      method: "POST",
      body: JSON.stringify({ observacion: form.elements.observacion.value.trim() || null }),
    });
    $("#dialogo-decision").close();
    avisar(accion === "aprobar" ? `Adopción de ${mascota} aprobada.` : "Solicitud rechazada.");
    cargarSolicitudes();
  });
});

// ---------- Navegación ----------

function mostrarVista(vista) {
  document.querySelectorAll(".pestana").forEach((p) => {
    if (p.dataset.vista === vista) p.setAttribute("aria-current", "page");
    else p.removeAttribute("aria-current");
  });
  $("#vista-mascotas").hidden = vista !== "mascotas";
  $("#vista-solicitudes").hidden = vista !== "solicitudes";
  if (vista === "mascotas") cargarMascotas();
  else cargarSolicitudes();
}

document.querySelectorAll(".pestana").forEach((p) => {
  p.addEventListener("click", () => mostrarVista(p.dataset.vista));
});
document.querySelectorAll("[data-cerrar]").forEach((b) => {
  b.addEventListener("click", () => b.closest("dialog").close());
});
$("#filtro-especie").addEventListener("change", cargarMascotas);
$("#filtro-estado").addEventListener("change", cargarMascotas);
$("#filtro-solicitud").addEventListener("change", cargarSolicitudes);

cargarMascotas();
