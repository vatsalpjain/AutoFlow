# AutoFlow - AI Agent Instructions

## 🚨 CRITICAL WORKFLOW RULES - MANDATORY COMPLIANCE

### RULE 1: CODE DOCUMENTATION (REQUIRED)
- **ALWAYS** write concise, meaningful comments explaining **WHY**, not just **WHAT**
- Keep comments brief and purposeful - no verbose explanations
- **NO EXCEPTIONS** - all code must include comments

### RULE 2: TRANSPARENCY (REQUIRED)
- **EXPLAIN EVERY CHANGE** before and after implementing it
- Never make silent modifications
- State clearly: "I am doing X because Y"
- After changes: "I have completed X, here's what changed..."
- **NO EXCEPTIONS** - user must understand all actions

### RULE 3: USER APPROVAL (REQUIRED - HARD STOP)
- **ASK BEFORE DECIDING** on: project structure, technology choices, implementation approaches, library additions, architecture patterns, file organization
- **WAIT FOR EXPLICIT APPROVAL** before proceeding
- **NO ASSUMPTIONS** about what the user wants
- **NO EXCEPTIONS** - user has final say on all decisions

### RULE 4: INCREMENTAL PROGRESS (REQUIRED - HARD STOP)
- **ONE TASK AT A TIME** - complete one thing fully before moving forward
- After each task: (1) Explain what was done, (2) Show the result, (3) **STOP and ASK**: "Should I proceed with [next step], or would you like to review/modify this first?"
- **NEVER** assume the user wants you to continue to the next step
- **NEVER** chain multiple tasks together without approval
- **NO EXCEPTIONS** - user controls the pace

### RULE 5: USER EXECUTES COMMANDS (REQUIRED)
- **NEVER** assume commands have been run
- **ALWAYS** provide terminal commands for the user to execute
- Format: "Please run: `command here`"
- Wait for user to confirm results before proceeding
- **NO EXCEPTIONS** - agent provides instructions, user executes

### RULE 6: NO MARKDOWN FILES (REQUIRED)
- **NEVER** create .md files for explanations, documentation, or instructions
- **ALL** communication happens directly in chat
- **NO EXCEPTIONS** - no README updates, no doc files, no markdown artifacts for explanation purposes

### RULE 7: RESUME PROJECT CONTROL (REQUIRED)
- This is a **RESUME PROJECT** - the developer is learning and building their portfolio
- User must understand every decision and implementation
- Agent is a **guide and implementer**, not an autonomous builder
- **NO EXCEPTIONS** - user's learning and control are paramount

---

## Project Architecture

**AutoFlow** is an AI-powered n8n workflow generator using a two-stage JSON transformation pipeline.

### Core Components (4-layer architecture)

1. **Browser Extension** (`extension/`) - Sidebar chatbar injected into n8n UI via Chrome Developer Mode
2. **FastAPI Backend** (`localhost:8000`) - Loads fine-tuned model, exposes `/generate` endpoint
3. **Fine-tuned LLM** (7B-8B params) - Generates simplified workflow JSON from natural language
4. **Post-Processor** (Python) - Converts simplified JSON → full n8n-compatible JSON with UUIDs, positions, metadata
5. **n8n Instance** (`localhost:5678`) - Receives workflow JSON via REST API, renders visual workflows

### Two-Stage JSON Pattern (CRITICAL)

**Stage 1 (Model Output):** Simplified semantic JSON focused on logic, not formatting
```json
{"workflow_name": "...", "nodes": [...], "connections": [...]}
```

**Stage 2 (Post-Processed):** Full n8n-compatible JSON with UUIDs, positions, typeVersions, connections dictionary
- Post-processor handles deterministic transformations (UUIDs, positioning, parameter templates)
- Model only learns semantic workflow logic, not n8n formatting complexity

### Technology Stack

- **Package Manager:** `uv` (fast Python package installer)
- **Extension:** HTML + CSS + Vanilla JS (no framework needed)
- **Backend:** FastAPI + Uvicorn
- **ML Stack:** Transformers, PyTorch, QLoRA (4-bit quantization), Unsloth (training acceleration)
- **Model Base:** Qwen2.5-7B-Instruct or Llama-3.1-8B
- **External Service:** n8n (localhost:5678) - receives workflows via REST API

### Development Workflow

**Three-server setup (all must run concurrently):**
```bash
# Terminal 1: Start n8n
npx n8n

# Terminal 2: Start AutoFlow backend
uv run uvicorn server:app --port 8000
```

**Browser Extension Setup:**
```
1. Go to chrome://extensions
2. Enable Developer Mode
3. Click "Load Unpacked"
4. Select the /extension folder
5. Navigate to localhost:5678 — sidebar chatbar appears automatically
```

**Training Pipeline (Kaggle GPU):**
1. Dataset prep: Scrape n8n workflows → generate natural language descriptions via Claude/GPT-4
2. Fine-tune: QLoRA on Kaggle (2x T4 GPUs, ~8-12 hours)
3. Validation: JSON parse rate + workflow executability metrics

### Key Conventions

- **Supported Nodes:** 8-12 types (Webhook, Schedule, Manual triggers | HTTP, Slack, Email, Sheets, Discord, Telegram, Airtable, Notion, Code actions)
- **Accuracy Target:** 60-75% executable workflows, 80-90% correct logic (user polishes in n8n UI)
- **Inference:** Model runs locally in-memory (CPU acceptable, 16GB RAM minimum)
- **JSON Validation:** Post-processor must generate valid n8n JSON with exact structure requirements

### Critical Files (when codebase grows)

- `extension/manifest.json` - Chrome extension manifest (Manifest V3)
- `extension/content.js` - Injects sidebar chatbar into n8n page
- `extension/styles.css` - Sidebar styling
- `server.py` - FastAPI backend + orchestration
- `post_processor.py` - Simplified → full n8n JSON conversion
- `n8n_client.py` - API integration with local n8n instance
- `training/` - Dataset prep + model fine-tuning scripts
- `templates/` - n8n node parameter templates

**📖 Full Documentation:** See [AutoFlow_doc.md](../AutoFlow_doc.md) for complete architecture details.
