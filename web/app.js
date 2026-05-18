/* Floridablanca · Balears 1787 — static SPA.
 *
 * Vanilla JS, single data.json source, no framework. Renders 111
 * pueblos with sortable/filterable list, per-pueblo detail panel, and
 * three aggregate views (demografia, comunitats religioses, comentari).
 */

const STATE = {
  data: null,
  pueblos: [],
  filtered: [],
  sortKey: "cod",
  sortDir: 1,
};

const $  = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const fmt = (n) =>
  n == null ? "–" : n.toLocaleString("ca-ES").replace(/ /g, ".");

const housingTotal = (p) =>
  p.population?.housing?.total?.T
  ?? p.population?.occupation?.total
  ?? null;

// ===== boot =================================================================

async function boot() {
  const res = await fetch("data.json", { cache: "no-cache" });
  STATE.data = await res.json();
  STATE.pueblos = STATE.data.pueblos.filter((p) => !p.parent_cod);
  STATE.filtered = [...STATE.pueblos];

  bindTabs();
  bindFilters();
  bindDetail();
  renderHome();
  renderPobles();
  renderDemografia();
  renderReligious();
  renderComentari();
}

// ===== tabs =================================================================

function bindTabs() {
  $$(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      $$(".tab").forEach((b) => b.classList.toggle("active", b === btn));
      const key = btn.dataset.tab;
      $$(".tab-content").forEach((c) =>
        c.classList.toggle("active", c.id === "tab-" + key)
      );
      window.scrollTo({ top: 0 });
    });
  });
}

// ===== home =================================================================

function renderHome() {
  const t = STATE.data.meta.totals;
  $("#stat-pueblos").textContent = fmt(t.pueblos);
  $("#stat-pop").textContent     = fmt(t.total_population);
  $("#stat-mal").textContent     = fmt(t.by_district.MAL || 0);
  $("#stat-men").textContent     = fmt(t.by_district.MEN || 0);
  $("#stat-ibi").textContent     = fmt(t.by_district.IBI || 0);
}

// ===== pobles list ==========================================================

function bindFilters() {
  const cats  = STATE.data.lookups.categories;
  const auths = STATE.data.lookups.authorities;
  const juris = STATE.data.lookups.jurisdictions;
  const dists = STATE.data.lookups.districts;

  for (const { code, label } of dists) {
    const o = document.createElement("option");
    o.value = code; o.textContent = `${label} (${code})`;
    $("#f-district").appendChild(o);
  }
  for (const { code, label } of cats) {
    const o = document.createElement("option");
    o.value = code; o.textContent = `${code} — ${label}`;
    $("#f-category").appendChild(o);
  }
  for (const { code, label } of juris) {
    const o = document.createElement("option");
    o.value = code; o.textContent = `${code} — ${label}`;
    $("#f-juris").appendChild(o);
  }
  for (const { code, label } of auths) {
    const o = document.createElement("option");
    o.value = code; o.textContent = `${code} — ${label}`;
    $("#f-auth").appendChild(o);
  }

  ["#f-text", "#f-district", "#f-category", "#f-juris", "#f-auth"]
    .forEach((sel) => $(sel).addEventListener("input", () => {
      applyFilters(); renderPobles();
    }));
  $("#btn-clear").addEventListener("click", () => {
    $("#f-text").value = "";
    $("#f-district").value = "";
    $("#f-category").value = "";
    $("#f-juris").value = "";
    $("#f-auth").value = "";
    applyFilters(); renderPobles();
  });

  $$(".pobles-table th.sortable").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (STATE.sortKey === key) STATE.sortDir *= -1;
      else { STATE.sortKey = key; STATE.sortDir = 1; }
      renderPobles();
    });
  });
}

function applyFilters() {
  const t = $("#f-text").value.trim().toLowerCase();
  const d = $("#f-district").value;
  const c = $("#f-category").value;
  const j = $("#f-juris").value;
  const a = $("#f-auth").value;
  STATE.filtered = STATE.pueblos.filter((p) => {
    if (t) {
      const hay = (p.name_current + " " + (p.name_1787 || "")).toLowerCase();
      if (!hay.includes(t)) return false;
    }
    if (d && p.district     !== d) return false;
    if (c && p.category     !== c) return false;
    if (j && p.jurisdiction !== j) return false;
    if (a && p.authority    !== a) return false;
    return true;
  });
}

