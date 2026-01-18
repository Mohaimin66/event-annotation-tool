/**
 * Event Annotation Tool - Frontend Logic
 */

// State
let config = {};
let eventTypes = [];
let eventTypesMap = {};
let items = [];
let currentIndex = 0;
let currentAnnotatorId = 0;
let selectedTriggerIndices = [];
let selectedEventType = null;
let notInList = false;

// DOM Elements
const annotatorSelect = document.getElementById("annotator");
const sentenceDisplay = document.getElementById("sentence-display");
const predictionCards = document.getElementById("prediction-cards");
const definitionSection = document.getElementById("definition-section");
const definitionContent = document.getElementById("definition-content");
const searchInput = document.getElementById("search-input");
const searchResults = document.getElementById("search-results");
const notInListCheckbox = document.getElementById("not-in-list");
const prevBtn = document.getElementById("prev-btn");
const nextBtn = document.getElementById("next-btn");
const gotoPage = document.getElementById("goto-page");
const gotoBtn = document.getElementById("goto-btn");

// Progress elements
const progressCompleted = document.getElementById("progress-completed");
const progressTotal = document.getElementById("progress-total");
const progressPercent = document.getElementById("progress-percent");
const progressFill = document.getElementById("progress-fill");

// Index/page elements
const currentIndexEl = document.getElementById("current-index");
const totalItemsEl = document.getElementById("total-items");
const currentPageEl = document.getElementById("current-page");
const totalPagesEl = document.getElementById("total-pages");
const selectedTriggerText = document.getElementById("selected-trigger-text");

// Modal elements
const searchModal = document.getElementById("search-modal");
const closeModal = document.getElementById("close-modal");
const modalSearchInput = document.getElementById("modal-search-input");
const modalResults = document.getElementById("modal-results");

// Initialize
async function init() {
  try {
    // Load config
    const configRes = await fetch("/api/config");
    config = await configRes.json();

    // Load event types
    const eventTypesRes = await fetch("/api/event-types");
    eventTypes = await eventTypesRes.json();
    eventTypesMap = {};
    eventTypes.forEach((et) => (eventTypesMap[et.id] = et));

    // Populate annotator dropdown
    populateAnnotatorDropdown();

    // Load data for first annotator
    await loadAnnotatorData(0);

    // Setup event listeners
    setupEventListeners();
  } catch (error) {
    console.error("Initialization error:", error);
    alert("Failed to load application. Please refresh the page.");
  }
}

function populateAnnotatorDropdown() {
  annotatorSelect.innerHTML = "";
  config.annotator_names.forEach((name, idx) => {
    const option = document.createElement("option");
    option.value = idx;
    option.textContent = name;
    annotatorSelect.appendChild(option);
  });
}

async function loadAnnotatorData(annotatorId) {
  currentAnnotatorId = annotatorId;
  try {
    const res = await fetch(`/api/data/${annotatorId}`);
    const data = await res.json();
    items = data.items;
    currentIndex = 0;

    // Find first unannotated item
    for (let i = 0; i < items.length; i++) {
      if (!items[i].annotation) {
        currentIndex = i;
        break;
      }
    }

    renderCurrentItem();
    updateProgress();
  } catch (error) {
    console.error("Error loading annotator data:", error);
  }
}

function renderCurrentItem() {
  if (items.length === 0) {
    sentenceDisplay.innerHTML = "<p>No items to annotate.</p>";
    return;
  }

  const item = items[currentIndex];

  // Reset state
  if (item.annotation) {
    selectedTriggerIndices = [...item.annotation.trigger_indices];
    selectedEventType = item.annotation.event_type;
    notInList = item.annotation.not_in_list || false;
  } else {
    selectedTriggerIndices = [...item.model_prediction.trigger_indices];
    selectedEventType = null;
    notInList = false;
  }

  // Render tokens
  renderTokens(item);

  // Render prediction cards
  renderPredictionCards(item);

  // Update checkbox
  notInListCheckbox.checked = notInList;

  // Update indices
  currentIndexEl.textContent = currentIndex + 1;
  totalItemsEl.textContent = items.length;
  currentPageEl.textContent = currentIndex + 1;
  totalPagesEl.textContent = items.length;

  // Update navigation buttons
  prevBtn.disabled = currentIndex === 0;
  nextBtn.disabled = currentIndex === items.length - 1;

  // Update selected trigger text
  updateSelectedTriggerText(item);

  // Show definition if event type selected
  if (selectedEventType && eventTypesMap[selectedEventType]) {
    showDefinition(eventTypesMap[selectedEventType]);
  } else {
    hideDefinition();
  }

  // Clear search
  searchInput.value = "";
  searchResults.style.display = "none";
}

