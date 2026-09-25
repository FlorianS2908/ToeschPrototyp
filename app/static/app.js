"use strict";
const $ = (id) => document.getElementById(id);
const names = { housekeeping: "Housekeeping", kitchen: "Küche" };
const items = { towel: "Handtücher", pizza: "Pizza Margherita" };
let bootstrap;
let preview = null;
let hasDuplicates = false;
let sending = false;
let refreshing = false;
let pending = readStored("staydesk.pending");
let last = readStored("staydesk.last");

function readStored(key) {
  try {
    return JSON.parse(sessionStorage.getItem(key) || "null");
  } catch {
    return null;
  }
}
function store(key, value) {
  // If storage is unavailable, do not send a request whose recovery key could be lost.
  if (value === null) sessionStorage.removeItem(key);
  else sessionStorage.setItem(key, JSON.stringify(value));
}
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function notify(message, error = false) {
  $("feedback").textContent = message;
  $("feedback").classList.toggle("error", error);
  $("feedback").hidden = false;
}
async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    signal: AbortSignal.timeout(15000),
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(
      data.detail?.message || "Die Anfrage konnte nicht verarbeitet werden.",
    );
    error.status = response.status;
    error.detail = data.detail;
    throw error;
  }
  return data;
}
function post(path, body = {}, headers = {}) {
  return api(path, { method: "POST", body: JSON.stringify(body), headers });
}
function syncButtons() {
  const blocked = sending || Boolean(pending);
  for (const id of ["stay", "wish", "interpret"]) $(id).disabled = blocked;
  document.querySelectorAll("[data-example]").forEach((node) => {
    node.disabled = blocked;
  });
  $("confirm").disabled =
    blocked || !preview || (hasDuplicates && !$("additional").checked);
  $("replay").disabled = blocked || !last;
  $("retry-pending").disabled = sending;
  $("pending-banner").hidden = !pending;
}
function resetPreview() {
  preview = null;
  hasDuplicates = false;
  $("preview").hidden = true;
  $("questions").hidden = true;
  $("preview-empty").hidden = false;
  $("additional").checked = false;
  syncButtons();
}
function duplicateDetails(orders) {
  hasDuplicates = orders.length > 0;
  $("duplicate").hidden = !hasDuplicates;
  $("additional").checked = false;
  $("duplicate-text").textContent =
    orders.map((o) => `${o.quantity} × ${items[o.kind]}`).join(", ") +
    ". Möchten Sie den Status sehen oder die angezeigte Bestellung zusätzlich aufgeben?";
  syncButtons();
}
$("request-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  resetPreview();
  const stay = $("stay").value;
  const text = $("wish").value;
  $("interpret").disabled = true;
  try {
    const result = await post("/api/interpret", { stay_id: stay, text });
    if (stay !== $("stay").value || text !== $("wish").value) return;
    $("preview-empty").hidden = true;
    if (!result.ready) {
      $("questions").replaceChildren(el("strong", "Eine kurze Rückfrage:"));
      const list = el("ul");
      result.questions.forEach((q) => list.append(el("li", q)));
      $("questions").append(list);
      $("questions").hidden = false;
      return;
    }
    preview = { stay_id: stay, items: result.items };
    $("preview-items").replaceChildren();
    result.items.forEach((item) => {
      const row = el("div", undefined, "preview-item");
      const copy = el("div");
      copy.append(
        el("strong", items[item.kind]),
        el("small", item.kind === "towel" ? "Housekeeping" : "Küche"),
      );
      row.append(el("span", `${item.quantity}×`, "quantity"), copy);
      $("preview-items").append(row);
    });
    duplicateDetails(result.conflicts);
    $("preview").hidden = false;
  } catch (error) {
    notify(error.message, true);
  } finally {
    syncButtons();
  }
});
$("wish").addEventListener("input", resetPreview);
$("stay").addEventListener("change", resetPreview);
$("additional").addEventListener("change", syncButtons);
document.querySelectorAll("[data-example]").forEach((button) =>
  button.addEventListener("click", () => {
    $("wish").value = button.dataset.example;
    resetPreview();
    $("wish").focus();
  }),
);
$("show-existing").addEventListener("click", async () => {
  $("order-filter").value = $("stay").value;
  await refresh();
  $("orders-section").scrollIntoView({ behavior: "smooth" });
});

async function send(envelope) {
  if (sending) return;
  sending = true;
  try {
    store("staydesk.pending", envelope);
    pending = envelope;
    syncButtons();
    const result = await post("/api/requests", envelope.body, {
      "Idempotency-Key": envelope.key,
    });
    store("staydesk.last", envelope);
    store("staydesk.pending", null);
    last = envelope;
    pending = null;
    resetPreview();
    notify(
      result.replayed
        ? "Wiederholung erkannt: vorhandene Bestellung zurückgegeben. Kein neuer Auftrag angelegt."
        : "Bestellung gespeichert. Den tatsächlichen Übertragungsstand sehen Sie bei jedem Auftrag.",
    );
    await refresh();
  } catch (error) {
    if (error.status >= 400 && error.status < 500) {
      store("staydesk.pending", null);
      pending = null;
      if (error.detail?.code === "open_orders" && preview)
        duplicateDetails(error.detail.orders);
    }
    notify(
      error.message +
        (pending
          ? " Die Sendung bleibt für eine sichere Wiederholung erhalten."
          : ""),
      true,
    );
  } finally {
    sending = false;
    syncButtons();
  }
}
$("confirm").addEventListener("click", () => {
  if (!preview || sending || pending) return;
  send({
    key: crypto.randomUUID(),
    body: { ...preview, allow_additional: $("additional").checked },
  });
});
$("retry-pending").addEventListener("click", () => {
  if (pending) send(pending);
});
$("replay").addEventListener("click", () => {
  if (last) send(last);
});

