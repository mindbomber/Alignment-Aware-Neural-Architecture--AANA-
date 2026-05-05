const state = {
  adapters: [],
  selectedId: null,
};

const els = {
  search: document.getElementById("search"),
  risk: document.getElementById("risk"),
  surface: document.getElementById("surface"),
  pack: document.getElementById("pack"),
  role: document.getElementById("role"),
  clear: document.getElementById("clear"),
  list: document.getElementById("adapter-list"),
  details: document.getElementById("details"),
  adapterCount: document.getElementById("adapter-count"),
  strictCount: document.getElementById("strict-count"),
  surfaceCount: document.getElementById("surface-count"),
  visibleCount: document.getElementById("visible-count"),
};

function chip(label, className = "") {
  return `<span class="chip ${className}">${escapeHtml(label)}</span>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function listItems(values, empty = "None declared") {
  const items = (values || []).filter(Boolean);
  if (!items.length) return `<p class="empty">${empty}</p>`;
  return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function playgroundHref(adapter) {
  const isBridgePage = window.location.pathname === "/adapter-gallery" || window.location.pathname === "/adapter-gallery/";
  const base = isBridgePage ? "/playground" : "../demo/";
  const query = isBridgePage ? `?adapter=${encodeURIComponent(adapter.id)}` : "";
  return `${base}${query}`;
}

function options(select, values) {
  for (const value of values || []) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }
}

function matches(adapter) {
  const query = els.search.value.trim().toLowerCase();
  const risk = els.risk.value;
  const surface = els.surface.value;
  const pack = els.pack.value;
  const role = els.role.value;
  if (query && !(adapter.search_text || "").includes(query)) return false;
  if (risk && adapter.risk_tier !== risk) return false;
  if (surface && !(adapter.supported_surfaces || []).includes(surface)) return false;
  if (pack && !(adapter.packs || []).includes(pack)) return false;
  if (role && !(adapter.roles || []).includes(role)) return false;
  return true;
}

function visibleAdapters() {
  return state.adapters.filter(matches);
}

function applyQueryFilters() {
  const params = new URLSearchParams(window.location.search);
  els.search.value = params.get("q") || params.get("search") || "";
  els.risk.value = params.get("risk") || "";
  els.surface.value = params.get("surface") || "";
  els.pack.value = params.get("pack") || "";
  els.role.value = params.get("role") || "";
  return params.get("adapter") || params.get("adapter_id") || "";
}

function renderList() {
  const visible = visibleAdapters();
  els.visibleCount.textContent = visible.length;
  els.list.innerHTML = "";
  for (const adapter of visible) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `adapter-card ${adapter.id === state.selectedId ? "active" : ""}`;
    button.innerHTML = `
      <strong>${escapeHtml(adapter.title)}</strong>
      <p>${escapeHtml(adapter.workflow)}</p>
      <div class="chips">
        ${chip(adapter.risk_tier, adapter.risk_tier)}
        ${chip(`${adapter.required_evidence.length} evidence`)}
        ${chip(`${adapter.supported_surfaces.length} surfaces`)}
        ${(adapter.roles || []).slice(0, 2).map((item) => chip(item)).join("")}
      </div>
    `;
    button.addEventListener("click", () => selectAdapter(adapter.id));
    els.list.appendChild(button);
  }
  if (!visible.length) {
    els.list.innerHTML = `<p class="empty">No adapters match the current filters.</p>`;
  }
  if (!visible.some((adapter) => adapter.id === state.selectedId)) {
    selectAdapter(visible[0]?.id || null, false);
  }
}

function aixBlock(adapter) {
  return JSON.stringify(adapter.aix, null, 2);
}

function renderDetails(adapter) {
  if (!adapter) {
    els.details.innerHTML = `<p class="empty">Select an adapter to inspect its evidence, AIx tuning, surfaces, and example behavior.</p>`;
    return;
  }
  const expected = adapter.example_outputs.expected || {};
  els.details.innerHTML = `
    <h2>${escapeHtml(adapter.title)}</h2>
    <p class="workflow">${escapeHtml(adapter.workflow)}</p>
    <div class="detail-actions">
      <a class="button primary" href="${escapeHtml(playgroundHref(adapter))}">Try this adapter</a>
      <a class="button" href="#copy-${escapeHtml(adapter.id)}">Review command</a>
    </div>
    <div class="chips">
      ${chip(adapter.risk_tier, adapter.risk_tier)}
      ${(adapter.packs || []).map((item) => chip(item)).join("")}
      ${(adapter.roles || []).map((item) => chip(item)).join("")}
      ${(adapter.supported_surfaces || []).slice(0, 3).map((item) => chip(item)).join("")}
    </div>

    <div class="section grid">
      <div class="metric"><span>AIx beta</span><strong>${escapeHtml(adapter.aix.beta)}</strong></div>
      <div class="metric"><span>Accept threshold</span><strong>${escapeHtml(adapter.aix.thresholds.accept)}</strong></div>
      <div class="metric"><span>Hard constraints</span><strong>${escapeHtml(adapter.constraints.hard_constraint_count)}</strong></div>
      <div class="metric"><span>Candidate gate</span><strong>${escapeHtml(expected.candidate_gate || "-")}</strong></div>
      <div class="metric"><span>Try state</span><strong>${escapeHtml(adapter.readiness?.try || "-")}</strong></div>
      <div class="metric"><span>Pilot state</span><strong>${escapeHtml(adapter.readiness?.pilot || "-")}</strong></div>
      <div class="metric"><span>Production state</span><strong>${escapeHtml(adapter.readiness?.production || "-")}</strong></div>
    </div>

    <div class="section">
      <h3>Required Evidence</h3>
      ${listItems(adapter.required_evidence, "No structured evidence sources declared.")}
    </div>

    <div class="section">
      <h3>Supported Surfaces</h3>
      ${listItems(adapter.supported_surfaces)}
    </div>

    <div class="section">
      <h3>Example Input</h3>
      <div class="metric"><span>Prompt</span><strong>${escapeHtml(adapter.example_inputs.prompt)}</strong></div>
      <div class="metric"><span>Bad candidate</span><strong>${escapeHtml(adapter.example_inputs.bad_candidate)}</strong></div>
    </div>

    <div class="section">
      <h3>Expected Output</h3>
      <div class="grid">
        <div class="metric"><span>Gate decision</span><strong>${escapeHtml(expected.gate_decision)}</strong></div>
        <div class="metric"><span>Recommended action</span><strong>${escapeHtml(expected.recommended_action)}</strong></div>
      </div>
      <h3>Failing Constraints</h3>
      ${listItems(expected.failing_constraints)}
    </div>

    <div class="section">
      <h3>AIx Tuning</h3>
      <pre>${escapeHtml(aixBlock(adapter))}</pre>
    </div>

    <div class="section">
      <h3 id="copy-${escapeHtml(adapter.id)}">Copy Command</h3>
      <pre>${escapeHtml(adapter.example_outputs.copy_command)}</pre>
    </div>
  `;
}

function selectAdapter(id, rerender = true) {
  state.selectedId = id;
  const adapter = state.adapters.find((item) => item.id === id);
  renderDetails(adapter);
  if (rerender) renderList();
}

function updateSummary(payload) {
  els.adapterCount.textContent = payload.adapter_count;
  els.strictCount.textContent = payload.risk_tier_counts.strict || 0;
  els.surfaceCount.textContent = Object.keys(payload.surface_counts || {}).length;
}

function bindFilters() {
  for (const element of [els.search, els.risk, els.surface, els.pack, els.role]) {
    element.addEventListener("input", renderList);
  }
  els.clear.addEventListener("click", () => {
    els.search.value = "";
    els.risk.value = "";
    els.surface.value = "";
    els.pack.value = "";
    els.role.value = "";
    renderList();
  });
}

async function boot() {
  const dataUrl = new URL("data.json", document.currentScript.src);
  const response = await fetch(dataUrl, { cache: "no-store" });
  if (!response.ok) throw new Error(`Gallery data failed to load: HTTP ${response.status}`);
  const payload = await response.json();
  state.adapters = payload.adapters || [];
  options(els.risk, payload.filters?.risk_tiers || []);
  options(els.surface, payload.filters?.surfaces || []);
  options(els.pack, payload.filters?.packs || []);
  options(els.role, payload.filters?.roles || []);
  updateSummary(payload);
  bindFilters();
  const requestedAdapter = applyQueryFilters();
  const visible = visibleAdapters();
  const selected = visible.find((adapter) => adapter.id === requestedAdapter) || visible[0] || state.adapters[0];
  selectAdapter(selected?.id || null);
}

boot().catch((error) => {
  els.list.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
});
