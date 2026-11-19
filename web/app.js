const collectionNames = ["books", "borrowings", "librarian", "students"];
const labels = {
  books: "Books",
  borrowings: "Borrowings",
  students: "Students",
  librarian: "Librarian",
};

const state = {
  collection: "books",
  documents: [],
  editingId: null,
  counts: {},
  loadSequence: 0,
};

const elements = {
  connectionDot: document.querySelector("#connectionDot"),
  connectionTitle: document.querySelector("#connectionTitle"),
  connectionDetail: document.querySelector("#connectionDetail"),
  errorBanner: document.querySelector("#errorBanner"),
  errorMessage: document.querySelector("#errorMessage"),
  tableHead: document.querySelector("#tableHead"),
  tableBody: document.querySelector("#tableBody"),
  emptyState: document.querySelector("#emptyState"),
  searchInput: document.querySelector("#searchInput"),
  recordDialog: document.querySelector("#recordDialog"),
  jsonInput: document.querySelector("#jsonInput"),
  dialogError: document.querySelector("#dialogError"),
};

function documentId(document) {
  return document._id?.$oid ?? String(document._id ?? "");
}

function displayValue(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function showConnectionError(message) {
  elements.errorBanner.hidden = false;
  elements.errorMessage.textContent = message;
  elements.connectionDot.classList.add("offline");
  elements.connectionTitle.textContent = "Not connected";
  elements.connectionDetail.textContent = "MongoDB unavailable";
}

function setConnected() {
  elements.errorBanner.hidden = true;
  elements.connectionDot.classList.remove("offline");
  elements.connectionTitle.textContent = "Database connected";
  elements.connectionDetail.textContent = "LibraryDB · localhost";
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || `Request failed (${response.status})`);
  }
  if (response.status === 204) return null;
  return response.json();
}

async function loadCollectionCounts() {
  try {
    const result = await request("/api/collections");
    state.counts = result.counts;
    setConnected();
    renderCounts();
  } catch (error) {
    showConnectionError(error.message);
  }
}

function renderCounts() {
  let total = 0;
  for (const name of collectionNames) {
    const count = state.counts[name] ?? 0;
    total += count;
    document.querySelector(`[data-count="${name}"]`).textContent = count;
    const stat = document.querySelector(`[data-stat="${name}"]`);
    if (stat) stat.textContent = count;
  }
  document.querySelector("#totalCount").textContent = total;
  document.querySelector("#collectionCount").textContent = state.counts[state.collection] ?? 0;
}

async function loadDocuments() {
  const name = state.collection;
  const sequence = ++state.loadSequence;
  document.querySelector("#collectionTitle").firstChild.textContent = labels[name] + " ";
  document.querySelector("#breadcrumbCollection").textContent = labels[name];
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.collection === name);
  });
  elements.tableBody.replaceChildren();
  elements.tableHead.replaceChildren();
  elements.emptyState.hidden = true;
  document.querySelector("#resultsLabel").textContent = "Loading records...";

  try {
    const result = await request(`/api/collections/${name}/documents`);
    if (sequence !== state.loadSequence) return;
    state.documents = result.documents;
    setConnected();
    await loadCollectionCounts();
    if (sequence !== state.loadSequence) return;
    renderDocuments(result.hasMore);
  } catch (error) {
    if (sequence !== state.loadSequence) return;
    state.documents = [];
    showConnectionError(error.message);
    renderDocuments(false);
  }
}