function renderOrders(orders) {
  const container = $("orders");
  const expanded = new Set(
    [...container.querySelectorAll("details[open]")].map(
      (d) => d.dataset.order,
    ),
  );
  container.replaceChildren();
  const filter = $("order-filter").value;
  const visible = orders.filter((o) => !filter || o.stay_id === filter);
  if (!visible.length) {
    const empty = el("div", undefined, "empty-orders");
    empty.append(
      el("h3", "Noch keine Aufträge."),
      el(
        "p",
        "Bestellen Sie oben einen Service. Hier sehen Sie anschließend Status und Verlauf.",
      ),
    );
    container.append(empty);
  }
  visible.forEach((order) => {
    const card = el("article", undefined, "order");
    card.dataset.id = order.id;
    const top = el("div", undefined, "order-top");
    top.append(
      el("span", names[order.service], "department"),
      el("span", order.status_label, `status ${order.status}`),
    );
    const room =
      bootstrap.stays.find((s) => s.id === order.stay_id)?.room ||
      order.stay_id;
    card.append(
      top,
      el("h3", `${order.quantity} × ${order.label}`),
      el(
        "p",
        `Zimmer ${room} · Referenz ${order.id.slice(0, 8)}`,
        "order-meta",
      ),
    );
    if (order.last_error) card.append(el("p", order.last_error, "order-error"));
    const actions = el("div", undefined, "order-actions");
    if (order.status !== "completed") {
      const reconcile = el(
        "button",
        "Abgleichen / erneut übermitteln",
        "secondary",
      );
      reconcile.addEventListener("click", () =>
        orderAction(reconcile, `/api/orders/${order.id}/reconcile`),
      );
      actions.append(reconcile);
    }
    if (["transmitted", "in_progress"].includes(order.status)) {
      const advance = el(
        "button",
        order.status === "transmitted"
          ? "Simulator: Bearbeitung starten"
          : "Simulator: Erledigen",
        "secondary",
      );
      advance.addEventListener("click", () =>
        orderAction(advance, `/api/simulator/orders/${order.id}/advance`, {
          status: order.status === "transmitted" ? "in_progress" : "completed",
        }),
      );
      actions.append(advance);
    }
    card.append(actions);
    const details = el("details");
    details.dataset.order = order.id;
    details.open = expanded.has(order.id);
    details.append(
      el("summary", `Verlauf · ${order.events.length} Ereignisse`),
    );
    const timeline = el("ol", undefined, "timeline");
    order.events.forEach((event) => {
      const entry = el("li");
      const time = el(
        "time",
        new Date(event.created_at).toLocaleString("de-DE"),
      );
      time.dateTime = event.created_at;
      entry.append(time, el("span", event.message));
      timeline.append(entry);
    });
    details.append(
      timeline,
      el("p", `Vollständige Referenz: ${order.id}`, "field-hint"),
    );
    card.append(details);
    container.append(card);
  });
}
async function orderAction(button, path, body = {}) {
  button.disabled = true;
  try {
    await post(path, body);
    await refresh();
  } catch (error) {
    notify(error.message, true);
    button.disabled = false;
  }
}
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  $("refresh").disabled = true;
  try {
    const [orders, receipts, config] = await Promise.all([
      api("/api/orders"),
      api("/api/simulator/receipts"),
      api("/api/bootstrap"),
    ]);
    bootstrap = config;
    $("stat-total").textContent = orders.orders.length;
    $("stat-open").textContent = orders.orders.filter(
      (o) => o.status !== "completed",
    ).length;
    $("stat-attention").textContent = orders.orders.filter(
      (o) => ["saved", "uncertain"].includes(o.status) || o.last_error,
    ).length;
    $("stat-received").textContent = receipts.receipts.length;
    renderOrders(orders.orders);
    Object.entries(config.modes).forEach(([service, mode]) => {
      $("mode-" + service).value = mode;
    });
    $("updated").textContent =
      "Stand: " + new Date().toLocaleTimeString("de-DE");
  } catch (error) {
    notify("Aktualisierung fehlgeschlagen: " + error.message, true);
  } finally {
    refreshing = false;
    $("refresh").disabled = false;
  }
}
$("refresh").addEventListener("click", refresh);
$("order-filter").addEventListener("change", refresh);
document.querySelectorAll("[data-service]").forEach((select) =>
  select.addEventListener("change", async () => {
    select.disabled = true;
    try {
      await post(`/api/simulator/${select.dataset.service}/mode`, {
        mode: select.value,
      });
      await refresh();
      notify(
        `Simulationsmodus für ${names[select.dataset.service]} aktualisiert.`,
      );
    } catch (error) {
      notify(error.message, true);
    } finally {
      select.disabled = false;
    }
  }),
);
async function init() {
  syncButtons();
  try {
    bootstrap = await api("/api/bootstrap");
    for (const stay of bootstrap.stays) {
      for (const id of ["stay", "order-filter"]) {
        const option = el("option", stay.label);
        option.value = stay.id;
        $(id).append(option);
      }
    }
    if (pending) $("stay").value = pending.body.stay_id;
    await refresh();
  } catch (error) {
    notify("Verbindung zur Anwendung fehlgeschlagen: " + error.message, true);
  }
}
init();
