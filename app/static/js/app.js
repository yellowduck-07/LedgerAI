const now = new Date();
const defaultPeriod = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;

const state = {
  period: defaultPeriod,
  chatHistory: [],
  matches: [],
  selectedMatch: null,
  dashboard: null,
  status: {
    invoice_count: 0,
    transaction_count: 0,
    analytics_ready: false,
  },
};

const titles = {
  upload: "Get started",
  dashboard: "Dashboard",
  invoices: "Invoices",
  transactions: "Transactions",
  reconcile: "Reconcile",
  actions: "Action Center",
  chat: "AI Assistant",
};

const subtitles = {
  upload: "Upload invoices and bank data to begin.",
  dashboard: "GST, TDS, reconciliation, and compliance in one place.",
  invoices: "Sales and purchase invoices extracted from your uploads.",
  transactions: "Categorized bank activity from your CSV import.",
  reconcile: "Match sales invoices to incoming bank credits.",
  actions: "Compliance issues that need attention.",
  chat: "Ask questions about your computed books.",
};

document.getElementById("period").value = defaultPeriod;

function periodQuery() {
  return state.period ? `?period=${encodeURIComponent(state.period)}` : "";
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    try {
      const payload = await response.json();
      message = payload.detail || payload.message || message;
    } catch {
      message = await response.text();
    }
    throw new Error(message);
  }
  return response.json();
}