function renderPobles() {
  const { sortKey, sortDir, filtered } = STATE;
  const valueFor = (p) => {
    if (sortKey === "population") return housingTotal(p) ?? -1;
    return p[sortKey] ?? "";
  };
  filtered.sort((a, b) => {
    const va = valueFor(a), vb = valueFor(b);
    if (typeof va === "number" && typeof vb === "number") return (va - vb) * sortDir;
    return String(va).localeCompare(String(vb), "ca") * sortDir;
  });

  $$(".pobles-table th.sortable").forEach((th) => {
    th.classList.remove("sorted-asc", "sorted-desc");
    if (th.dataset.sort === sortKey)
      th.classList.add(sortDir > 0 ? "sorted-asc" : "sorted-desc");
  });

  $("#filter-count").textContent = `${filtered.length} pobles`;

  const rows = filtered.map((p) => `
    <tr data-cod="${p.cod}">
      <td>${p.cod}</td>
      <td><strong>${p.name_current}</strong></td>
      <td><em>${p.name_1787 || ""}</em></td>
      <td>${p.category ? `<span class="pill" title="${p.category_label || ""}">${p.category}</span>` : ""}</td>
      <td>${p.jurisdiction ? `<span class="pill ${p.jurisdiction.toLowerCase()}" title="${p.jurisdiction_label || ""}">${p.jurisdiction}</span>` : ""}</td>
      <td title="${p.authority_label || ""}">${p.authority || ""}</td>
      <td title="${p.district_label || ""}">${p.district || ""}</td>
      <td class="num">${fmt(housingTotal(p))}</td>
    </tr>`).join("");
  $("#pobles-tbody").innerHTML = rows;

  $$("#pobles-tbody tr").forEach((tr) =>
    tr.addEventListener("click", () => openDetail(Number(tr.dataset.cod)))
  );
}

// ===== poble detail =========================================================

function bindDetail() {
  $("#detail-close").addEventListener("click", closeDetail);
  $("#detail-overlay").addEventListener("click", (e) => {
    if (e.target.id === "detail-overlay") closeDetail();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDetail();
  });
}

function openDetail(cod) {
  const p = STATE.pueblos.find((x) => x.cod === cod);
  if (!p) return;
  $("#detail-content").innerHTML = renderDetailHTML(p);
  $("#detail-overlay").classList.add("open");
  document.body.style.overflow = "hidden";
}
function closeDetail() {
  $("#detail-overlay").classList.remove("open");
  document.body.style.overflow = "";
}

