// ============================================================
// AutoFlow Content Script
// Injects a minimal sidebar into the n8n UI with a greeting
// and a chatbar for AI-powered workflow generation.
// Runs on localhost:5678 (n8n instance).
// ============================================================

(function () {
  "use strict";

  const WORKFLOW_ID_STORAGE_KEY = "autoflow_current_workflow_id";

  function extractWorkflowIdFromUrl() {
    // n8n workflow editor URL usually looks like /workflow/<id>.
    const match = window.location.pathname.match(/\/workflow\/([^/]+)/);
    return match ? match[1] : null;
  }

  function getCurrentWorkflowId() {
    return extractWorkflowIdFromUrl() || sessionStorage.getItem(WORKFLOW_ID_STORAGE_KEY);
  }

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

  async function handleSend() {
    const prompt = chatInput.value.trim();
    if (!prompt) return;

    // Give instant UI feedback so users know generation is in progress.
    chatSend.disabled = true;
    const originalSymbol = chatSend.textContent;
    chatSend.textContent = "...";

    try {
      const response = await fetch("http://localhost:8000/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          prompt,
          workflow_id: getCurrentWorkflowId(),
        }),
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || `Request failed with status ${response.status}`);
      }

      const data = await response.json();
      console.log("[AutoFlow] Backend response:", data);

      // n8n API creates the workflow but does not auto-open it in UI.
      // Navigate to the created workflow so users immediately see the render.
      const workflowId =
        data?.n8n?.id ||
        data?.n8n?.data?.id ||
        data?.id;

      if (workflowId) {
        // Persist id so future requests can update the same workflow.
        sessionStorage.setItem(WORKFLOW_ID_STORAGE_KEY, workflowId);

        const workflowUrl = `${window.location.origin}/workflow/${workflowId}`;
        const currentUrl = `${window.location.origin}${window.location.pathname}`;

        if (currentUrl === workflowUrl) {
          // Force refresh so the editor reloads updated workflow data.
          window.location.reload();
        } else {
          window.location.assign(workflowUrl);
        }
      }

      chatInput.value = "";
    } catch (error) {
      console.error("[AutoFlow] Failed to generate workflow:", error);
    } finally {
      // Always restore the send button state after the request completes.
      chatSend.disabled = false;
      chatSend.textContent = originalSymbol;
    }
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
