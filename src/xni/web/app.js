import cytoscape from "/static/vendor/cytoscape.min.js";

const $ = (id) => document.getElementById(id);
const controls = {
  target: $("target-filter"),
  topic: $("topic-filter"),
  type: $("type-filter"),
  newOnly: $("new-only"),
  newDays: $("new-days"),
  coverage: $("coverage-filter"),
  coverageValue: $("coverage-value"),
  search: $("search-input"),
  layout: $("layout-select"),
  maxAccounts: $("max-accounts"),
  reload: $("reload-button"),
  fit: $("fit-button"),
  status: $("status-banner"),
  empty: $("empty-state"),
  detail: $("detail-panel"),
  summary: $("graph-summary"),
};

let cy = null;
let graphPayload = null;
const classifierVersion = "rule-v1";

function status(message, isError = false) {
  controls.status.textContent = message;
  controls.status.classList.toggle("error", isError);
}

async function requestJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body.detail) detail = body.detail;
    } catch (_) {}
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function fillSelect(select, values, allLabel) {
  const current = select.value;
  select.replaceChildren(new Option(allLabel, ""));
  values.forEach((value) => select.add(new Option(value, value)));
  if ([...select.options].some((option) => option.value === current)) select.value = current;
}

async function loadOptions() {
  const data = await requestJson(`/api/graph/options?classifier_version=${encodeURIComponent(classifierVersion)}`);
  fillSelect(controls.target, data.targets, "전체 Target");
  fillSelect(controls.topic, data.topics, "전체 Topic");
  fillSelect(controls.type, data.account_types, "전체 Type");
}

function graphUrl() {
  const params = new URLSearchParams({
    classifier_version: classifierVersion,
    new_only: String(controls.newOnly.checked),
    new_account_days: String(Math.max(0, Number(controls.newDays.value) || 90)),
    min_target_coverage: String(Number(controls.coverage.value) || 0),
    max_accounts: String(Math.min(2000, Math.max(1, Number(controls.maxAccounts.value) || 500))),
  });
  if (controls.target.value) params.set("target", controls.target.value);
  if (controls.topic.value) params.set("topic", controls.topic.value);
  if (controls.type.value) params.set("account_type", controls.type.value);
  return `/api/graph?${params.toString()}`;
}

function cytoscapeStyle() {
  return [
    {
      selector: "node",
      style: {
        label: "data(username)",
        "font-size": 10,
        color: "#cbd7e6",
        "text-valign": "bottom",
        "text-margin-y": 7,
        "background-color": "#8794a7",
        width: 18,
        height: 18,
        "border-width": 1,
        "border-color": "#334156",
      },
    },
    {
      selector: 'node[kind = "target"]',
      style: {
        "background-color": "#6fa6ff",
        width: 34,
        height: 34,
        "font-size": 12,
        "font-weight": 700,
        "border-width": 2,
        "border-color": "#a9caff",
      },
    },
    {
      selector: 'node[is_central = true]',
      style: { "background-color": "#56d6a1", width: 26, height: 26 },
    },
    {
      selector: 'node[is_bridge = true]',
      style: { "border-width": 4, "border-color": "#f4c35e" },
    },
    {
      selector: 'node[is_new = true]',
      style: { shape: "diamond" },
    },
    {
      selector: "edge",
      style: {
        width: 1,
        "line-color": "#334055",
        "curve-style": "haystack",
        opacity: 0.65,
      },
    },
    {
      selector: ".search-muted",
      style: { opacity: 0.12 },
    },
    {
      selector: ":selected",
      style: { "overlay-color": "#6fa6ff", "overlay-opacity": 0.18, "overlay-padding": 8 },
    },
  ];
}

function currentLayout() {
  const name = controls.layout.value;
  const common = { name, animate: true, animationDuration: 350, fit: true, padding: 35 };
  if (name === "cose") return { ...common, nodeRepulsion: 7000, idealEdgeLength: 80 };
  if (name === "concentric") return { ...common, concentric: (n) => n.data("followed_by_targets") || 0, levelWidth: () => 1 };
  if (name === "breadthfirst") return { ...common, directed: false, spacingFactor: 1.4 };
  if (name === "grid") return { ...common, avoidOverlap: true };
  return common;
}

function renderGraph(payload) {
  graphPayload = payload;
  controls.empty.hidden = payload.meta.account_count > 0;
  const suffix = payload.meta.truncated ? ` · 상위 ${payload.meta.account_count}개만 표시` : "";
  controls.summary.textContent = `Target ${payload.meta.target_count} · Account ${payload.meta.account_count} · Edge ${payload.meta.edge_count}${suffix}`;

  if (cy) cy.destroy();
  cy = cytoscape({
    container: $("cy"),
    elements: [...payload.nodes, ...payload.edges],
    style: cytoscapeStyle(),
    layout: currentLayout(),
    minZoom: 0.08,
    maxZoom: 4,
    wheelSensitivity: 0.2,
  });

  cy.on("tap", "node", async (event) => {
    const node = event.target;
    cy.nodes().unselect();
    node.select();
    await showNodeDetail(node.data());
  });
  applySearch();
}