function money(value) {
  return `₹${Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function setStatus(ok, text) {
  const pill = document.getElementById("status-pill");
  pill.textContent = text;
  pill.className = ok ? "pill ok" : "pill error";
}

function emptyState(title, body, actionLabel, actionView) {
  return `
    <div class="empty-card">
      <h3>${title}</h3>
      <p>${body}</p>
      ${actionLabel ? `<button class="secondary empty-action" data-view="${actionView}">${actionLabel}</button>` : ""}
    </div>
  `;
}

function bindEmptyActions(container) {
  container.querySelectorAll(".empty-action").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.view));
  });
}

function switchView(view) {
  if (view !== "upload" && !state.status.analytics_ready) {
    switchView("upload");
    showUploadStatus("Upload invoices and bank CSV before opening this section.", "warn");
    return;
  }

  document.querySelectorAll(".view").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach((el) => el.classList.remove("active"));
  document.getElementById(view).classList.add("active");
  document.querySelector(`[data-view="${view}"]`).classList.add("active");
  document.getElementById("view-title").textContent = titles[view];
  document.getElementById("view-subtitle").textContent = subtitles[view];
}

function updateSetupUI() {
  const banner = document.getElementById("setup-banner");
  const ready = state.status.analytics_ready;
  banner.classList.toggle("hidden", ready);

  if (!ready) {
    document.getElementById("setup-banner-text").textContent =
      state.status.invoice_count === 0 && state.status.transaction_count === 0
        ? "Upload invoices and a bank CSV to unlock GST, TDS, and reconciliation."
        : state.status.invoice_count === 0
          ? "Invoices still needed before analytics can run."
          : "Bank CSV still needed before analytics can run.";
  }

  document.getElementById("step-invoices").classList.toggle("done", state.status.invoice_count > 0);
  document.getElementById("step-transactions").classList.toggle("done", state.status.transaction_count > 0);
  document.getElementById("step-dashboard").classList.toggle("done", ready);

  document.querySelectorAll("[data-requires-data='true']").forEach((button) => {
    button.disabled = !ready;
    button.classList.toggle("disabled", !ready);
  });
}

async function loadStatus() {
  state.status = await api("/api/status");
  updateSetupUI();
}

async function loadDashboard() {
  const data = await api(`/api/dashboard${periodQuery()}`);
  state.dashboard = data;

  const empty = document.getElementById("dashboard-empty");
  const content = document.getElementById("dashboard-content");

  if (!data.ready) {
    empty.classList.remove("hidden");
    content.classList.add("hidden");
    empty.innerHTML = emptyState(
      "Dashboard locked",
      data.message,
      "Upload files",
      "upload"
    );
    bindEmptyActions(empty);
    return;
  }

  if (data.has_period_data === false) {
    empty.classList.remove("hidden");
    content.classList.add("hidden");
    empty.innerHTML = emptyState(
      "No records for this period",
      data.message,
      "Change period or upload more data",
      "upload"
    );
    bindEmptyActions(empty);
    return;
  }

  empty.classList.add("hidden");
  content.classList.remove("hidden");

  document.getElementById("gst-cards").innerHTML = [
    ["Output GST", money(data.gst.output_tax)],
    ["Eligible ITC", money(data.gst.eligible_itc)],
    ["Net GST payable", money(data.gst.net_liability)],
    ["Sales invoices", String(data.gst.outward_invoice_count)],
    ["Purchase invoices", String(data.gst.purchase_invoice_count)],
  ]
    .map(
      ([label, value]) => `
      <div class="card accent-gst">
        <div class="label">${label}</div>
        <div class="value">${value}</div>
      </div>`
    )
    .join("");

  document.getElementById("tds-cards").innerHTML = [
    ["TDS deductible", money(data.tds.tds_deductible)],
    ["TDS deposited", money(data.tds.tds_deposited)],
    ["Pending deposit", money(data.tds.pending_deposit)],
    ["Payments to review", String(data.tds.payments_needing_review)],
  ]
    .map(
      ([label, value]) => `
      <div class="card accent-tds">
        <div class="label">${label}</div>
        <div class="value">${value}</div>
      </div>`
    )
    .join("");

  const breakdown = data.tds.by_section || {};
  const rows = Object.entries(breakdown);
  document.getElementById("tds-breakdown-rows").innerHTML = rows.length
    ? rows
        .map(
          ([section, amount]) => `
        <tr><td>${section}</td><td>${money(amount)}</td></tr>`
        )
        .join("")
    : `<tr><td colspan="2" class="muted">No TDS sections detected for this period.</td></tr>`;

  document.getElementById("match-cards").innerHTML = [
    ["Auto matched", data.match_stats.auto],
    ["Needs review", data.match_stats.review],
    ["Unmatched", data.match_stats.unmatched],
  ]
    .map(
      ([label, value]) => `
      <div class="card">
        <div class="label">${label}</div>
        <div class="value">${value}</div>
      </div>`
    )
    .join("");

  const deadlines = data.compliance_calendar.upcoming || [];
  document.getElementById("deadlines").innerHTML = deadlines.length
    ? deadlines
        .map(
          (item) => `
        <li>
          <strong>${item.title}</strong>
          <div class="muted">Due ${item.due_date} · ${item.days_until} days · ${item.category}</div>
        </li>`
        )
        .join("")
    : `<li class="muted">No statutory deadlines in the next 7 days.</li>`;

  document.getElementById("chat-context").innerHTML = `
    <div><strong>Net GST payable:</strong> ${money(data.gst.net_liability)}</div>
    <div><strong>TDS pending deposit:</strong> ${money(data.tds.pending_deposit)}</div>
    <div><strong>Compliance actions:</strong> ${data.action_summary.total}</div>
  `;

  document.getElementById("ai-summary").textContent =
    "Click Generate summary for a plain-English overview of this period.";
}

async function loadSummary() {
  if (!state.status.analytics_ready) return;
  document.getElementById("ai-summary").textContent = "Generating summary…";
  const data = await api(`/api/chat/summary${periodQuery()}`);
  document.getElementById("ai-summary").textContent = data.summary;
}

async function loadInvoices() {
  const data = await api(`/api/invoices${periodQuery()}`);
  const empty = document.getElementById("invoices-empty");
  if (!data.count) {
    empty.classList.remove("hidden");
    empty.innerHTML = emptyState(
      "No invoices yet",
      "Upload invoice PDFs, images, or JSON files to populate this table.",
      "Upload invoices",
      "upload"
    );
    bindEmptyActions(empty);
    document.getElementById("invoice-rows").innerHTML = "";
    return;
  }
  empty.classList.add("hidden");
  document.getElementById("invoice-rows").innerHTML = data.invoices
    .map((invoice) => {
      const party = invoice.is_purchase
        ? invoice.vendor_name || "Vendor"
        : invoice.customer_name || "Customer";
      return `
      <tr>
        <td>${invoice.invoice_number}</td>
        <td>${invoice.date}</td>
        <td>${party}</td>
        <td>${money(invoice.amount)}</td>
        <td>${invoice.gst_rate}%</td>
        <td>${invoice.gstin || "—"}</td>
        <td>${invoice.is_purchase ? "Purchase" : "Sales"}</td>
      </tr>`;
    })
    .join("");
}

async function loadTransactions() {
  const data = await api(`/api/transactions${periodQuery()}`);
  const empty = document.getElementById("transactions-empty");
  if (!data.count) {
    empty.classList.remove("hidden");
    empty.innerHTML = emptyState(
      "No transactions yet",
      "Import a bank CSV to categorize spending and compute TDS.",
      "Upload bank CSV",
      "upload"
    );
    bindEmptyActions(empty);
    document.getElementById("transaction-rows").innerHTML = "";
    return;
  }
  empty.classList.add("hidden");
  document.getElementById("transaction-rows").innerHTML = data.transactions
    .map(
      (txn) => `
      <tr>
        <td>${txn.date}</td>
        <td>${txn.description}</td>
        <td>${money(txn.amount)}</td>
        <td><span class="tag">${txn.direction}</span></td>
        <td>${txn.category || "Pending categorization"}</td>
      </tr>`
    )
    .join("");
}

async function loadMatches() {
  const data = await api(`/api/matches${periodQuery()}`);
  const empty = document.getElementById("reconcile-empty");
  if (!data.ready) {
    empty.classList.remove("hidden");
    empty.innerHTML = emptyState(
      "Reconciliation unavailable",
      data.message,
      "Complete upload",
      "upload"
    );
    bindEmptyActions(empty);
    document.getElementById("match-list").innerHTML = "";
    return;
  }
  empty.classList.add("hidden");
  state.matches = data.matches;
  renderMatchList();
}

function renderMatchList() {
  const container = document.getElementById("match-list");
  if (!state.matches.length) {
    container.innerHTML = `<p class="muted">No outward sales invoices found for this period.</p>`;
    return;
  }

  container.innerHTML = state.matches
    .map((match, index) => {
      const invoice = match.invoice;
      return `
      <div class="match-card" data-index="${index}">
        <div class="match-card-head">
          <strong>${invoice.invoice_number}</strong>
          <span class="tag">${match.status}</span>
        </div>
        <div>${invoice.customer_name}</div>
        <div class="muted">${money(invoice.amount)} · confidence ${Number(match.confidence || 0).toFixed(1)}%</div>
      </div>`;
    })
    .join("");

  container.querySelectorAll(".match-card").forEach((card) => {
    card.addEventListener("click", () => {
      state.selectedMatch = state.matches[Number(card.dataset.index)];
      renderMatchDetail();
    });
  });
}

function renderMatchDetail() {
  const detail = document.getElementById("match-detail");
  const match = state.selectedMatch;
  if (!match) {
    detail.innerHTML = "Select an invoice match to review the suggested bank transaction.";
    return;
  }

  const invoice = match.invoice;
  const txn = match.transaction;
  detail.innerHTML = `
    <div><strong>Invoice:</strong> ${invoice.invoice_number} · ${invoice.customer_name}</div>
    <div><strong>Taxable amount:</strong> ${money(invoice.amount)} · ${invoice.date}</div>
    <div><strong>Match confidence:</strong> ${Number(match.confidence || 0).toFixed(1)} / 100 (${match.status})</div>
    ${
      txn
        ? `<div><strong>Suggested bank credit:</strong> ${txn.description} · ${money(txn.amount)} · ${txn.date}</div>
           <button id="confirm-match">Confirm match</button>`
        : `<div class="muted">No bank transaction matched within the allowed date window.</div>`
    }
  `;

  const confirmBtn = document.getElementById("confirm-match");
  if (confirmBtn) {
    confirmBtn.addEventListener("click", async () => {
      await api("/api/matches/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          invoice_number: invoice.invoice_number,
          transaction_date: txn.date,
          transaction_description: txn.description,
        }),
      });
      detail.innerHTML += `<p class="muted">Match confirmed and saved.</p>`;
    });
  }
}

async function loadActions() {
  const data = await api(`/api/actions${periodQuery()}`);
  const empty = document.getElementById("actions-empty");
  const badge = document.getElementById("action-badge");

  if (!data.ready) {
    empty.classList.remove("hidden");
    empty.innerHTML = emptyState(
      "No compliance actions yet",
      data.message,
      "Upload files",
      "upload"
    );
    bindEmptyActions(empty);
    document.getElementById("action-list").innerHTML = "";
    badge.classList.add("hidden");
    return;
  }

  empty.classList.add("hidden");
  const total = data.action_summary.total || 0;
  badge.textContent = total;
  badge.classList.toggle("hidden", total === 0);

  document.getElementById("action-list").innerHTML = data.actions.length
    ? data.actions
        .map(
          (action) => `
        <div class="action-card ${action.severity}">
          <div class="action-card-head">
            <span class="tag">${action.source.toUpperCase()}</span>
            <span class="tag">${action.severity}</span>
          </div>
          <div>${action.message}</div>
          <div class="muted">${action.entity_label || ""}</div>
        </div>`
        )
        .join("")
    : `<div class="empty-card"><h3>All clear</h3><p>No compliance actions for this period.</p></div>`;
}

function appendChatMessage(role, content) {
  const container = document.getElementById("chat-messages");
  const div = document.createElement("div");
  div.className = `msg ${role === "user" ? "user" : "bot"}`;
  div.textContent = content;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

async function sendChat(message) {
  if (!state.status.analytics_ready) {
    showUploadStatus("Upload invoices and bank CSV before using the assistant.", "warn");
    switchView("upload");
    return;
  }
  if (!message.trim()) return;

  appendChatMessage("user", message);
  state.chatHistory.push({ role: "user", content: message });

  const data = await api("/api/chat/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      period: state.period,
      history: state.chatHistory.slice(-6),
    }),
  });

  appendChatMessage("assistant", data.reply);
  state.chatHistory.push({ role: "assistant", content: data.reply });
}

async function uploadFile(endpoint, fileInput) {
  const file = fileInput.files[0];
  if (!file) throw new Error("Choose a file first.");
  const formData = new FormData();
  formData.append("file", file);
  return api(endpoint, { method: "POST", body: formData });
}

function showUploadStatus(message, tone = "ok") {
  const box = document.getElementById("upload-status");
  box.classList.remove("hidden", "warn", "error");
  if (tone === "warn") box.classList.add("warn");
  if (tone === "error") box.classList.add("error");
  box.textContent = message;
}

function renderOcrPreview(result) {
  const preview = document.getElementById("ocr-preview");
  if (!result.invoices || !result.invoices.length) {
    preview.classList.add("hidden");
    return;
  }

  const invoice = result.invoices[0];
  const party = invoice.is_purchase
    ? invoice.vendor_name || "Vendor"
    : invoice.customer_name || "Customer";

  preview.classList.remove("hidden");
  preview.innerHTML = `
    <strong>Extraction method:</strong> ${result.extraction_method}<br>
    <strong>Invoice:</strong> ${invoice.invoice_number}<br>
    <strong>Date:</strong> ${invoice.date}<br>
    <strong>Party:</strong> ${party}<br>
    <strong>Taxable amount:</strong> ${money(invoice.amount)}<br>
    <strong>GST rate:</strong> ${invoice.gst_rate}% · ${invoice.supply_type}<br>
    <strong>GSTIN:</strong> ${invoice.gstin || "—"}
  `;
}

async function refreshAll() {
  await loadStatus();
  await Promise.all([
    loadDashboard(),
    loadInvoices(),
    loadTransactions(),
    loadMatches(),
    loadActions(),
  ]);

  const chatEmpty = document.getElementById("chat-empty");
  if (!state.status.analytics_ready) {
    chatEmpty.classList.remove("hidden");
    chatEmpty.innerHTML = emptyState(
      "Assistant locked",
      "Upload invoices and bank CSV to ask questions about GST, TDS, and compliance.",
      "Upload files",
      "upload"
    );
    bindEmptyActions(chatEmpty);
    document.getElementById("chat-messages").innerHTML = "";
  } else {
    chatEmpty.classList.add("hidden");
    if (!document.getElementById("chat-messages").children.length) {
      appendChatMessage(
        "assistant",
        "Ask me about your GST liability, TDS gap, compliance flags, or upcoming deadlines."
      );
    }
  }
}

document.querySelectorAll(".nav-btn").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

document.getElementById("setup-banner-btn").addEventListener("click", () => switchView("upload"));

document.getElementById("period").addEventListener("change", async (event) => {
  state.period = event.target.value;
  await refreshAll();
});

document.getElementById("refresh-summary").addEventListener("click", loadSummary);

document.getElementById("invoice-file").addEventListener("change", (event) => {
  const file = event.target.files[0];
  document.getElementById("invoice-file-label").textContent = file ? file.name : "Choose invoice file";
});

document.getElementById("transaction-file").addEventListener("change", (event) => {
  const file = event.target.files[0];
  document.getElementById("transaction-file-label").textContent = file ? file.name : "Choose bank CSV";
});

document.getElementById("upload-invoices").addEventListener("click", async () => {
  try {
    const result = await uploadFile("/api/invoices/upload", document.getElementById("invoice-file"));
    renderOcrPreview(result);
    showUploadStatus(`Saved ${result.saved} invoice(s) via ${result.extraction_method}.`);
    await refreshAll();
    if (state.status.analytics_ready) switchView("dashboard");
  } catch (error) {
    showUploadStatus(error.message, "error");
  }
});

document.getElementById("preview-ocr").addEventListener("click", async () => {
  try {
    const result = await uploadFile("/api/invoices/ocr", document.getElementById("invoice-file"));
    renderOcrPreview(result);
    showUploadStatus("Extraction preview ready. Save to ledger when it looks correct.");
  } catch (error) {
    showUploadStatus(error.message, "error");
    document.getElementById("ocr-preview").classList.add("hidden");
  }
});

document.getElementById("upload-transactions").addEventListener("click", async () => {
  try {
    const result = await uploadFile(
      "/api/transactions/upload",
      document.getElementById("transaction-file")
    );
    showUploadStatus(`Imported ${result.saved} bank transaction(s).`);
    await refreshAll();
    if (state.status.analytics_ready) switchView("dashboard");
  } catch (error) {
    showUploadStatus(error.message, "error");
  }
});

document.getElementById("reset-btn").addEventListener("click", async () => {
  if (!confirm("Clear all uploaded invoices and transactions?")) return;
  await api("/api/reset", { method: "POST" });
  state.chatHistory = [];
  document.getElementById("chat-messages").innerHTML = "";
  showUploadStatus("All uploaded data cleared.");
  await refreshAll();
  switchView("upload");
});

document.getElementById("chat-send").addEventListener("click", async () => {
  const input = document.getElementById("chat-input");
  const message = input.value;
  input.value = "";
  await sendChat(message);
});

document.getElementById("chat-input").addEventListener("keydown", async (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    const message = event.target.value;
    event.target.value = "";
    await sendChat(message);
  }
});

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => sendChat(chip.dataset.prompt));
});

async function init() {
  try {
    const health = await api("/api/health");
    const label = health.ocr_ready ? "OCR ready" : "Set GEMINI_API_KEY for OCR";
    setStatus(true, label);
    await refreshAll();
    switchView("upload");
  } catch (error) {
    setStatus(false, "Backend unreachable");
    console.error(error);
  }
}

init();