function renderDetailHTML(p) {
  const meta = [
    ["Cod",                 p.cod],
    ["Categoria",           p.category ? `${p.category} — ${p.category_label || ""}` : null],
    ["Autoritat",           p.authority ? `${p.authority} — ${p.authority_label || ""}` : null],
    ["Jurisdicció",         p.jurisdiction ? `${p.jurisdiction} — ${p.jurisdiction_label || ""}` : null],
    ["Intendència",         p.intendancy],
    ["Partit",              p.district_label],
    ["Municipi actual",     p.current_municipality_name
                              ? `${String(p.current_municipality_code).padStart(3,"0")} ${p.current_municipality_name}`
                              : null],
    ["Manuscrit 1787 (RAH)", p.manuscript_page ? `p. ${p.manuscript_page}` : null],
    ["Fotograma INE",       p.ine_photogram],
  ].filter(([, v]) => v != null && v !== "");
  const metaHtml = `<dl class="detail-meta">${meta.map(([k,v]) =>
    `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("")}</dl>`;

  const obsHtml = p.observations
    ? `<div class="observations-note"><strong>Observacions:</strong> ${p.observations}</div>`
    : "";

  return `
    <h2>${p.name_current}</h2>
    <p class="detail-name1787">Denominació al Nomenclàtor de 1787: <em>${p.name_1787 || "(igual)"}</em></p>
    ${obsHtml}
    ${metaHtml}
    ${renderPopulationHTML(p)}
    ${renderOccupationHTML(p)}
    ${renderReligiousHTML(p)}
    ${renderWelfareHTML(p)}
    ${renderOtherCentresHTML(p)}
  `;
}

const MARITAL_LABELS = {
  total: "Total", single: "Solters", married: "Casats", widowed: "Vidus",
};
const AGE_ORDER = ["all", "<7", "7-16", "16-25", "25-40", "40-50", ">50"];
const AGE_LABELS = {
  all: "Tots", "<7": "< 7", "7-16": "7-16", "16-25": "16-25",
  "25-40": "25-40", "40-50": "40-50", ">50": "> 50",
};

function renderPopulationHTML(p) {
  if (!p.population || !p.population.marital) return "";
  const m = p.population.marital;

  const rows = AGE_ORDER.flatMap((age) => {
    const cells = [];
    for (const ms of ["total", "single", "married", "widowed"]) {
      const cell = m?.[ms]?.[age] || {};
      cells.push(cell);
    }
    if (cells.every((c) => Object.keys(c).length === 0)) return [];
    return [`<tr${age === "all" ? ' class="rollup"' : ""}>
        <td>${AGE_LABELS[age]}</td>
        ${cells.map((c) =>
          `<td>${fmt(c.T)}</td><td>${fmt(c.V)}</td><td>${fmt(c.M)}</td>`
        ).join("")}
    </tr>`];
  }).join("");

  const housing = p.population.housing || {};
  let housingBox = "";
  if (housing.total?.T) {
    housingBox = `
      <p style="margin:0 0 0.6em; font-size:0.9em;">
        Població total: <strong>${fmt(housing.total.T)}</strong>
        (varons ${fmt(housing.total.V)}, dones ${fmt(housing.total.M)}).
        ${housing.collective_religious?.T
          ? `Vivendes col·lectives religioses: ${fmt(housing.collective_religious.T)}. `
          : ""}
        ${housing.collective_other?.T
          ? `Altres col·lectives: ${fmt(housing.collective_other.T)}.`
          : ""}
      </p>`;
  }

  return `
    <div class="detail-section">
      <h3>Demografia (estat civil × edat × sexe)</h3>
      ${housingBox}
      <table class="demog-table">
        <thead>
          <tr>
            <th rowspan="2">Edat</th>
            ${Object.values(MARITAL_LABELS).map((l) =>
              `<th colspan="3" style="text-align:center;">${l}</th>`).join("")}
          </tr>
          <tr>
            ${Array(4).fill(0).map(() => "<th>T</th><th>V</th><th>M</th>").join("")}
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

const OCC_LABELS = {
  curas: "Curas (rectors)",
  beneficiados: "Beneficiats",
  tenientes_de_cura: "Tinents de cura",
  sacristanes: "Sagristans",
  acolitos: "Acòlits",
  ordenados_titulo_patrimonio: "Ordenats a títol de patrimoni",
  ordenados_de_menores: "Ordenats de menors",
  hidalgos: "Hidalgos",
  abogados: "Advocats",
  escribanos: "Escrivans",
  estudiantes: "Estudiants",
  labradores: "Llauradors",
  jornaleros: "Jornalers",
  comerciantes: "Comerciants",
  fabricantes: "Fabricants",
  artesanos: "Artesans",
  criados: "Criats",
  empleados_sueldo_real: "Empleats (sou reial)",
  fuero_militar: "Fur militar",
  dep_inquisicion: "Dep. Inquisició",
  sindicos_ord_relig: "Síndics d'ordes religiosos",
  depend_cruzada: "Dependents de Croada",
  demandantes: "Demandants",
  otros: "Altres",
  menores_sin_profesion: "Menors / sense professió",
  total: "Total",
};

function renderOccupationHTML(p) {
  const occ = p.population?.occupation;
  if (!occ || Object.keys(occ).length === 0) return "";
  const rows = Object.entries(OCC_LABELS).flatMap(([k, label]) => {
    const v = occ[k];
    if (v == null || v === 0) return [];
    const cls = k === "total" ? ' class="rollup"' : "";
    return [`<tr${cls}><td>${label}</td><td>${fmt(v)}</td></tr>`];
  }).join("");
  const note = p.population.occupation_notes
    ? `<p style="font-size:0.85em; color:var(--text-muted); margin-top:0.4em;">
        <em>${p.population.occupation_notes}</em></p>` : "";
  return `
    <div class="detail-section">
      <h3>Ocupacions declarades</h3>
      <table class="occ-table">
        <thead><tr><th>Ocupació</th><th>Persones</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      ${note}
    </div>`;
}