function pct(value) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`;
}

function metric(label, value) {
  return `<div class="metric"><span>${label}</span><strong>${value ?? "-"}</strong></div>`;
}

function chips(values) {
  if (!values?.length) return '<span class="muted">없음</span>';
  return `<div class="chips">${values.map((value) => `<span class="chip">${escapeHtml(value)}</span>`).join("")}</div>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function showNodeDetail(data) {
  controls.detail.innerHTML = `<div class="detail-card"><h2>${escapeHtml(data.display_name || data.username)}</h2><div class="handle">@${escapeHtml(data.username)}</div><p class="muted">상세 분석을 불러오는 중…</p></div>`;
  try {
    if (data.kind === "target") {
      const fp = await requestJson(`/api/analysis/fingerprints/${encodeURIComponent(data.username)}?classifier_version=${encodeURIComponent(classifierVersion)}`);
      const topics = (fp.top_topics || []).slice(0, 6);
      const associations = (fp.public_associations || []).slice(0, 6);
      controls.detail.innerHTML = `
        <div class="detail-card">
          <h2>${escapeHtml(data.display_name || data.username)}</h2>
          <div class="handle">@${escapeHtml(data.username)} · Target</div>
          <div class="metric-grid">
            ${metric("Following", fp.following_count)}
            ${metric("신생계정", pct(fp.new_account_ratio))}
            ${metric("Shared network", pct(fp.shared_network_concentration))}
            ${metric("Topic HHI", Number(fp.topic_concentration || 0).toFixed(3))}
            ${metric("Topic diversity", Number(fp.topic_diversity || 0).toFixed(3))}
            ${metric("미분류", pct(fp.unclassified_ratio))}
          </div>
          <h3>주요 Topic</h3>
          <ul class="detail-list">${topics.map((item) => `<li>${escapeHtml(item.topic)} · ${pct(item.share)}</li>`).join("") || '<li class="muted">분류 데이터 없음</li>'}</ul>
          <h3>공개 Association</h3>
          <ul class="detail-list">${associations.map((item) => `<li>${escapeHtml(item.value)} · ${escapeHtml(item.association_type)} · ${item.account_count}</li>`).join("") || '<li class="muted">추출 데이터 없음</li>'}</ul>
        </div>`;
      return;
    }

    let classification = null;
    try {
      classification = await requestJson(`/api/accounts/${data.account_id}/classification?classifier_version=${encodeURIComponent(classifierVersion)}`);
    } catch (error) {
      if (error.status !== 404) throw error;
    }
    controls.detail.innerHTML = `
      <div class="detail-card">
        <h2>${escapeHtml(data.display_name || data.username)}</h2>
        <div class="handle">@${escapeHtml(data.username)} · ${escapeHtml(data.account_type || "Unknown")}</div>
        <div class="metric-grid">
          ${metric("Followers", data.followers_count)}
          ${metric("Following", data.following_count)}
          ${metric("계정 나이", data.age_days == null ? "-" : `${data.age_days}일`)}
          ${metric("Target coverage", pct(data.target_coverage))}
          ${metric("Target 연결", data.followed_by_targets)}
          ${metric("View betweenness", Number(data.view_betweenness || 0).toFixed(4))}
        </div>
        <h3>Topic</h3>
        ${chips(data.topics || [])}
        <h3>분류 근거</h3>
        ${classification ? `<p>${escapeHtml(classification.account_type_evidence)}</p><ul class="detail-list">${classification.topics.map((item) => `<li>${escapeHtml(item.topic)} · ${(item.confidence * 100).toFixed(0)}%<br><span class="muted">${escapeHtml(item.evidence)}</span></li>`).join("")}</ul>` : '<p class="muted">저장된 rule-v1 분류 결과가 없습니다.</p>'}
        <p class="muted">Central/Bridge 값은 표시된 관계망의 수치 신호이며 조직성이나 개인 속성을 뜻하지 않습니다.</p>
      </div>`;
  } catch (error) {
    controls.detail.innerHTML = `<div class="error-box">상세 정보를 불러오지 못했습니다: ${escapeHtml(error.message)}</div>`;
  }
}

function applySearch() {
  if (!cy) return;
  const query = controls.search.value.trim().toLowerCase().replace(/^@/, "");
  cy.elements().removeClass("search-muted");
  if (!query) return;
  cy.nodes().forEach((node) => {
    const username = String(node.data("username") || "").toLowerCase();
    const displayName = String(node.data("display_name") || "").toLowerCase();
    if (!username.includes(query) && !displayName.includes(query)) node.addClass("search-muted");
  });
  cy.edges().forEach((edge) => {
    if (edge.source().hasClass("search-muted") && edge.target().hasClass("search-muted")) edge.addClass("search-muted");
  });
}

async function loadGraph() {
  status("그래프 계산 중…");
  try {
    const payload = await requestJson(graphUrl());
    renderGraph(payload);
    status(`Account ${payload.meta.account_count} · Edge ${payload.meta.edge_count}`);
  } catch (error) {
    status(error.message, true);
    controls.empty.hidden = false;
  }
}

function rerunLayout() {
  if (cy) cy.layout(currentLayout()).run();
}

controls.coverage.addEventListener("input", () => {
  controls.coverageValue.value = `${Math.round(Number(controls.coverage.value) * 100)}%`;
});
controls.search.addEventListener("input", applySearch);
controls.layout.addEventListener("change", rerunLayout);
controls.fit.addEventListener("click", () => cy?.fit(undefined, 35));
controls.reload.addEventListener("click", loadGraph);
[controls.target, controls.topic, controls.type, controls.newOnly].forEach((control) => control.addEventListener("change", loadGraph));

(async function init() {
  try {
    await loadOptions();
    await loadGraph();
  } catch (error) {
    status(error.message, true);
  }
})();
