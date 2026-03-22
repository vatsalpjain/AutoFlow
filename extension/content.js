// ============================================================
// AutoFlow Content Script
// Injects a minimal sidebar into the n8n UI with a greeting
// and a chatbar for AI-powered workflow generation.
// Runs on localhost:5678 (n8n instance).
// ============================================================

(function () {
  "use strict";

  // --- Prevent double-injection if script runs multiple times ---
  if (document.getElementById("autoflow-sidebar")) return;

  // =============================================================
  // SECTION 1: Build the Sidebar HTML
  // Minimal layout: greeting + chatbar only.
  // =============================================================

  function buildSidebarHTML() {
    return `
      <div id="autoflow-sidebar">

        <!-- Header: greeting -->
        <div class="af-header">
          <h2 class="af-greeting">Hello, User! <span class="af-sparkle">✦</span></h2>
        </div>

        <!-- Spacer pushes chatbar to the bottom -->
        <div class="af-spacer"></div>

        <!-- Chatbar: where users type workflow prompts -->
        <div class="af-chatbar">
          <div class="af-chatbar-inner">
            <input
              type="text"
              class="af-chatbar-input"
              placeholder="Describe a workflow..."
              id="af-chatbar-input"
            />
            <button class="af-chatbar-send" id="af-chatbar-send" title="Generate workflow">
              ➤
            </button>
          </div>
        </div>

      </div>

      <!-- Toggle button: opens/closes the sidebar -->
      <button id="autoflow-toggle" title="Toggle AutoFlow">⚡</button>
    `;
  }

  // =============================================================
  // SECTION 2: Inject Sidebar into the Page
  // =============================================================

  const wrapper = document.createElement("div");
  wrapper.id = "autoflow-wrapper";
  wrapper.innerHTML = buildSidebarHTML();
  document.body.appendChild(wrapper);

  // =============================================================
  // SECTION 3: Event Listeners
  // =============================================================

  const sidebar = document.getElementById("autoflow-sidebar");
  const toggleBtn = document.getElementById("autoflow-toggle");

  // --- Toggle Sidebar Open/Close ---
  toggleBtn.addEventListener("click", () => {
    sidebar.classList.toggle("af-collapsed");
    toggleBtn.classList.toggle("af-collapsed");
  });

  // --- Chatbar Submit ---
  // Logs to console for now — will POST to localhost:8000/generate later
  const chatInput = document.getElementById("af-chatbar-input");
  const chatSend = document.getElementById("af-chatbar-send");

  function handleSend() {
    const prompt = chatInput.value.trim();
    if (!prompt) return;

    // TODO: Replace with fetch() to FastAPI backend
    console.log("[AutoFlow] Prompt submitted:", prompt);
    chatInput.value = "";
  }

  // Send on button click
  chatSend.addEventListener("click", handleSend);

  // Send on Enter key
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  console.log("[AutoFlow] Sidebar injected into n8n UI ✓");
})();