const FRIAR_KEYS = ["profesos", "novicios", "legos", "donados", "criados", "ninos", "otros"];
const NUN_KEYS   = ["profesas", "novicias", "sras_seglares", "ninas", "criadas", "donados", "criados", "otros_var", "otros_muj"];

function renderConventCard(c, kind) {
  const order = c.order ? `<p class="order">${kind === "friars" ? "Ordre" : "Ordre"}: <strong>${c.order}</strong></p>` : "";
  const m = c.members || {};
  const keys = kind === "friars" ? FRIAR_KEYS : kind === "nuns" ? NUN_KEYS : Object.keys(m);
  const items = keys
    .filter((k) => m[k] != null && m[k] !== 0)
    .map((k) => `<span><b>${m[k]}</b> ${prettyMemberKey(k)}</span>`)
    .join("");
  const label = kind === "friars" ? "Convent de frares" : kind === "nuns" ? "Convent de monges" : "Casa de religió";
  return `<div class="convent-card">
    <h4>${c.name || "(sense nom)"}</h4>
    <p class="order" style="font-style:italic; opacity:0.8;">${label}</p>
    ${order}
    <div class="members">${items || "<span><em>Sense detall numèric</em></span>"}</div>
  </div>`;
}

function prettyMemberKey(k) {
  const m = {
    profesos: "professos", profesas: "professes",
    novicios: "novicis", novicias: "novícies",
    legos: "llecs", donados: "donats",
    criados: "criats", criadas: "criades",
    ninos: "infants", ninas: "infantes",
    sras_seglares: "sres. seglars",
    otros: "altres", otros_var: "altres (homes)", otros_muj: "altres (dones)",
    titulares_varones: "titulars (homes)", titulares_mujeres: "titulars (dones)",
    otros_varones: "altres (homes)", otros_mujeres: "altres (dones)",
  };
  return m[k] || k;
}

function renderReligiousHTML(p) {
  if (!p.religious || p.religious.length === 0) return "";
  return `
    <div class="detail-section">
      <h3>Comunitats religioses</h3>
      ${p.religious.map((c) => renderConventCard(c, c.type)).join("")}
    </div>`;
}

const WELFARE_LABELS = {
  hospital: "Hospital", hospicio: "Hospici", casa_expositos: "Casa d'exposits",
};
function renderWelfareHTML(p) {
  if (!p.welfare || p.welfare.length === 0) return "";
  const cards = p.welfare.map((w) => {
    const roles = Object.entries(w.roles || {})
      .filter(([, v]) => v != null && v !== 0 && v !== "")
      .map(([k, v]) => `<span><b>${v}</b> ${prettyRoleKey(k)}</span>`).join("");
    const totals = w.total != null
      ? `<p class="total">Total: ${fmt(w.total)} (homes ${fmt(w.males)}, dones ${fmt(w.females)})</p>`
      : "";
    return `<div class="welfare-card">
      <h4>${w.name || "(sense nom)"}</h4>
      <p class="order" style="font-style:italic; opacity:0.8;">${WELFARE_LABELS[w.type] || w.type}</p>
      ${totals}
      <div class="roles">${roles || "<span><em>Sense detall</em></span>"}</div>
    </div>`;
  }).join("");
  return `<div class="detail-section"><h3>Centres benèfics i sanitaris</h3>${cards}</div>`;
}

function prettyRoleKey(k) {
  const m = {
    capellanes: "capellans", empleados: "empleats",
    facultativos: "facultatius", sirvientes: "servents",
    enfermos: "malalts", enfermas: "malaltes",
    locos: "bojos", locas: "boges",
    expositos: "exposits", expositas: "expòsites",
    otros_muj: "altres (dones)", otros: "altres",
    hombres: "homes", mujeres: "dones",
    ninos: "nens", ninas: "nenes",
    otras_acogidas: "altres acollides",
  };
  return m[k] || k;
}

function renderOtherCentresHTML(p) {
  if (!p.other_centres || p.other_centres.length === 0) return "";
  const cards = p.other_centres.map((c) => {
    const rows = c.roles.map(({ role, count }) =>
      `<tr><td>${role}</td><td>${fmt(count)}</td></tr>`
    ).join("");
    return `<div class="welfare-card">
      <h4>${c.name}</h4>
      <table class="members-table"><tbody>${rows}</tbody></table>
    </div>`;
  }).join("");
  return `<div class="detail-section"><h3>Altres centres</h3>${cards}</div>`;
}