function renderDocuments(hasMore = false) {
  elements.tableHead.replaceChildren();
  elements.tableBody.replaceChildren();
  const query = elements.searchInput.value.trim().toLowerCase();
  const documents = state.documents.filter((document) =>
    JSON.stringify(document).toLowerCase().includes(query),
  );
  const keys = [...new Set(documents.flatMap((document) => Object.keys(document).filter((key) => key !== "_id")))];
  const columns = keys.slice(0, 5);
  if (!columns.length && documents.length) columns.push("_id");

  if (documents.length) {
    const headerRow = document.createElement("tr");
    for (const key of columns) {
      const heading = document.createElement("th");
      heading.textContent = key
        .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
        .replace(/^./, (letter) => letter.toUpperCase());
      headerRow.append(heading);
    }
    const actionsHeading = document.createElement("th");
    actionsHeading.className = "actions-heading";
    actionsHeading.textContent = "Actions";
    headerRow.append(actionsHeading);
    elements.tableHead.append(headerRow);

    for (const record of documents) {
      const row = document.createElement("tr");
      for (const key of columns) {
        const cell = document.createElement("td");
        const value = displayValue(key === "_id" ? documentId(record) : record[key]);
        cell.textContent = value.length > 72 ? `${value.slice(0, 69)}...` : value;
        cell.title = value;
        row.append(cell);
      }
      const actions = document.createElement("td");
      actions.className = "row-actions";
      actions.innerHTML = `<button type="button" class="row-action" data-action="edit" aria-label="Edit record">Edit</button><button type="button" class="row-action danger" data-action="delete" aria-label="Delete record">Delete</button>`;
      actions.dataset.id = documentId(record);
      row.append(actions);
      elements.tableBody.append(row);
    }
  }

  const isEmpty = documents.length === 0;
  elements.emptyState.hidden = !isEmpty;
  document.querySelector("#emptyTitle").textContent = query ? "No matching records" : "No records yet";
  document.querySelector("#emptyDescription").textContent = query
    ? "Try another search term or clear your search."
    : `Add a record to get started with ${labels[state.collection].toLowerCase()}.`;
  document.querySelector("#emptyAdd").hidden = Boolean(query);
  document.querySelector("#collectionCount").textContent = state.counts[state.collection] ?? state.documents.length;
  document.querySelector("#resultsLabel").textContent = hasMore
    ? `Showing ${documents.length} matches from first 100 records · search is limited to loaded records`
    : `Showing ${documents.length} ${documents.length === 1 ? "record" : "records"}`;
}

function openEditor(record = null) {
  state.editingId = record ? documentId(record) : null;
  document.querySelector("#dialogEyebrow").textContent = state.editingId ? "EDIT RECORD" : "NEW RECORD";
  document.querySelector("#dialogTitle").textContent = `${state.editingId ? "Edit" : "Add to"} ${labels[state.collection]}`;
  document.querySelector("#saveDocument").textContent = state.editingId ? "Save changes" : "Save record";
  elements.jsonInput.value = JSON.stringify(record ? { ...record, _id: undefined } : {}, null, 2);
  elements.dialogError.hidden = true;
  elements.recordDialog.showModal();
  elements.jsonInput.focus();
}

async function saveDocument() {
  let document;
  try {
    document = JSON.parse(elements.jsonInput.value);
    if (!document || Array.isArray(document) || typeof document !== "object") {
      throw new Error("Enter a JSON object, such as {\"title\":\"Example\"}.");
    }
    delete document._id;
  } catch (error) {
    elements.dialogError.textContent = error instanceof SyntaxError
      ? "Check the JSON syntax and try again."
      : error.message;
    elements.dialogError.hidden = false;
    return;
  }

  try {
    const path = `/api/collections/${state.collection}/documents${state.editingId ? `/${encodeURIComponent(state.editingId)}` : ""}`;
    await request(path, {
      method: state.editingId ? "PUT" : "POST",
      body: JSON.stringify(document),
    });
    elements.recordDialog.close();
    await loadDocuments();
  } catch (error) {
    elements.dialogError.textContent = error.message;
    elements.dialogError.hidden = false;
  }
}

async function deleteDocument(id) {
  if (!window.confirm("Delete this record? This cannot be undone.")) return;
  try {
    await request(`/api/collections/${state.collection}/documents/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
    await loadDocuments();
  } catch (error) {
    showConnectionError(error.message);
  }
}

document.querySelectorAll(".nav-item").forEach((item) => {
  item.addEventListener("click", () => {
    state.collection = item.dataset.collection;
    elements.searchInput.value = "";
    loadDocuments();
  });
});

document.querySelector("#addDocument").addEventListener("click", () => openEditor());
document.querySelector("#emptyAdd").addEventListener("click", () => openEditor());
document.querySelector("#saveDocument").addEventListener("click", saveDocument);
document.querySelector("#retryConnection").addEventListener("click", () => {
  loadCollectionCounts();
  loadDocuments();
});
document.querySelector("#refreshRecords").addEventListener("click", loadDocuments);
elements.searchInput.addEventListener("input", () => renderDocuments());
elements.tableBody.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const id = button.closest(".row-actions").dataset.id;
  if (button.dataset.action === "delete") {
    deleteDocument(id);
  } else {
    const document = state.documents.find((entry) => documentId(entry) === id);
    if (document) openEditor(document);
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
    event.preventDefault();
    elements.searchInput.focus();
  }
});

loadCollectionCounts();
loadDocuments();
