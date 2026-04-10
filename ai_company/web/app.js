const state = {
  tasks: [],
  selectedTaskId: null,
  pollHandle: null,
};

const STAGES = [
  { id: "triage", label: "CEO Triage" },
  { id: "queued", label: "Queued" },
  { id: "in_progress", label: "In Progress" },
  { id: "ceo_review", label: "CEO Review" },
  { id: "completed", label: "Completed" },
];

const els = {
  liveStatus: document.getElementById("live-status"),
  statusMessage: document.getElementById("status-message"),
  submitButton: document.getElementById("submit-button"),
  taskForm: document.getElementById("task-form"),
  taskTitle: document.getElementById("task-title"),
  taskRequest: document.getElementById("task-request"),
  taskPriority: document.getElementById("task-priority"),
  taskDepartment: document.getElementById("task-department"),
  openTaskList: document.getElementById("open-task-list"),
  assignmentContextTitle: document.getElementById("assignment-context-title"),
  assignmentContextCopy: document.getElementById("assignment-context-copy"),
  assignmentTeamName: document.getElementById("assignment-team-name"),
  assignmentTeamCopy: document.getElementById("assignment-team-copy"),
  assignmentNextTitle: document.getElementById("assignment-next-title"),
  assignmentNextCopy: document.getElementById("assignment-next-copy"),
  progressSteps: document.getElementById("progress-steps"),
  detailTitle: document.getElementById("detail-title"),
  detailDepartment: document.getElementById("detail-department"),
  detailReason: document.getElementById("detail-reason"),
  detailEffect: document.getElementById("detail-effect"),
  detailResult: document.getElementById("detail-result"),
  detailActions: document.getElementById("detail-actions"),
  eventList: document.getElementById("event-list"),
};

function getApiBase() {
  return window.MASAI_API_BASE_URL || localStorage.getItem("masai_api_base_url") || "";
}

function apiUrl(path) {
  const base = getApiBase().trim().replace(/\/+$/, "");
  return base ? `${base}${path}` : path;
}

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function setStatus(message) {
  if (els.statusMessage) {
    els.statusMessage.textContent = message;
  }
}

function getOpenTasks() {
  return state.tasks.filter((task) => task.status !== "completed" && task.status !== "failed");
}

function getSelectedTask() {
  const openTasks = getOpenTasks();
  return openTasks.find((task) => task.id === state.selectedTaskId) || openTasks[0] || null;
}

function selectTask(taskId) {
  state.selectedTaskId = taskId;
  renderOpenTasks();
  renderAssignment();
  renderTaskDetail();
}

function renderOpenTasks() {
  if (!els.openTaskList) {
    return;
  }

  const openTasks = getOpenTasks();
  if (!openTasks.length) {
    els.openTaskList.innerHTML = `<div class="empty-state">No open requests right now. Submit a new one to start the flow.</div>`;
    return;
  }

  els.openTaskList.innerHTML = openTasks
    .map(
      (task) => `
        <button class="open-task-chip ${task.id === state.selectedTaskId ? "active" : ""}" data-task-id="${task.id}">
          <span class="open-task-chip-title">${escapeHtml(task.title)}</span>
          <span class="open-task-chip-meta">${escapeHtml(task.department_label || "CEO Triage")} • ${escapeHtml(task.status.replaceAll("_", " "))}</span>
        </button>
      `
    )
    .join("");

  els.openTaskList.querySelectorAll(".open-task-chip").forEach((chip) => {
    chip.addEventListener("click", () => selectTask(chip.dataset.taskId));
  });
}

