const state = {
  company: null,
  summary: null,
  departments: [],
  tasks: [],
  activity: [],
  selectedTaskId: null,
  pollHandle: null,
};

function getApiBase() {
  return window.MASAI_API_BASE_URL || localStorage.getItem("masai_api_base_url") || "";
}

function apiUrl(path) {
  const base = getApiBase().trim().replace(/\/+$/, "");
  return base ? `${base}${path}` : path;
}

const STATUS_COLUMNS = [
  { id: "triage", label: "CEO Triage" },
  { id: "queued", label: "Queued" },
  { id: "in_progress", label: "In Progress" },
  { id: "ceo_review", label: "CEO Review" },
  { id: "completed", label: "Completed / Failed" },
];

const els = {
  summaryCards: document.getElementById("summary-cards"),
  departmentGrid: document.getElementById("department-grid"),
  taskColumns: document.getElementById("task-columns"),
  activityList: document.getElementById("activity-list"),
  eventList: document.getElementById("event-list"),
  detailTitle: document.getElementById("detail-title"),
  detailDepartment: document.getElementById("detail-department"),
  detailReason: document.getElementById("detail-reason"),
  detailEffect: document.getElementById("detail-effect"),
  detailResult: document.getElementById("detail-result"),
  detailActions: document.getElementById("detail-actions"),
  statusMessage: document.getElementById("status-message"),
  submitButton: document.getElementById("submit-button"),
  liveStatus: document.getElementById("live-status"),
  taskForm: document.getElementById("task-form"),
  taskTitle: document.getElementById("task-title"),
  taskRequest: document.getElementById("task-request"),
  taskPriority: document.getElementById("task-priority"),
  taskDepartment: document.getElementById("task-department"),
};

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function setStatus(message) {
  els.statusMessage.textContent = message;
}

function selectTask(taskId) {
  state.selectedTaskId = taskId;
  renderTaskBoard();
  renderTaskDetail();
}

