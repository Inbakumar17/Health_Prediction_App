// Health Prediction: frontend logic.
// Talks to the FastAPI backend at /api/patients and renders the form, table and rejected log.

const API = "/api/patients";
const FIELDS = ["full_name", "dob", "email", "glucose", "haemoglobin", "cholesterol"];

const state = {
  records: [],
  editingId: null,
  rejected: [],
};

const $ = (id) => document.getElementById(id);
const form = $("patientForm");

// ---------- Helpers ----------

function escapeHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function showToast(message) {
  const toast = $("toast");
  toast.textContent = message;
  toast.classList.remove("hidden");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.add("hidden"), 3200);
}

async function request(method, url, body) {
  const options = { method, headers: {} };
  if (body) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    throw { detail: "Cannot reach the server. Is it running?", errors: {} };
  }
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw { status: response.status, detail: data.detail || `Error ${response.status}`, errors: data.errors || {} };
  return data;
}

// Normal ranges, the same as in the AI prompt. Used only to colour the numbers:
// red = above normal, green = normal, yellow = below normal.
const RANGES = {
  glucose: { low: 70, high: 140, label: "Normal 70–140 mg/dL" },
  haemoglobin: { low: 12, high: 17.5, label: "Normal 12–17.5 g/dL" },
  cholesterol: { low: -Infinity, high: 199.99, label: "Normal below 200 mg/dL" },
};

function flag(field, value) {
  const range = RANGES[field];
  if (value > range.high) return "val-high";
  if (value < range.low) return "val-low";
  return "val-normal";
}

function valueCell(field, value) {
  const level = { "val-high": "High", "val-low": "Low", "val-normal": "Normal" }[flag(field, value)];
  return `<td class="num ${flag(field, value)}" title="${level}. ${RANGES[field].label}">${formatNumber(value)}</td>`;
}

function formatNumber(value) {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)));
}

// ---------- Form errors ----------

function clearErrors() {
  FIELDS.forEach((field) => {
    $(field).classList.remove("invalid");
    document.querySelector(`[data-error-for="${field}"]`).textContent = "";
  });
  $("formAlert").classList.add("hidden");
}

function showErrors(error) {
  const errors = error.errors || {};
  Object.entries(errors).forEach(([field, message]) => {
    const input = $(field);
    if (!input) return;
    input.classList.add("invalid");
    document.querySelector(`[data-error-for="${field}"]`).textContent = message;
  });
  const alert = $("formAlert");
  alert.textContent = error.detail;
  alert.className = "alert alert-error";
  const first = FIELDS.find((f) => errors[f]);
  if (first) $(first).focus();
}

function logRejected(values, error) {
  const messages = Object.values(error.errors || {});
  state.rejected.unshift({
    name: values.full_name || "(no name)",
    time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
    messages: messages.length ? messages : [error.detail],
  });
  renderLog();
}

// ---------- Rendering ----------

function remarksCell(record) {
  if (record.ai_status === "failed") {
    return `<span class="risk risk-failed">AI unavailable</span>
            <button class="retry" data-retry="${record.id}">Retry AI</button>
            <p class="sub">${escapeHtml(record.remarks)}</p>`;
  }
  if (record.ai_status !== "done") return `<span class="sub">Waiting for AI…</span>`;
  const level = record.risk_level || "low";
  return `<span class="risk risk-${level}">${level} risk</span><p>${escapeHtml(record.remarks)}</p>`;
}

function renderTable() {
  const query = $("search").value.trim().toLowerCase();
  const rows = state.records.filter(
    (r) => !query || r.full_name.toLowerCase().includes(query) || r.email.toLowerCase().includes(query)
  );

  $("recordRows").innerHTML = rows
    .map((r) => `
      <tr data-id="${r.id}" class="${r.id === state.editingId ? "editing" : ""}">
        <td class="sub">${r.id}</td>
        <td><span class="name">${escapeHtml(r.full_name)}</span><div class="sub">Age ${r.age}</div></td>
        <td>${escapeHtml(r.dob)}</td>
        <td class="email">${escapeHtml(r.email).replace(/([@.])/g, "$1<wbr>")}</td>
        ${valueCell("glucose", r.glucose)}
        ${valueCell("haemoglobin", r.haemoglobin)}
        ${valueCell("cholesterol", r.cholesterol)}
        <td class="remarks">${remarksCell(r)}</td>
        <td><div class="actions">
          <button data-edit="${r.id}">Edit</button>
          <button class="delete" data-delete="${r.id}">Delete</button>
        </div></td>
      </tr>`)
    .join("");

  const count = state.records.length;
  $("statRecords").textContent = count;
  $("statHigh").textContent = state.records.filter((r) => r.risk_level === "high").length;
  $("emptyState").classList.toggle("hidden", rows.length > 0);
  $("emptyState").textContent = count ? "No records match your search." : "No records yet. Add the first patient with the form.";
}

