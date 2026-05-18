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
  renderPyramid();
  renderMaritalByAge();
  renderOccupationStack();
  bindOccupationToggle();
  renderRatioChart();
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

  // Largest pueblo by population.
  const withPop = STATE.pueblos
    .map((p) => ({ p, pop: housingTotal(p) }))
    .filter((x) => x.pop != null)
    .sort((a, b) => b.pop - a.pop);
  if (withPop.length) {
    const top = withPop[0];
    $("#stat-toppop").textContent       = fmt(top.pop);
    $("#stat-toppop-label").textContent = `habitants a ${top.p.name_current}`;
  }

  // Per-district pueblo counts (Mallorca / Menorca / Ibiza-Formentera).
  $("#src-mal").textContent = fmt(t.by_district.MAL || 0);
  $("#src-men").textContent = fmt(t.by_district.MEN || 0);
  $("#src-ibi").textContent = fmt(t.by_district.IBI || 0);

  // Featured pueblo: pick a random one with population data so the
  // card looks substantive (not an empty entry like ALCUDIETA).
  const candidates = STATE.pueblos.filter((p) =>
    housingTotal(p) != null || (p.population && p.population.occupation));
  if (candidates.length) {
    const pick = candidates[Math.floor(Math.random() * candidates.length)];
    $("#featured-title").textContent = pick.name_current;
    const bits = [];
    if (pick.category_label) bits.push(pick.category_label);
    if (pick.district_label) bits.push(pick.district_label);
    if (pick.jurisdiction_label) bits.push(pick.jurisdiction_label.toLowerCase());
    const pop = housingTotal(pick);
    if (pop != null) bits.push(`${fmt(pop)} habitants`);
    $("#featured-meta").textContent = bits.join(" · ");

    // Short excerpt: name_1787 difference + top occupation if available.
    const excerptParts = [];
    if (pick.name_1787 && pick.name_1787 !== pick.name_current) {
      excerptParts.push(`Al Nomenclàtor del 1787 hi apareix com a <em>${pick.name_1787}</em>.`);
    }
    const occ = pick.population?.occupation;
    if (occ) {
      const sorted = Object.entries(occ)
        .filter(([k, v]) => v && k !== "total" && k !== "menores_sin_profesion")
        .sort((a, b) => b[1] - a[1]);
      if (sorted.length) {
        const [k, v] = sorted[0];
        excerptParts.push(`Ocupació més declarada: <strong>${OCC_LABELS[k] || k}</strong> (${fmt(v)}).`);
      }
    }
    if (pick.religious?.length) {
      excerptParts.push(`${pick.religious.length} comunitats religioses documentades.`);
    }
    $("#featured-excerpt").innerHTML = excerptParts.join(" ") || "Vegeu la fitxa per al detall.";

    $("#featured-open").onclick = () => openDetail(pick.cod);
    $("#home-featured").hidden = false;
  }
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
  $("#btn-export").addEventListener("click", exportCSV);

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
    if (sortKey === "municipality_official")
      return p.current_municipality_name_official ?? p.current_municipality_name ?? "";
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

  const rows = filtered.map((p) => {
    const muniOfficial = p.current_municipality_name_official;
    const muniINE      = p.current_municipality_name;
    const muniCell = muniOfficial
      ? `<span title="Forma INE 1986: ${muniINE || "—"}">${muniOfficial}</span>`
      : (muniINE || "");
    return `
    <tr data-cod="${p.cod}">
      <td>${p.cod}</td>
      <td><strong>${p.name_current}</strong></td>
      <td><em>${p.name_1787 || ""}</em></td>
      <td>${muniCell}</td>
      <td>${p.category ? `<span class="pill" title="${p.category_label || ""}">${p.category}</span>` : ""}</td>
      <td>${p.jurisdiction ? `<span class="pill ${p.jurisdiction.toLowerCase()}" title="${p.jurisdiction_label || ""}">${p.jurisdiction}</span>` : ""}</td>
      <td title="${p.authority_label || ""}">${p.authority || ""}</td>
      <td title="${p.district_label || ""}">${p.district || ""}</td>
      <td class="num">${fmt(housingTotal(p))}</td>
    </tr>`;
  }).join("");
  $("#pobles-tbody").innerHTML = rows;

  $$("#pobles-tbody tr").forEach((tr) =>
    tr.addEventListener("click", () => openDetail(Number(tr.dataset.cod)))
  );
}