function renderTokens(item) {
  sentenceDisplay.innerHTML = "";
  item.tokens.forEach((token, idx) => {
    const tokenEl = document.createElement("span");
    tokenEl.className = "token";
    tokenEl.textContent = token;
    tokenEl.dataset.index = idx;

    // Mark model-predicted triggers
    if (item.model_prediction.trigger_indices.includes(idx)) {
      tokenEl.classList.add("model-predicted");
    }

    // Mark selected triggers
    if (selectedTriggerIndices.includes(idx)) {
      tokenEl.classList.add("selected");
    }

    tokenEl.addEventListener("click", (e) => handleTokenClick(idx, e.shiftKey));
    sentenceDisplay.appendChild(tokenEl);
  });
}

function handleTokenClick(idx, shiftKey) {
  if (shiftKey && selectedTriggerIndices.length > 0) {
    // Range selection
    const lastSelected =
      selectedTriggerIndices[selectedTriggerIndices.length - 1];
    const start = Math.min(lastSelected, idx);
    const end = Math.max(lastSelected, idx);
    for (let i = start; i <= end; i++) {
      if (!selectedTriggerIndices.includes(i)) {
        selectedTriggerIndices.push(i);
      }
    }
  } else {
    // Toggle selection
    const existingIdx = selectedTriggerIndices.indexOf(idx);
    if (existingIdx >= 0) {
      selectedTriggerIndices.splice(existingIdx, 1);
    } else {
      selectedTriggerIndices.push(idx);
    }
  }

  selectedTriggerIndices.sort((a, b) => a - b);
  renderTokens(items[currentIndex]);
  updateSelectedTriggerText(items[currentIndex]);
}

function updateSelectedTriggerText(item) {
  if (selectedTriggerIndices.length === 0) {
    selectedTriggerText.textContent = "Selected: none";
  } else {
    const words = selectedTriggerIndices.map((i) => item.tokens[i]).join(" ");
    selectedTriggerText.textContent = `Selected: "${words}"`;
  }
}

function renderPredictionCards(item) {
  predictionCards.innerHTML = "";
  item.model_prediction.top_event_types.forEach((typeId, idx) => {
    const eventType = eventTypesMap[typeId];
    if (!eventType) return;

    const card = document.createElement("div");
    card.className = "prediction-card";
    if (selectedEventType === typeId) {
      card.classList.add("selected");
    }
    card.innerHTML = `<span class="rank">${idx + 1}.</span>${eventType.name}`;
    card.dataset.typeId = typeId;

    card.addEventListener("click", () => selectEventType(typeId));
    predictionCards.appendChild(card);
  });
}

function selectEventType(typeId) {
  if (notInList) {
    notInList = false;
    notInListCheckbox.checked = false;
  }

  selectedEventType = typeId;

  // Update card styles
  document.querySelectorAll(".prediction-card").forEach((card) => {
    card.classList.toggle("selected", card.dataset.typeId === typeId);
  });

  // Show definition
  const eventType = eventTypesMap[typeId];
  if (eventType) {
    showDefinition(eventType);
  }
}

function showDefinition(eventType) {
  definitionContent.innerHTML = `<strong>${eventType.name}:</strong> ${eventType.description}`;
  definitionSection.style.display = "block";
}

function hideDefinition() {
  definitionSection.style.display = "none";
}

function toggleDefinition() {
  if (definitionSection.style.display === "none" && selectedEventType) {
    showDefinition(eventTypesMap[selectedEventType]);
  } else {
    hideDefinition();
  }
}

// Search functionality
function handleSearch(query) {
  if (!query.trim()) {
    searchResults.style.display = "none";
    return;
  }

  const lowerQuery = query.toLowerCase();
  const matches = eventTypes
    .filter(
      (et) =>
        et.name.toLowerCase().includes(lowerQuery) ||
        et.description.toLowerCase().includes(lowerQuery),
    )
    .slice(0, 10);

  if (matches.length === 0) {
    searchResults.style.display = "none";
    return;
  }

  searchResults.innerHTML = "";
  matches.forEach((et) => {
    const item = document.createElement("div");
    item.className = "search-result-item";
    item.innerHTML = `
            <div class="name">${et.name}</div>
            <div class="description">${et.description}</div>
        `;
    item.addEventListener("click", () => {
      selectEventType(et.id);
      searchInput.value = "";
      searchResults.style.display = "none";
    });
    searchResults.appendChild(item);
  });
  searchResults.style.display = "block";
}

// Modal search
function openSearchModal() {
  searchModal.style.display = "flex";
  modalSearchInput.value = "";
  modalSearchInput.focus();
  renderModalResults("");
}

function closeSearchModal() {
  searchModal.style.display = "none";
}