function renderSummary() {
  if (!state.summary || !els.summaryCards) {
    return;
  }

  const cards = [
    { value: state.summary.open_tasks, label: "Open tasks" },
    { value: state.summary.backlog_tasks, label: "Queued backlog" },
    { value: state.summary.active_departments, label: "Active departments" },
    { value: `${state.summary.avg_cycle_seconds || 0}s`, label: "Avg completion" },
  ];

  els.summaryCards.innerHTML = cards
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

function renderDepartments() {
  if (!state.departments.length) {
    els.departmentGrid.innerHTML = `<div class="empty-state">Departments will appear here once the company state loads.</div>`;
    return;
  }

  els.departmentGrid.innerHTML = state.departments
    .map((department) => {
      const loadPercent = Math.min(
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
          <div class="capacity-bar"><span style="width: ${loadPercent}%"></span></div>
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

function renderTaskBoard() {
  const tasksByStatus = Object.fromEntries(STATUS_COLUMNS.map((column) => [column.id, []]));
  state.tasks.forEach((task) => {
    const key = task.status === "failed" ? "completed" : task.status;
    if (tasksByStatus[key]) {
      tasksByStatus[key].push(task);
    }
  });

  els.taskColumns.innerHTML = STATUS_COLUMNS.map((column) => {
    const tasks = tasksByStatus[column.id] || [];
    const cards = tasks.length
      ? tasks
          .map(
            (task) => `
              <article class="task-card ${state.selectedTaskId === task.id ? "active" : ""}" data-task-id="${task.id}">
                <div class="card-row">
                  <span class="priority-pill" data-priority="${task.priority}">${task.priority}</span>
                  <span class="status-pill" data-status="${task.status}">${task.status.replaceAll("_", " ")}</span>
                </div>
                <h4>${escapeHtml(task.title)}</h4>
                <p>${escapeHtml(task.department_label || "CEO Triage")}</p>
                <p>${escapeHtml(task.assignee || "Unassigned")}</p>
                ${task.queue_position ? `<p>Queue position: ${task.queue_position}</p>` : ""}
              </article>
            `
          )
          .join("")
      : `<div class="empty-state">No tasks in this stage.</div>`;

    return `
      <section class="task-column">
        <h3>${escapeHtml(column.label)}</h3>
        <span class="task-column-count">${tasks.length} task(s)</span>
        <div class="task-list">${cards}</div>
      </section>
    `;
  }).join("");

  document.querySelectorAll(".task-card").forEach((card) => {
    card.addEventListener("click", () => selectTask(card.dataset.taskId));
  });
}

function renderTaskDetail() {
  const task = state.tasks.find((item) => item.id === state.selectedTaskId) || state.tasks[0];
  if (!task) {
    els.detailTitle.textContent = "Choose a task to inspect its workflow";
    els.detailDepartment.textContent = "No task selected";
    els.detailReason.textContent = "No live task selected yet.";
    if (els.detailEffect) {
      els.detailEffect.textContent = "No database change yet.";
    }
    els.detailResult.textContent = "No result yet.";
    els.detailActions.innerHTML = "";
    els.eventList.innerHTML = `<div class="empty-state">Task events will appear here once work starts.</div>`;
    return;
  }

  state.selectedTaskId = task.id;
  els.detailTitle.textContent = task.title;
  els.detailDepartment.textContent = task.department_label || "CEO Triage";
  els.detailReason.textContent = task.ceo_reason || "CEO is still triaging this request.";
  if (els.detailEffect) {
    els.detailEffect.textContent = task.data_effect || "No database change has been applied yet.";
  }
  els.detailResult.textContent = task.result || task.error || "This task is still in progress.";

  const priorityButtons = ["critical", "high", "normal", "low"]
    .map(
      (priority) => `
        <button
          class="secondary"
          data-action="priority"
          data-priority="${priority}"
          ${task.status !== "queued" ? "disabled" : ""}
        >
          Set ${priority}
        </button>
      `
    )
    .join("");

  const retryButton =
    task.status === "failed"
      ? `<button class="secondary" data-action="retry">Retry failed task</button>`
      : "";

  els.detailActions.innerHTML = priorityButtons + retryButton;
  els.detailActions.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", async () => {
      if (button.dataset.action === "priority") {
        await updatePriority(task.id, button.dataset.priority);
      }
      if (button.dataset.action === "retry") {
        await retryTask(task.id);
      }
    });
  });

  els.eventList.innerHTML = task.events.length
    ? [...task.events]
        .reverse()
        .map(
          (event) => `
            <article class="event-card">
              <div class="card-row">
                <h4>${escapeHtml(event.actor)}</h4>
                <span class="status-pill" data-status="${escapeHtml(event.stage)}">${escapeHtml(event.stage.replaceAll("_", " "))}</span>
              </div>
              <p class="detail-meta">${escapeHtml(event.timestamp)}</p>
              <p>${escapeHtml(event.message)}</p>
            </article>
          `
        )
        .join("")
    : `<div class="empty-state">This task has no events yet.</div>`;
}

function renderActivity() {
  if (!state.activity.length) {
    els.activityList.innerHTML = `<div class="empty-state">Live activity will appear here once tasks enter the company.</div>`;
    return;
  }

  els.activityList.innerHTML = state.activity
    .slice(0, 12)
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

function applyState(payload) {
  state.company = payload.company;
  state.summary = payload.summary;
  state.departments = payload.departments || [];
  state.tasks = payload.tasks || [];
  state.activity = payload.activity || [];

  renderSummary();
  renderDepartments();
  renderTaskBoard();
  renderTaskDetail();
  renderActivity();
}

async function fetchState() {
  const response = await fetch(apiUrl("/api/state"));
  if (!response.ok) {
    throw new Error("Could not fetch company state.");
  }
  const payload = await response.json();
  applyState(payload);
}

async function createTask(event) {
  event.preventDefault();
  const request = els.taskRequest.value.trim();
  if (!request) {
    setStatus("Please enter a founder request before creating a task.");
    return;
  }

  els.submitButton.disabled = true;
  setStatus("Submitting task to the CEO inbox...");

  try {
    const response = await fetch(apiUrl("/api/tasks"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: els.taskTitle.value.trim(),
        request,
        priority: els.taskPriority.value,
        department_hint: els.taskDepartment.value,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Failed to create task.");
    }

    applyState(payload.state);
    selectTask(payload.task.id);
    els.taskForm.reset();
    els.taskPriority.value = "normal";
    setStatus("Task created. The CEO is triaging it now.");
  } catch (error) {
    setStatus(error.message);
  } finally {
    els.submitButton.disabled = false;
  }
}

async function updatePriority(taskId, priority) {
  setStatus(`Changing priority to ${priority}...`);
  const response = await fetch(apiUrl(`/api/tasks/${taskId}/priority`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ priority }),
  });
  const payload = await response.json();
  if (!response.ok) {
    setStatus(payload.error || "Could not update priority.");
    return;
  }

  applyState(payload.state);
  selectTask(taskId);
  setStatus(`Priority updated to ${priority}.`);
}

async function retryTask(taskId) {
  setStatus("Retrying failed task...");
  const response = await fetch(apiUrl(`/api/tasks/${taskId}/retry`), { method: "POST" });
  const payload = await response.json();
  if (!response.ok) {
    setStatus(payload.error || "Could not retry task.");
    return;
  }

  applyState(payload.state);
  selectTask(taskId);
  setStatus("Task sent back to the CEO for retry.");
}

async function pollState() {
  try {
    await fetchState();
    els.liveStatus.textContent = "Live polling every 2s";
  } catch (error) {
    els.liveStatus.textContent = "Polling interrupted";
    setStatus(error.message);
  }
}

els.taskForm.addEventListener("submit", createTask);

pollState();
state.pollHandle = window.setInterval(pollState, 2000);