// ===== CSV export ===========================================================

// One row per pueblo with the most useful flat columns. Honours the
// current filter selection so the downloaded file matches what the
// user sees on screen.
const CSV_COLUMNS = [
  ["cod",                       (p) => p.cod],
  ["name_current",              (p) => p.name_current],
  ["name_1787",                 (p) => p.name_1787],
  ["category",                  (p) => p.category],
  ["category_label",            (p) => p.category_label],
  ["authority",                 (p) => p.authority],
  ["authority_label",           (p) => p.authority_label],
  ["jurisdiction",              (p) => p.jurisdiction],
  ["jurisdiction_label",        (p) => p.jurisdiction_label],
  ["district",                  (p) => p.district],
  ["district_label",            (p) => p.district_label],
  ["current_municipality_code", (p) => p.current_municipality_code],
  ["current_municipality_name_1986",     (p) => p.current_municipality_name],
  ["current_municipality_name_official", (p) => p.current_municipality_name_official],
  ["manuscript_page_1787",      (p) => p.manuscript_page],
  ["ine_photogram",             (p) => p.ine_photogram],
  ["population_total",          (p) => housingTotal(p)],
  ["population_males",          (p) => p.population?.housing?.total?.V],
  ["population_females",        (p) => p.population?.housing?.total?.M],
  ["population_family_housing", (p) => p.population?.housing?.family?.T],
  ["population_collective_religious", (p) => p.population?.housing?.collective_religious?.T],
  ["population_collective_other",     (p) => p.population?.housing?.collective_other?.T],
  ["religious_communities",     (p) => p.religious?.length || 0],
  ["welfare_centres",           (p) => p.welfare?.length || 0],
  ["other_centres",             (p) => p.other_centres?.length || 0],
  ["observations",              (p) => p.observations],
];