function renderModalResults(query) {
  const lowerQuery = query.toLowerCase();
  const matches = query.trim()
    ? eventTypes.filter(
        (et) =>
          et.name.toLowerCase().includes(lowerQuery) ||
          et.description.toLowerCase().includes(lowerQuery),
      )
    : eventTypes;

  modalResults.innerHTML = "";
  matches.forEach((et) => {
    const item = document.createElement("div");
    item.className = "modal-result-item";
    item.innerHTML = `
            <div class="name">${et.name}</div>
            <div class="description">${et.description}</div>
        `;
    item.addEventListener("click", () => {
      selectEventType(et.id);
      closeSearchModal();
    });
    modalResults.appendChild(item);
  });
}

// Save annotation
async function saveCurrentAnnotation() {
  if (items.length === 0) return;

  const item = items[currentIndex];
  const annotation = {
    trigger_indices: selectedTriggerIndices,
    event_type: notInList ? null : selectedEventType,
    not_in_list: notInList,
  };

  try {
    const res = await fetch("/api/annotate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        annotator_id: currentAnnotatorId,
        item: item,
        annotation: annotation,
      }),
    });

    if (res.ok) {
      // Update local state
      item.annotation = annotation;
      updateProgress();
    } else {
      console.error("Failed to save annotation");
    }
  } catch (error) {
    console.error("Error saving annotation:", error);
  }
}

async function updateProgress() {
  try {
    const res = await fetch(`/api/progress/${currentAnnotatorId}`);
    const progress = await res.json();

    progressCompleted.textContent = progress.completed;
    progressTotal.textContent = progress.total;
    progressPercent.textContent = progress.percentage;
    progressFill.style.width = `${progress.percentage}%`;
  } catch (error) {
    console.error("Error updating progress:", error);
  }
}

// Navigation
async function goToItem(index) {
  if (index < 0 || index >= items.length) return;

  // Save current annotation before navigating
  await saveCurrentAnnotation();

  currentIndex = index;
  renderCurrentItem();
}

function goToPrev() {
  goToItem(currentIndex - 1);
}

function goToNext() {
  goToItem(currentIndex + 1);
}

function goToPage() {
  const page = parseInt(gotoPage.value);
  if (page >= 1 && page <= items.length) {
    goToItem(page - 1);
  }
  gotoPage.value = "";
}

// Event listeners
function setupEventListeners() {
  // Annotator change
  annotatorSelect.addEventListener("change", (e) => {
    loadAnnotatorData(parseInt(e.target.value));
  });

  // Navigation
  prevBtn.addEventListener("click", goToPrev);
  nextBtn.addEventListener("click", goToNext);
  gotoBtn.addEventListener("click", goToPage);
  gotoPage.addEventListener("keypress", (e) => {
    if (e.key === "Enter") goToPage();
  });

  // Not in list checkbox
  notInListCheckbox.addEventListener("change", (e) => {
    notInList = e.target.checked;
    if (notInList) {
      selectedEventType = null;
      document.querySelectorAll(".prediction-card").forEach((card) => {
        card.classList.remove("selected");
      });
      hideDefinition();
    }
  });

  // Search
  searchInput.addEventListener("input", (e) => handleSearch(e.target.value));
  searchInput.addEventListener("focus", () => {
    if (searchInput.value.trim()) {
      handleSearch(searchInput.value);
    }
  });
  document.addEventListener("click", (e) => {
    if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
      searchResults.style.display = "none";
    }
  });

  // Modal
  closeModal.addEventListener("click", closeSearchModal);
  searchModal.addEventListener("click", (e) => {
    if (e.target === searchModal) closeSearchModal();
  });
  modalSearchInput.addEventListener("input", (e) =>
    renderModalResults(e.target.value),
  );

  // Keyboard shortcuts
  document.addEventListener("keydown", handleKeyboard);
}

function handleKeyboard(e) {
  // Ignore if typing in input
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") {
    if (e.key === "Escape") {
      e.target.blur();
      closeSearchModal();
    }
    return;
  }

  const item = items[currentIndex];
  if (!item) return;

  switch (e.key) {
    case "1":
    case "2":
    case "3":
      const idx = parseInt(e.key) - 1;
      const predictions = item.model_prediction.top_event_types;
      if (idx < predictions.length) {
        selectEventType(predictions[idx]);
      }
      break;

    case "ArrowLeft":
      e.preventDefault();
      goToPrev();
      break;

    case "ArrowRight":
      e.preventDefault();
      goToNext();
      break;

    case " ":
      e.preventDefault();
      toggleDefinition();
      break;

    case "s":
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        saveCurrentAnnotation();
      }
      break;

    case "n":
    case "N":
      notInListCheckbox.checked = !notInListCheckbox.checked;
      notInListCheckbox.dispatchEvent(new Event("change"));
      break;

    case "/":
      e.preventDefault();
      openSearchModal();
      break;

    case "Escape":
      closeSearchModal();
      break;
  }
}

// Start the app
document.addEventListener("DOMContentLoaded", init);