function renderLog() {
  $("rejectLog").innerHTML = state.rejected
    .map((item) => `
      <li>
        <span class="who">${escapeHtml(item.name)}</span><span class="time">${item.time}</span>
        <ul>${item.messages.map((m) => `<li>${escapeHtml(m)}</li>`).join("")}</ul>
      </li>`)
    .join("");
  $("logEmpty").classList.toggle("hidden", state.rejected.length > 0);
  $("logCount").textContent = state.rejected.length ? `(${state.rejected.length})` : "";
  $("statRejected").textContent = state.rejected.length;
}

function flashRow(id) {
  const row = document.querySelector(`tr[data-id="${id}"]`);
  if (!row) return;
  row.classList.add("flash");
  row.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ---------- Create / Update ----------

function readForm() {
  return Object.fromEntries(FIELDS.map((field) => [field, $(field).value.trim()]));
}

function resetForm() {
  form.reset();
  clearErrors();
  state.editingId = null;
  $("formTitle").textContent = "Add a patient";
  $("submitBtn").textContent = "Save record";
  $("cancelEdit").classList.add("hidden");
  renderTable();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearErrors();
  const values = readForm();
  const editing = state.editingId;
  const button = $("submitBtn");
  button.disabled = true;
  button.textContent = "Saving and asking AI…";

  try {
    const saved = editing
      ? await request("PUT", `${API}/${editing}`, values)
      : await request("POST", API, values);
    await loadRecords();
    resetForm();
    flashRow(saved.id);
    showToast(
      saved.ai_status === "done"
        ? `Record #${saved.id} ${editing ? "updated" : "saved"}. AI remark added.`
        : `Record #${saved.id} saved, but the AI is busy. Use Retry AI later.`
    );
  } catch (error) {
    showErrors(error);
    logRejected(values, error);
  } finally {
    button.disabled = false;
    button.textContent = state.editingId ? "Update record" : "Save record";
  }
});

$("cancelEdit").addEventListener("click", resetForm);

// ---------- Table actions: edit, delete, retry ----------

$("recordRows").addEventListener("click", async (event) => {
  const editBtn = event.target.closest("[data-edit]");
  const deleteBtn = event.target.closest("[data-delete]");
  const retryBtn = event.target.closest("[data-retry]");

  if (editBtn) {
    const record = state.records.find((r) => r.id === Number(editBtn.dataset.edit));
    state.editingId = record.id;
    FIELDS.forEach((field) => ($(field).value = record[field]));
    clearErrors();
    $("formTitle").textContent = `Edit record #${record.id}`;
    $("submitBtn").textContent = "Update record";
    $("cancelEdit").classList.remove("hidden");
    renderTable();
    $("full_name").focus();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  if (deleteBtn) {
    // Two clicks to delete: the first asks, the second confirms.
    if (deleteBtn.dataset.armed !== "1") {
      deleteBtn.dataset.armed = "1";
      deleteBtn.classList.add("armed");
      deleteBtn.textContent = "Confirm?";
      setTimeout(() => {
        if (!deleteBtn.isConnected) return;
        deleteBtn.dataset.armed = "";
        deleteBtn.classList.remove("armed");
        deleteBtn.textContent = "Delete";
      }, 3500);
      return;
    }
    const id = Number(deleteBtn.dataset.delete);
    try {
      await request("DELETE", `${API}/${id}`);
      if (state.editingId === id) resetForm();
      await loadRecords();
      showToast(`Record #${id} deleted.`);
    } catch (error) {
      showToast(error.detail);
    }
  }

  if (retryBtn) {
    retryBtn.textContent = "Asking AI…";
    retryBtn.disabled = true;
    try {
      const updated = await request("POST", `${API}/${retryBtn.dataset.retry}/predict`);
      await loadRecords();
      flashRow(updated.id);
      showToast(updated.ai_status === "done" ? "AI remark added." : "The AI is still busy. Try again in a minute.");
    } catch (error) {
      showToast(error.detail);
    }
  }
});

$("search").addEventListener("input", renderTable);
$("clearLog").addEventListener("click", () => {
  state.rejected = [];
  renderLog();
});

// ---------- Start ----------

async function loadRecords() {
  try {
    state.records = await request("GET", API);
  } catch (error) {
    showToast(error.detail);
  }
  renderTable();
}

loadRecords();
renderLog();
