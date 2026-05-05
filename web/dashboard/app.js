const els = {
  refresh: document.getElementById("refresh"),
  statusTitle: document.getElementById("status-title"),
  statusDetail: document.getElementById("status-detail"),
  auditPath: document.getElementById("audit-path"),
  totalRecords: document.getElementById("total-records"),
  gatePassFail: document.getElementById("gate-pass-fail"),
  aixStats: document.getElementById("aix-stats"),
  hardBlockers: document.getElementById("hard-blockers"),
  violationTotal: document.getElementById("violation-total"),
  shadowBlockRate: document.getElementById("shadow-block-rate"),
  gateChart: document.getElementById("gate-chart"),
  actionChart: document.getElementById("action-chart"),
  violationChart: document.getElementById("violation-chart"),
  shadowChart: document.getElementById("shadow-chart"),
  trendTable: document.getElementById("trend-table"),
  adapterTable: document.getElementById("adapter-table"),
  familyTable: document.getElementById("family-table"),
  blockerChart: document.getElementById("blocker-chart"),
};

function pct(value) {
  return `${Math.round((Number(value) || 0) * 100)}%`;
}

function countMapToItems(map) {
  return Object.entries(map || {})
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

function clearNode(node, message = "No data yet.") {
  node.innerHTML = "";
  const empty = document.createElement("div");
  empty.className = "empty";
  empty.textContent = message;
  node.appendChild(empty);
}

function renderBars(node, items, options = {}) {
  node.innerHTML = "";
  if (!items || items.length === 0) {
    clearNode(node, options.empty || "No data yet.");
    return;
  }
  const max = Math.max(...items.map((item) => item.count), 1);
  for (const item of items) {
    const row = document.createElement("div");
    row.className = "bar-row";
    const label = document.createElement("div");
    label.className = "bar-label";
    label.textContent = item.label;
    const track = document.createElement("div");
    track.className = "bar-track";
    const fill = document.createElement("div");
    fill.className = `bar-fill ${item.className || ""}`.trim();
    fill.style.width = `${Math.max(3, (item.count / max) * 100)}%`;
    track.appendChild(fill);
    const value = document.createElement("div");
    value.className = "bar-value";
    value.textContent = item.count;
    row.append(label, track, value);
    node.appendChild(row);
  }
}

function compactCounts(map, limit = 4) {
  const items = countMapToItems(map).slice(0, limit);
  if (!items.length) return "-";
  return items.map((item) => `${item.label}: ${item.count}`).join(", ");
}

function pills(map) {
  const fragment = document.createDocumentFragment();
  const items = countMapToItems(map);
  if (!items.length) {
    fragment.append("-");
    return fragment;
  }
  for (const item of items.slice(0, 6)) {
    const pill = document.createElement("span");
    pill.className = "pill";
    pill.textContent = `${item.label} ${item.count}`;
    fragment.appendChild(pill);
  }
  return fragment;
}

function renderTrendTable(rows) {
  els.trendTable.innerHTML = "";
  if (!rows || rows.length === 0) {
    clearNode(els.trendTable, "No trend data yet.");
    return;
  }
  const table = document.createElement("table");
  table.innerHTML = `
    <thead>
      <tr>
        <th>Date</th>
        <th>Checks</th>
        <th>Gate</th>
        <th>Actions</th>
        <th>Violations</th>
        <th>AIx</th>
        <th>Shadow</th>
      </tr>
    </thead>
  `;
  const body = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    const aix = row.aix || {};
    tr.innerHTML = `
      <td>${row.id}</td>
      <td>${row.total}</td>
      <td>${compactCounts(row.gate_decisions)}</td>
      <td>${compactCounts(row.recommended_actions)}</td>
      <td>${row.violation_total}</td>
      <td>${aix.average ?? "-"} / ${aix.min ?? "-"} / ${aix.max ?? "-"}</td>
      <td>${pct(row.shadow_would_block_rate)} block, ${pct(row.shadow_would_intervene_rate)} intervene</td>
    `;
    body.appendChild(tr);
  }
  table.appendChild(body);
  els.trendTable.appendChild(table);
}

function renderAdapterTable(rows) {
  els.adapterTable.innerHTML = "";
  if (!rows || rows.length === 0) {
    clearNode(els.adapterTable, "No adapter checks yet.");
    return;
  }
  const table = document.createElement("table");
  table.innerHTML = `
    <thead>
      <tr>
        <th>Adapter</th>
        <th>Checks</th>
        <th>Actions</th>
        <th>Violations</th>
        <th>AIx avg/min</th>
        <th>Hard blockers</th>
        <th>Shadow</th>
      </tr>
    </thead>
  `;
  const body = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    const aix = row.aix || {};
    const cells = [
      row.id,
      String(row.total),
      compactCounts(row.recommended_actions),
      String(row.violation_total),
      `${aix.average ?? "-"} / ${aix.min ?? "-"}`,
      "",
      `${pct(row.shadow_would_block_rate)} block`,
    ];
    for (const value of cells) {
      const td = document.createElement("td");
      if (value === "") {
        td.appendChild(pills(row.hard_blockers));
      } else {
        td.textContent = value;
      }
      tr.appendChild(td);
    }
    body.appendChild(tr);
  }
  table.appendChild(body);
  els.adapterTable.appendChild(table);
}