function csvCell(v) {
  if (v == null) return "";
  const s = String(v);
  return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function exportCSV() {
  const header = CSV_COLUMNS.map((c) => c[0]).join(",");
  const lines = [header];
  for (const p of STATE.filtered) {
    lines.push(CSV_COLUMNS.map(([, fn]) => csvCell(fn(p))).join(","));
  }
  // BOM so Excel opens the file as UTF-8 directly (catalans, eñes, …).
  const blob = new Blob(["﻿" + lines.join("\n") + "\n"],
                       { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `floridablanca_balears_${STATE.filtered.length}_pobles.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
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
    ["Municipi actual",     p.current_municipality_name_official
                              ? `${String(p.current_municipality_code).padStart(3,"0")} ${p.current_municipality_name_official}`
                              + (p.current_municipality_name && p.current_municipality_name !== p.current_municipality_name_official
                                  ? ` <small style="font-weight:400; color:var(--text-muted);">(INE 1986: ${p.current_municipality_name})</small>`
                                  : "")
                              : (p.current_municipality_name
                                  ? `${String(p.current_municipality_code).padStart(3,"0")} ${p.current_municipality_name}`
                                  : null)],
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

// Population pyramid (age × sex). Aggregates by default, can be
// filtered to any single pueblo that has Table 3 (marital × age ×
// sex) data via the selector dropdown.
const PYRAMID_AGES = ["<7", "7-16", "16-25", "25-40", "40-50", ">50"];

function pueblosWithMaritalData() {
  return STATE.pueblos.filter((p) =>
    p.population && p.population.marital
    && p.population.marital.total
    && Object.keys(p.population.marital.total).length > 0
  );
}

function pyramidAggregate(pueblos) {
  const rows = PYRAMID_AGES.map((age) => ({ age, V: 0, M: 0 }));
  for (const p of pueblos) {
    const t = p.population.marital.total || {};
    for (const row of rows) {
      row.V += t[row.age]?.V || 0;
      row.M += t[row.age]?.M || 0;
    }
  }
  return rows;
}

function renderPyramid() {
  const sel = $("#pyramid-select");
  const opts = ['<option value="">Tot l\'arxipèlag</option>']
    .concat(
      pueblosWithMaritalData()
        .sort((a, b) => a.name_current.localeCompare(b.name_current, "ca"))
        .map((p) => `<option value="${p.cod}">${p.name_current}</option>`)
    );
  sel.innerHTML = opts.join("");
  sel.addEventListener("change", () => paintPyramid(sel.value));
  paintPyramid("");
}

function paintPyramid(codStr) {
  const target = codStr
    ? STATE.pueblos.filter((p) => String(p.cod) === codStr)
    : pueblosWithMaritalData();
  const rows = pyramidAggregate(target);

  const sumV = rows.reduce((s, r) => s + r.V, 0);
  const sumM = rows.reduce((s, r) => s + r.M, 0);
  const total = sumV + sumM;
  const max = rows.reduce((m, r) => Math.max(m, r.V, r.M), 1);

  const ratio = sumM ? (sumV / sumM * 100) : null;
  const ratioTxt = ratio ? `${ratio.toFixed(0)} varons per cada 100 dones` : "—";

  const where = codStr
    ? STATE.pueblos.find((p) => String(p.cod) === codStr)?.name_current || codStr
    : `${target.length} pobles amb dades`;

  $("#pyramid-meta").innerHTML =
    `<b>${where}</b> · Total: ${fmt(total)} habitants ` +
    `(<b>${fmt(sumV)}</b> varons, <b>${fmt(sumM)}</b> dones) · ${ratioTxt}.`;

  const cells = ['<div class="py-header left">Varons</div>',
                 '<div class="py-header">Edat</div>',
                 '<div class="py-header right">Dones</div>'];
  for (const r of rows) {
    const wV = r.V ? Math.max(2, (r.V / max) * 100) : 0;
    const wM = r.M ? Math.max(2, (r.M / max) * 100) : 0;
    const pV = total ? (r.V / total * 100).toFixed(1) : "0.0";
    const pM = total ? (r.M / total * 100).toFixed(1) : "0.0";
    cells.push(
      `<div class="pyramid-row-left">
         <span>${fmt(r.V)} <small>(${pV}%)</small></span>
         <span class="pyramid-bar-male" style="width:${wV}%"></span>
       </div>`,
      `<div class="pyramid-age">${r.age}</div>`,
      `<div class="pyramid-row-right">
         <span class="pyramid-bar-female" style="width:${wM}%"></span>
         <span><small>(${pM}%)</small> ${fmt(r.M)}</span>
       </div>`,
    );
  }
  $("#pyramid-chart").innerHTML = cells.join("");
}

// Occupation stacked bars per pueblo. Collapses the ~25 printed
// professions into seven canonical groups (pagesia / artesania /
// servei domèstic / clergat / noblesa-administració / militars /
// altres) so the chart is readable across 30 pueblos at once.
// menores_sin_profesion and total are excluded so the bar reflects
// the active workforce, not pop. distribution.
const OCC_GROUPS = [
  ["agri",     "Pagesia",                    "occ-agri",
   ["labradores", "jornaleros"]],
  ["craft",    "Artesania, comerç i indústria", "occ-craft",
   ["artesanos", "fabricantes", "comerciantes"]],
  ["service",  "Servei domèstic",            "occ-service",
   ["criados"]],
  ["clergy",   "Clergat",                    "occ-clergy",
   ["curas", "beneficiados", "tenientes_de_cura", "sacristanes",
    "acolitos", "ordenados_titulo_patrimonio", "ordenados_de_menores"]],
  ["nobility", "Noblesa, administració, justícia", "occ-nobility",
   ["hidalgos", "abogados", "escribanos", "empleados_sueldo_real",
    "sindicos_ord_relig", "dep_inquisicion", "depend_cruzada"]],
  ["military", "Fur militar",                "occ-military",
   ["fuero_militar"]],
  ["other",    "Estudiants i altres",        "occ-other",
   ["estudiantes", "demandantes", "otros"]],
];

// Cache the projected rows so flipping the mode toggle is instant
// (no DOM re-rendering of the legend, just bar widths).
let OCC_ROWS_CACHE = null;
let OCC_MAX_ACTIVE = 0;

function projectOccupationRows() {
  const rows = STATE.pueblos
    .filter((p) => p.population?.occupation)
    .map((p) => {
      const occ = p.population.occupation;
      const groups = {};
      let active = 0;
      for (const [key, _label, _cls, occList] of OCC_GROUPS) {
        let sum = 0;
        for (const o of occList) sum += occ[o] || 0;
        groups[key] = sum;
        active += sum;
      }
      return { p, groups, active };
    })
    .filter((x) => x.active > 0)
    .sort((a, b) => b.active - a.active);
  OCC_MAX_ACTIVE = rows.reduce((m, r) => Math.max(m, r.active), 0) || 1;
  OCC_ROWS_CACHE = rows;
}

function renderOccupationStack(mode = "relative") {
  if (!OCC_ROWS_CACHE) projectOccupationRows();
  const rows = OCC_ROWS_CACHE;

  $("#occ-legend").innerHTML = OCC_GROUPS
    .map(([_k, label, cls]) =>
      `<span><span class="swatch ${cls}"></span>${label}</span>`
    ).join("");

  $("#occ-stack").innerHTML = rows.map(({ p, groups, active }) => {
    // Bar width within its wrap: 100% in relative mode; proportional
    // to the global max in absolute mode.
    const barWidthPct = mode === "absolute"
      ? Math.max(1.5, (active / OCC_MAX_ACTIVE) * 100)
      : 100;
    // Segment widths inside the bar are always percentages of the
    // pueblo's own active count — that way the internal composition
    // stays readable regardless of mode.
    const segments = OCC_GROUPS.map(([key, label, cls]) => {
      const v = groups[key];
      if (!v) return "";
      const segPct = (v / active) * 100;
      const title = `${label}: ${fmt(v)} (${segPct.toFixed(1)}%)`;
      return `<span class="occ-seg ${cls}" style="width:${segPct}%" title="${title}"></span>`;
    }).join("");
    return `<div class="occ-row" data-cod="${p.cod}">
      <span class="occ-name">${p.name_current}</span>
      <span class="occ-bar-wrap">
        <span class="occ-bar" style="width:${barWidthPct.toFixed(1)}%">${segments}</span>
      </span>
      <span class="occ-count">${fmt(active)}</span>
    </div>`;
  }).join("");

  $$("#occ-stack .occ-row").forEach((row) =>
    row.addEventListener("click", () => openDetail(Number(row.dataset.cod)))
  );
}

function bindOccupationToggle() {
  $$('input[name="occ-mode"]').forEach((r) =>
    r.addEventListener("change", () => renderOccupationStack(r.value))
  );
}

// Marital × age × sex stacked pyramid. Mirrors the pyramid layout
// (V on the left, M on the right, age band at the centre) but each
// bar is normalised to 100% width and split into segments for
// solters / casats / vidus, so the marital composition per age-band
// jumps out at a glance.
const MARITAL_STATUSES = ["single", "married", "widowed"];
const MS_CLASS = {
  single: "ms-single",
  married: "ms-married",
  widowed: "ms-widowed",
};
const MS_LABEL_M = {
  single: "Solters",
  married: "Casats",
  widowed: "Vidus",
};
const MS_LABEL_F = {
  single: "Solteres",
  married: "Casades",
  widowed: "Vídues",
};

function aggregateMaritalByAge(pueblos) {
  const ages = PYRAMID_AGES;       // ["<7", "7-16", ..., ">50"]
  const rows = ages.map((age) => ({
    age,
    male:   { single: 0, married: 0, widowed: 0 },
    female: { single: 0, married: 0, widowed: 0 },
  }));
  for (const p of pueblos) {
    const m = p.population?.marital;
    if (!m) continue;
    for (const row of rows) {
      for (const ms of MARITAL_STATUSES) {
        row.male[ms]   += m[ms]?.[row.age]?.V || 0;
        row.female[ms] += m[ms]?.[row.age]?.M || 0;
      }
    }
  }
  return rows;
}

function renderMaritalByAge() {
  const sel = $("#marital-select");
  const opts = ['<option value="">Tot l\'arxipèlag</option>']
    .concat(
      pueblosWithMaritalData()
        .sort((a, b) => a.name_current.localeCompare(b.name_current, "ca"))
        .map((p) => `<option value="${p.cod}">${p.name_current}</option>`)
    );
  sel.innerHTML = opts.join("");
  sel.addEventListener("change", () => paintMaritalByAge(sel.value));
  paintMaritalByAge("");
}

function paintMaritalByAge(codStr) {
  const target = codStr
    ? STATE.pueblos.filter((p) => String(p.cod) === codStr)
    : pueblosWithMaritalData();
  const rows = aggregateMaritalByAge(target);

  // Totals.
  let totV = 0, totM = 0, totMar = 0, totWid = 0;
  for (const r of rows) {
    for (const ms of MARITAL_STATUSES) {
      totV += r.male[ms];
      totM += r.female[ms];
      if (ms === "married") totMar += r.male[ms] + r.female[ms];
      if (ms === "widowed") totWid += r.male[ms] + r.female[ms];
    }
  }
  const totAll = totV + totM;
  const where = codStr
    ? STATE.pueblos.find((p) => String(p.cod) === codStr)?.name_current || codStr
    : `${target.length} pobles amb dades`;
  $("#marital-meta").innerHTML =
    `<b>${where}</b> · Total ${fmt(totAll)} habitants · ` +
    `Casats/des: <b>${(totMar / totAll * 100).toFixed(1)}%</b> · ` +
    `Vidus/dues: <b>${(totWid / totAll * 100).toFixed(1)}%</b>`;

  // Header row.
  const cells = [
    '<div class="mc-header left">Varons (100 %)</div>',
    '<div class="mc-header">Edat</div>',
    '<div class="mc-header right">Dones (100 %)</div>',
  ];

  for (const row of rows) {
    const sumV = row.male.single + row.male.married + row.male.widowed;
    const sumM = row.female.single + row.female.married + row.female.widowed;

    const segV = MARITAL_STATUSES.map((ms) => {
      const v = row.male[ms];
      if (!v) return "";
      const pct = (v / sumV) * 100;
      const title = `${MS_LABEL_M[ms]} ${row.age}: ${fmt(v)} (${pct.toFixed(1)}%)`;
      return `<span class="ms-seg ${MS_CLASS[ms]}" style="width:${pct}%" title="${title}"></span>`;
    }).join("");
    const segM = MARITAL_STATUSES.map((ms) => {
      const v = row.female[ms];
      if (!v) return "";
      const pct = (v / sumM) * 100;
      const title = `${MS_LABEL_F[ms]} ${row.age}: ${fmt(v)} (${pct.toFixed(1)}%)`;
      return `<span class="ms-seg ${MS_CLASS[ms]}" style="width:${pct}%" title="${title}"></span>`;
    }).join("");

    cells.push(
      `<div class="marital-count left">${fmt(sumV)}</div>`,
      `<div class="marital-bar left">${segV}</div>`,
      `<div class="marital-age">${row.age}</div>`,
      `<div class="marital-bar right">${segM}</div>`,
      `<div class="marital-count right">${fmt(sumM)}</div>`,
    );
  }
  $("#marital-chart").innerHTML = cells.join("");
}

// Sex-ratio diverging bars. For every pueblo with marital_status=total
// age_group=all data, compute V/M*100 (men per 100 women) and draw a
// horizontal bar that diverges left of 100 (female-skewed) or right
// (male-skewed). Magnitude → one of five colour buckets.
function ratioBucket(r) {
  if (r >= 110) return ["ratio-strong-male",   "male"];
  if (r >= 103) return ["ratio-mid-male",      "male"];
  if (r >  100) return ["ratio-light-male",    "male"];
  if (r ===100) return ["ratio-light-male",    "male"];
  if (r >= 97)  return ["ratio-light-female",  "female"];
  if (r >= 90)  return ["ratio-mid-female",    "female"];
  return ["ratio-strong-female", "female"];
}

function renderRatioChart() {
  const rows = STATE.pueblos
    .filter((p) => p.population?.marital?.total?.all)
    .map((p) => {
      const all = p.population.marital.total.all;
      const v = all.V || 0;
      const m = all.M || 0;
      if (m === 0) return null;
      return { p, v, m, ratio: (v / m) * 100 };
    })
    .filter(Boolean)
    .sort((a, b) => b.ratio - a.ratio);

  // The half-bar scale: largest deviation from 100 anchors the
  // farthest-out bar at ~95% of the available half-width, so the
  // smaller-skew rows stay visually proportional.
  const maxDev = rows.reduce(
    (m, r) => Math.max(m, Math.abs(r.ratio - 100)), 1,
  );

  $("#ratio-chart").innerHTML = rows.map(({ p, v, m, ratio }) => {
    const [cls, side] = ratioBucket(ratio);
    const dev = Math.abs(ratio - 100);
    const widthPct = Math.min(100, (dev / maxDev) * 95);
    const segHTML = (side === "male")
      ? `<span class="neg-wrap"></span>
         <span class="pos-wrap"><span class="pos ${cls}" style="width:${widthPct}%"></span></span>`
      : `<span class="neg-wrap"><span class="neg ${cls}" style="width:${widthPct}%"></span></span>
         <span class="pos-wrap"></span>`;
    const title = `V=${fmt(v)} · M=${fmt(m)} · ${ratio.toFixed(1)} homes per cada 100 dones`;
    return `<div class="ratio-row" data-cod="${p.cod}" title="${title}">
      <span class="ratio-name">${p.name_current}</span>
      <span class="ratio-bar">${segHTML}</span>
      <span class="ratio-value">${ratio.toFixed(1)}</span>
    </div>`;
  }).join("");

  $$("#ratio-chart .ratio-row").forEach((row) =>
    row.addEventListener("click", () => openDetail(Number(row.dataset.cod)))
  );
}

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

// ===== comunitats religioses (cross-pueblo aggregates + list) =============

// Normalise the printed religious-order strings into ~12 canonical
// families, with a CSS class for colour. The 1986 facsimile prints
// 22 distinct labels (Franciscanos vs Franciscanos Observantes vs
// Capuchinos vs Mínimos vs Alcantarinos — all Franciscan family),
// which we collapse here so the visualisations stay legible.
const ORDER_FAMILIES = [
  // [family_label, css_class, regex matched against the printed string]
  ["Franciscans (i variants)", "ord-franciscan",  /franciscan|capuchin|mínim|minim|alcantarin|clarisa/i],
  ["Dominics (Predicadors)",   "ord-dominican",   /dominic|predicador/i],
  ["Agustins",                 "ord-augustinian", /agustin/i],
  ["Carmelites",               "ord-carmelite",   /carmelit/i],
  ["Mercedaris",               "ord-mercedarian", /mercedari/i],
  ["Trinitaris",               "ord-trinitarian", /trinitari/i],
  ["Jerònimes",                "ord-jeronymite",  /gerónim|jerónim|jeronim/i],
  ["Orde del Císter",          "ord-cistercian",  /císter|cister/i],
  ["Cartoixans",               "ord-cartusian",   /bruno|cartoix/i],
  ["Pauls (Vincentians)",      "ord-vincentian",  /vicente.*paul|paul/i],
  ["Clergues regulars",        "ord-other-clergy",/clérigos|clergues/i],
];
const ORDER_OTHER = ["Hermitatges i beateris", "ord-secular"];

function classifyOrder(orderStr) {
  if (!orderStr) return ORDER_OTHER;
  for (const fam of ORDER_FAMILIES) {
    if (fam[2].test(orderStr)) return [fam[0], fam[1]];
  }
  return ["Altres ordres", "ord-other-clergy"];
}

function communityMembers(c) {
  return Object.values(c.members || {}).reduce(
    (sum, v) => sum + (typeof v === "number" ? v : 0), 0,
  );
}

function renderReligious() {
  const pueblosWithReligious = STATE.pueblos.filter((p) => p.religious.length > 0);
  if (pueblosWithReligious.length === 0) {
    $("#religious-list").innerHTML = "<p><em>Sense dades extretes.</em></p>";
    return;
  }

  // ---------- Aggregate by canonical order family ----------------------
  const byFamily = new Map();   // family_label → { cssClass, members, convents }
  for (const p of pueblosWithReligious) {
    for (const c of p.religious) {
      const [fam, cls] = classifyOrder(c.order);
      const row = byFamily.get(fam) || { cssClass: cls, members: 0, convents: 0 };
      row.members  += communityMembers(c);
      row.convents += 1;
      byFamily.set(fam, row);
    }
  }
  const familyRows = [...byFamily.entries()]
    .map(([label, row]) => ({ label, ...row }))
    .sort((a, b) => b.members - a.members);

  const familyMax = familyRows.reduce((m, x) => Math.max(m, x.members), 0) || 1;
  const orderBars = familyRows.map((r) => `
    <div class="order-bar">
      <span class="label">${r.label}</span>
      <span class="bar ${r.cssClass}" style="width: ${Math.max(2, (r.members / familyMax) * 100)}%"></span>
      <span class="meta"><b>${fmt(r.members)}</b> persones · ${r.convents} cases</span>
    </div>`).join("");

  const legend = familyRows.map((r) =>
    `<span><span class="swatch ${r.cssClass}"></span>${r.label}</span>`
  ).join("");

  // ---------- Per-pueblo convent dot map -------------------------------
  // One row per pueblo with religious communities. The dots are sized
  // by member count (sqrt for visual fairness) and coloured by order
  // family. Click forwards to the pueblo detail panel.
  const allMembers = pueblosWithReligious.flatMap((p) =>
    p.religious.map(communityMembers));
  const maxMembers = Math.max(...allMembers, 1);
  const sortedPueblos = [...pueblosWithReligious]
    .map((p) => ({
      p,
      totalMembers: p.religious.reduce((s, c) => s + communityMembers(c), 0),
    }))
    .sort((a, b) => b.totalMembers - a.totalMembers);

  const dotMap = sortedPueblos.map(({ p, totalMembers }) => {
    const dots = p.religious.map((c) => {
      const [, cls] = classifyOrder(c.order);
      const m = communityMembers(c);
      // Diameter 8-30px, sqrt scale.
      const size = Math.max(8, Math.round(8 + 22 * Math.sqrt(m / maxMembers)));
      const title = `${c.name || "(sense nom)"}${c.order ? ` · ${c.order}` : ""} · ${m} persones`;
      return `<span class="convent-dot ${cls}" style="width:${size}px;height:${size}px" title="${title}"></span>`;
    }).join("");
    return `<div class="convent-map-row" data-cod="${p.cod}">
      <span class="pueblo-name">${p.name_current}</span>
      <span class="dots">${dots}</span>
      <span class="count"><b>${p.religious.length}</b> · ${fmt(totalMembers)}</span>
    </div>`;
  }).join("");

  // ---------- Bottom: full per-pueblo list (existing behaviour) --------
  const fullList = pueblosWithReligious
    .sort((a, b) => b.religious.length - a.religious.length)
    .map((p) => `
      <div class="chart-card" style="margin-bottom:1em;">
        <h3>${p.name_current} <span style="font-size:0.7em; color:var(--text-muted); font-weight:400;">— ${p.religious.length} comunitats</span></h3>
        ${p.religious.map((c) => renderConventCard(c, c.type)).join("")}
      </div>`).join("");

  $("#religious-list").innerHTML = `
    <div class="chart-card" style="margin-bottom:1.5em;">
      <h3>Membres per ordre religiós (arxipèlag balear)</h3>
      <p style="font-size:0.85em; color:var(--text-muted); margin:0 0 0.8em;">
        Tots els membres de cada ordre sumats a través de les seves
        cases (professos + novicis + llecs + donats + criats + infants).
        Permet veure quina ordre era hegemònica al 1787.
      </p>
      ${orderBars}
    </div>

    <div class="chart-card" style="margin-bottom:1.5em;">
      <h3>Convents per poble</h3>
      <p style="font-size:0.85em; color:var(--text-muted); margin:0 0 0.6em;">
        Cada cercle és una comunitat. Diàmetre = nombre total de
        membres (escala arrel quadrada). Color = ordre religiós.
        Clic damunt el poble per veure'n el detall.
      </p>
      <div class="order-legend">${legend}</div>
      <div class="convent-map">${dotMap}</div>
    </div>

    <h3 style="font-family:Georgia,serif; margin:1.5em 0 0.8em; color:var(--accent-dark);">
      Llista completa per poble
    </h3>
    ${fullList}
  `;

  // Wire up clicks on the convent-map rows.
  $$("#religious-list .convent-map-row").forEach((row) =>
    row.addEventListener("click", () => openDetail(Number(row.dataset.cod)))
  );
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