// ===== demografia ==========================================================

function renderDemografia() {
  const pueblos = STATE.pueblos.filter((p) => housingTotal(p) != null);
  const totalPop = pueblos.reduce((s, p) => s + (housingTotal(p) || 0), 0);
  $("#demog-total-pop").textContent = fmt(totalPop);

  // Top 20 by population.
  const top = [...pueblos]
    .sort((a, b) => (housingTotal(b) || 0) - (housingTotal(a) || 0))
    .slice(0, 20);
  $("#chart-top-pueblos").innerHTML = renderBars(
    top.map((p) => ({ name: p.name_current, value: housingTotal(p) }))
  );

  // By district.
  const byDistrict = {};
  for (const p of pueblos) {
    const k = p.district_label || p.district || "—";
    byDistrict[k] = (byDistrict[k] || 0) + (housingTotal(p) || 0);
  }
  $("#chart-by-district").innerHTML = renderBars(
    Object.entries(byDistrict)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value),
    "alt"
  );

  // Marital × sex aggregate.
  const agg = { single: { V: 0, M: 0 }, married: { V: 0, M: 0 }, widowed: { V: 0, M: 0 } };
  for (const p of pueblos) {
    const m = p.population?.marital;
    if (!m) continue;
    for (const ms of ["single", "married", "widowed"]) {
      const all = m[ms]?.all || {};
      agg[ms].V += all.V || 0;
      agg[ms].M += all.M || 0;
    }
  }
  $("#chart-marital").innerHTML = renderBars([
    { name: "Solters",   value: agg.single.V },
    { name: "Solteres",  value: agg.single.M },
    { name: "Casats",    value: agg.married.V },
    { name: "Casades",   value: agg.married.M },
    { name: "Vidus",     value: agg.widowed.V },
    { name: "Vídues",    value: agg.widowed.M },
  ]);

  // Top occupations (sum excluding total / menores).
  const occAgg = {};
  for (const p of pueblos) {
    const occ = p.population?.occupation || {};
    for (const [k, v] of Object.entries(occ)) {
      if (k === "total" || k === "menores_sin_profesion") continue;
      occAgg[k] = (occAgg[k] || 0) + (v || 0);
    }
  }
  const topOcc = Object.entries(occAgg)
    .map(([k, v]) => ({ name: OCC_LABELS[k] || k, value: v }))
    .filter((x) => x.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, 15);
  $("#chart-occupations").innerHTML = renderBars(topOcc, "alt");
}

function renderBars(items, modClass = "") {
  if (items.length === 0) return "<p><em>Sense dades.</em></p>";
  const max = items.reduce((m, x) => Math.max(m, x.value), 0) || 1;
  return items.map((x) => {
    const pct = Math.max(2, (x.value / max) * 100);
    return `<div class="bar-row ${modClass}">
      <span class="name" title="${x.name}">${x.name}</span>
      <span class="bar" style="width: ${pct}%"></span>
      <span class="num">${fmt(x.value)}</span>
    </div>`;
  }).join("");
}

// ===== comunitats religioses (cross-pueblo list) ==========================

function renderReligious() {
  // Group all convents grouped by pueblo.
  const html = STATE.pueblos
    .filter((p) => p.religious.length > 0)
    .sort((a, b) => b.religious.length - a.religious.length)
    .map((p) => `
      <div class="chart-card" style="margin-bottom:1em;">
        <h3>${p.name_current} <span style="font-size:0.7em; color:var(--text-muted); font-weight:400;">— ${p.religious.length} comunitats</span></h3>
        ${p.religious.map((c) => renderConventCard(c, c.type)).join("")}
      </div>`).join("");
  $("#religious-list").innerHTML = html || "<p><em>Sense dades extretes.</em></p>";
}

// ===== comentari ==========================================================

function renderComentari() {
  const body = STATE.data.comentario || "";
  const nota = STATE.data.nota_1787 || "";
  $("#comentario-body").innerHTML = body
    .split(/\n{2,}/)
    .map((p) => `<p>${escapeHtml(p)}</p>`)
    .join("");
  $("#nota-1787").textContent = nota;
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ===== go ===================================================================

boot().catch((err) => {
  console.error(err);
  document.body.insertAdjacentHTML(
    "afterbegin",
    `<pre style="background:#fee; padding:1em;">Error de càrrega: ${err.message}</pre>`
  );
});
