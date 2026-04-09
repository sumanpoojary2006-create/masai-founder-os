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

async function fetchState() {
  const response = await fetch(apiUrl("/api/state"));
  if (!response.ok) {
    throw new Error("Could not load live company state.");
  }
  return response.json();
}

function renderSummaryCards(summary) {
  const el = document.getElementById("summary-cards");
  if (!el || !summary) {
    return;
  }

  const cards = [
    { value: summary.open_tasks, label: "Open tasks" },
    { value: summary.backlog_tasks, label: "Queued backlog" },
    { value: summary.active_departments, label: "Active departments" },
    { value: summary.completed_tasks, label: "Completed" },
  ];

  el.innerHTML = cards
    .map(
      (card) => `
        <div class="metric-card">
          <span class="metric-value">${escapeHtml(card.value)}</span>
          <span class="metric-label">${escapeHtml(card.label)}</span>
        </div>
      `
    )
    .join("");
}

function renderDepartmentGrid(departments) {
  const el = document.getElementById("department-grid");
  if (!el) {
    return;
  }

  if (!departments?.length) {
    el.innerHTML = `<div class="empty-state">No departments available yet.</div>`;
    return;
  }

  el.innerHTML = departments
    .map((department) => {
      const fill = Math.min(
        100,
        Math.round(((department.active_count + department.queued_count) / Math.max(department.capacity, 1)) * 50)
      );

      return `
        <article class="department-card">
          <div class="card-row">
            <div>
              <h3>${escapeHtml(department.label)}</h3>
              <p class="meta-text">${escapeHtml(department.focus)}</p>
            </div>
            <span class="status-pill" data-status="${department.active_count ? "in_progress" : "queued"}">
              ${department.active_count}/${department.capacity} active
            </span>
          </div>
          <div class="capacity-bar"><span style="width: ${fill}%"></span></div>
          <div class="department-stats">
            <div>
              <p class="summary-label">Queued</p>
              <p class="department-stat">${department.queued_count}</p>
            </div>
            <div>
              <p class="summary-label">Completed</p>
              <p class="department-stat">${department.completed_count}</p>
            </div>
            <div>
              <p class="summary-label">Failed</p>
              <p class="department-stat">${department.failed_count}</p>
            </div>
            <div>
              <p class="summary-label">Avg cycle</p>
              <p class="department-stat">${department.avg_cycle_seconds || 0}s</p>
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderActivity(activity) {
  const el = document.getElementById("activity-list");
  if (!el) {
    return;
  }

  if (!activity?.length) {
    el.innerHTML = `<div class="empty-state">Live activity will appear here once tasks enter the system.</div>`;
    return;
  }

  el.innerHTML = activity
    .slice(0, 10)
    .map(
      (event) => `
        <article class="activity-card">
          <div class="card-row">
            <h4>${escapeHtml(event.task_title)}</h4>
            <span class="status-pill" data-status="${escapeHtml(event.stage)}">${escapeHtml(event.stage.replaceAll("_", " "))}</span>
          </div>
          <p class="activity-meta">${escapeHtml(event.actor)} • ${escapeHtml(event.timestamp)}</p>
          <p>${escapeHtml(event.message)}</p>
        </article>
      `
    )
    .join("");
}

function renderRecordList(elementId, records, fields) {
  const el = document.getElementById(elementId);
  if (!el) {
    return;
  }

  if (!records?.length) {
    el.innerHTML = `<div class="empty-state">No records available.</div>`;
    return;
  }

  el.innerHTML = records
    .map((record) => {
      const rows = fields
        .map(
          (field) => `
            <div class="record-row">
              <span class="record-key">${escapeHtml(field.label)}</span>
              <span class="record-value">${escapeHtml(record[field.key] ?? "-")}</span>
            </div>
          `
        )
        .join("");

      return `<article class="record-card">${rows}</article>`;
    })
    .join("");
}

function renderRecords(records) {
  if (!records) {
    return;
  }

  renderRecordList("records-leads", records.leads, [
    { key: "name", label: "Lead" },
    { key: "status", label: "Status" },
    { key: "city", label: "City" },
    { key: "score", label: "Score" },
  ]);
  renderRecordList("records-cohorts", records.cohorts, [
    { key: "code", label: "Cohort" },
    { key: "status", label: "Status" },
    { key: "city", label: "City" },
    { key: "readiness_pct", label: "Readiness" },
  ]);
  renderRecordList("records-students", records.students, [
    { key: "name", label: "Student" },
    { key: "status", label: "Status" },
    { key: "attendance_pct", label: "Attendance" },
    { key: "fees_due", label: "Fees Due" },
  ]);
  renderRecordList("records-payments", records.payments, [
    { key: "student_email", label: "Student" },
    { key: "status", label: "Status" },
    { key: "amount_due", label: "Amount Due" },
    { key: "due_date", label: "Due Date" },
  ]);
  renderRecordList("records-modules", records.modules, [
    { key: "name", label: "Module" },
    { key: "review_status", label: "Review" },
    { key: "quality_score", label: "Quality" },
    { key: "completion_pct", label: "Completion" },
  ]);
  renderRecordList("records-incidents", records.incidents, [
    { key: "title", label: "Incident" },
    { key: "severity", label: "Severity" },
    { key: "status", label: "Status" },
    { key: "impacted_users", label: "Users" },
  ]);
}

async function loadOverviewPage() {
  try {
    const state = await fetchState();
    renderSummaryCards(state.summary);
    renderDepartmentGrid(state.departments);
    renderActivity(state.activity);
    renderRecords(state.records);
  } catch (error) {
    const activity = document.getElementById("activity-list");
    if (activity) {
      activity.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    }
  }
}

loadOverviewPage();
window.setInterval(loadOverviewPage, 4000);