function renderAssignment() {
  const task = getSelectedTask();

  if (!task) {
    els.assignmentContextTitle.textContent = "Waiting for a request";
    els.assignmentContextCopy.textContent = "The CEO will read the founder request and decide which team should own it.";
    els.assignmentTeamName.textContent = "No team assigned yet";
    els.assignmentTeamCopy.textContent = "Submit a task to see the right team pick it up.";
    els.assignmentNextTitle.textContent = "No action yet";
    els.assignmentNextCopy.textContent = "Once a team starts working, this card will explain what the system is doing.";
    els.progressSteps.innerHTML = STAGES.map((stage) => `<div class="stage-step">${escapeHtml(stage.label)}</div>`).join("");
    return;
  }

  els.assignmentContextTitle.textContent = task.title;
  els.assignmentContextCopy.textContent = task.ceo_reason || "The CEO is still deciding the best department for this request.";
  els.assignmentTeamName.textContent = task.department_label || "CEO Triage";
  els.assignmentTeamCopy.textContent =
    task.assignee || (task.status === "triage" ? "The CEO is reviewing the request." : "Waiting for the next available worker.");

  const nextCopyByStatus = {
    triage: "The CEO is deciding the right department and priority.",
    queued: "The task is waiting in the department queue for the next available worker.",
    in_progress: "A department worker is actively executing the request.",
    ceo_review: "The work is done and the CEO is doing the final quality check.",
  };

  els.assignmentNextTitle.textContent = task.status.replaceAll("_", " ");
  els.assignmentNextCopy.textContent = task.data_effect || nextCopyByStatus[task.status] || "The next action will appear here.";

  const stageIndex = STAGES.findIndex((stage) => stage.id === task.status);
  els.progressSteps.innerHTML = STAGES.map((stage, index) => {
    const stateClass = index < stageIndex ? "done" : index === stageIndex ? "active" : "";
    return `<div class="stage-step ${stateClass}">${escapeHtml(stage.label)}</div>`;
  }).join("");
}

function renderTaskDetail() {
  const task = getSelectedTask();

  if (!task) {
    els.detailTitle.textContent = "Choose an open task";
    els.detailDepartment.textContent = "No task selected";
    els.detailReason.textContent = "The CEO routing note will appear here.";
    els.detailEffect.textContent = "Any actual record changes will appear here.";
    els.detailResult.textContent = "No result yet.";
    els.detailActions.innerHTML = "";
    els.eventList.innerHTML = `<div class="empty-state">Live workflow events will appear here once a task starts moving.</div>`;
    return;
  }

  state.selectedTaskId = task.id;
  els.detailTitle.textContent = task.title;
  els.detailDepartment.textContent = task.department_label || "CEO Triage";
  els.detailReason.textContent = task.ceo_reason || "The CEO is still writing the routing note.";
  els.detailEffect.textContent = task.data_effect || "No direct database effect has been recorded yet.";
  els.detailResult.textContent = task.result || task.error || "The team is still working on this request.";

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

  els.eventList.innerHTML = task.events?.length
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

function applyState(payload) {
  state.tasks = payload.tasks || [];
  const openTasks = getOpenTasks();
  if (!openTasks.find((task) => task.id === state.selectedTaskId)) {
    state.selectedTaskId = openTasks[0]?.id || null;
  }
  renderOpenTasks();
  renderAssignment();
  renderTaskDetail();
}

async function fetchState() {
  const response = await fetch(apiUrl("/api/state"));
  if (!response.ok) {
    throw new Error("Failed to fetch");
  }
  const payload = await response.json();
  applyState(payload);
}

async function createTask(event) {
  event.preventDefault();
  const request = els.taskRequest.value.trim();
  if (!request) {
    setStatus("Please enter a founder request before submitting.");
    return;
  }

  els.submitButton.disabled = true;
  setStatus("Sending request to the CEO...");

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
    setStatus("Request submitted. The CEO is routing it now.");
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
    if (els.liveStatus) {
      els.liveStatus.textContent = "Live polling every 2s";
    }
  } catch (error) {
    if (els.liveStatus) {
      els.liveStatus.textContent = "Polling interrupted";
    }
    setStatus(error.message);
  }
}

if (els.taskForm) {
  els.taskForm.addEventListener("submit", createTask);
}

pollState();
state.pollHandle = window.setInterval(pollState, 2000);