function renderFamilyTable(rows) {
  els.familyTable.innerHTML = "";
  if (!rows || rows.length === 0) {
    clearNode(els.familyTable, "No family checks yet.");
    return;
  }
  const table = document.createElement("table");
  table.innerHTML = `
    <thead>
      <tr>
        <th>Family</th>
        <th>Usage</th>
        <th>Revise / defer / refuse</th>
        <th>AIx avg/min/max</th>
        <th>Hard blockers</th>
        <th>Human review</th>
        <th>Evidence missing</th>
        <th>Shadow would block</th>
      </tr>
    </thead>
  `;
  const body = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    const aix = row.aix || {};
    const cells = [
      row.id,
      String(row.adapter_usage ?? row.total ?? 0),
      `${pct(row.revise_rate)} / ${pct(row.defer_rate)} / ${pct(row.refuse_rate)}`,
      `${aix.average ?? "-"} / ${aix.min ?? "-"} / ${aix.max ?? "-"}`,
      String(row.hard_blocker_total || 0),
      `${row.human_review_escalations || 0} (${pct(row.human_review_escalation_rate)})`,
      `${row.evidence_missing || 0} (${pct(row.evidence_missing_rate)})`,
      pct(row.shadow_would_block_rate),
    ];
    for (const value of cells) {
      const td = document.createElement("td");
      td.textContent = value;
      tr.appendChild(td);
    }
    body.appendChild(tr);
  }
  table.appendChild(body);
  els.familyTable.appendChild(table);
}

function render(payload) {
  const cards = payload.cards || {};
  const aix = payload.aix || {};
  els.statusTitle.textContent = payload.status === "ok" ? "Dashboard ready" : "Dashboard waiting for audit data";
  els.statusDetail.textContent = payload.message || `${payload.record_count || 0} redacted audit record(s) loaded.`;
  els.auditPath.textContent = payload.audit_log_path || "No audit log configured";
  els.totalRecords.textContent = cards.total_records || 0;
  els.gatePassFail.textContent = `${cards.gate_pass || 0} / ${cards.gate_fail || 0}`;
  els.aixStats.textContent = aix.count ? `${aix.average} / ${aix.min} / ${aix.max}` : "-";
  els.hardBlockers.textContent = cards.hard_blocker_total || 0;
  els.violationTotal.textContent = cards.violation_total || 0;
  els.shadowBlockRate.textContent = pct(cards.shadow_would_block_rate);

  renderBars(els.gateChart, countMapToItems(payload.gate_decisions));
  renderBars(
    els.actionChart,
    countMapToItems(payload.recommended_actions).map((item) => ({
      ...item,
      className: item.label === "accept" ? "" : item.label === "refuse" ? "danger" : "warn",
    }))
  );
  renderBars(
    els.violationChart,
    (payload.top_violations || []).map((item) => ({ label: item.code, count: item.count, className: "warn" })),
    { empty: "No violations recorded." }
  );
  renderBars(
    els.shadowChart,
    countMapToItems((payload.shadow_mode || {}).would_routes).map((item) => ({
      ...item,
      className: item.label === "pass" ? "" : item.label === "refuse" ? "danger" : "alt",
    })),
    { empty: "No shadow-mode records yet." }
  );
  renderBars(
    els.blockerChart,
    ((payload.hard_blockers || {}).items || []).map((item) => ({ label: item.code, count: item.count, className: "danger" })),
    { empty: "No hard blockers recorded." }
  );
  renderTrendTable(payload.violation_trends || []);
  renderAdapterTable(payload.adapter_breakdown || []);
  renderFamilyTable(payload.family_breakdown || []);
}

async function loadMetrics() {
  els.refresh.disabled = true;
  els.refresh.textContent = "Refreshing...";
  try {
    const response = await fetch("/dashboard/metrics", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `Metrics request failed: HTTP ${response.status}`);
    render(payload);
  } catch (error) {
    els.statusTitle.textContent = "Dashboard error";
    els.statusDetail.textContent = error.message;
  } finally {
    els.refresh.disabled = false;
    els.refresh.textContent = "Refresh";
  }
}

els.refresh.addEventListener("click", loadMetrics);
loadMetrics();
