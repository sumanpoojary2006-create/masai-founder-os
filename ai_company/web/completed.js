function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function getApiBase() {
  return window.MASAI_API_BASE_URL || localStorage.getItem("masai_api_base_url") || "";
}

function apiUrl(path) {
  const base = getApiBase().trim().replace(/\/+$/, "");
  return base ? `${base}${path}` : path;
}

function renderCompletedSummary(tasks) {
  const el = document.getElementById("completed-summary");
  if (!el) {
    return;
  }

  const completed = tasks.filter((task) => task.status === "completed");
  const failed = tasks.filter((task) => task.status === "failed");

  el.innerHTML = `
    <div class="metric-card">
      <span class="metric-value">${completed.length}</span>
      <span class="metric-label">Completed tasks</span>
    </div>
    <div class="metric-card">
      <span class="metric-value">${failed.length}</span>
      <span class="metric-label">Failed tasks</span>
    </div>
    <div class="metric-card">
      <span class="metric-value">${tasks.length}</span>
      <span class="metric-label">Archived requests</span>
    </div>
  `;
}

function renderCompletedTasks(tasks) {
  const el = document.getElementById("completed-task-list");
  if (!el) {
    return;
  }

  if (!tasks.length) {
    el.innerHTML = `<div class="empty-state">No completed requests yet.</div>`;
    return;
  }

  el.innerHTML = tasks
    .map(
      (task) => `
        <article class="completed-card">
          <div class="card-row">
            <div>
              <h3>${escapeHtml(task.title)}</h3>
              <p class="meta-text">${escapeHtml(task.department_label || "CEO Routed")} • ${escapeHtml(task.completed_at || task.updated_at || "-")}</p>
            </div>
            <span class="status-pill" data-status="${escapeHtml(task.status)}">${escapeHtml(task.status.replaceAll("_", " "))}</span>
          </div>
          <div class="completed-card-grid">
            <div>
              <p class="summary-label">Founder request</p>
              <p class="summary-text">${escapeHtml(task.request)}</p>
            </div>
            <div>
              <p class="summary-label">CEO reason</p>
              <p class="summary-text">${escapeHtml(task.ceo_reason || "No CEO note recorded.")}</p>
            </div>
            <div>
              <p class="summary-label">Database effect</p>
              <p class="summary-text">${escapeHtml(task.data_effect || "No direct database effect recorded.")}</p>
            </div>
          </div>
          <div class="result-panel completed-result-panel">
            <p class="summary-label">Result</p>
            <pre class="result-output compact">${escapeHtml(task.result || task.error || "No result recorded.")}</pre>
          </div>
          <div class="detail-card completed-events-card">
            <p class="summary-label">Workflow highlights</p>
            <div class="completed-event-list">
              ${renderCompletedEvents(task.events || [])}
            </div>
          </div>
        </article>
      `
    )
    .join("");
}

function renderCompletedEvents(events) {
  if (!events.length) {
    return `<p class="summary-text">No workflow events recorded.</p>`;
  }

  return [...events]
    .slice(-4)
    .reverse()
    .map(
      (event) => `
        <article class="completed-event-item">
          <div class="card-row">
            <strong>${escapeHtml(event.actor || "System")}</strong>
            <span class="status-pill" data-status="${escapeHtml(event.stage || "event")}">${escapeHtml((event.stage || "event").replaceAll("_", " "))}</span>
          </div>
          <p class="meta-text">${escapeHtml(event.timestamp || "")}</p>
          <p class="summary-text">${escapeHtml(event.message || "")}</p>
        </article>
      `
    )
    .join("");
}

async function loadCompletedPage() {
  const response = await fetch(apiUrl("/api/state"));
  if (!response.ok) {
    throw new Error("Could not load completed requests.");
  }

  const payload = await response.json();
  const archived = (payload.tasks || [])
    .filter((task) => task.status === "completed" || task.status === "failed")
    .sort((a, b) => (b.sequence || 0) - (a.sequence || 0));

  renderCompletedSummary(archived);
  renderCompletedTasks(archived);
}

loadCompletedPage().catch((error) => {
  const el = document.getElementById("completed-task-list");
  if (el) {
    el.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  }
});
