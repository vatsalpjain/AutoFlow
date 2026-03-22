# AutoFlow - AI-Powered n8n Workflow Generator

## Project Overview

**AutoFlow** is an AI-powered tool that generates n8n workflows from natural language descriptions. Users describe what they want in plain English directly inside n8n via a browser extension, and the system generates 80% complete workflows that auto-import into their local n8n instance for final tweaking.

**Goal:** 10x faster n8n workflow creation through AI-assisted scaffolding.

---

## What We're Building

### Core Functionality

* User types in AutoFlow chatbar (injected into n8n UI via extension)
* FastAPI backend receives prompt, runs fine-tuned model
* Model generates simplified workflow JSON
* Post-processor converts to full n8n-compatible JSON
* Workflow auto-imports to local n8n via API
* User fine-tunes credentials and parameters in n8n UI

### Scope (3-4 Week MVP)

* **Supported Nodes:** 8-12 types
  * Triggers: Webhook, Schedule, Manual
  * Actions: HTTP Request, Slack, Email, Google Sheets, Discord, Telegram, Airtable, Notion, Code
* **Workflow Complexity:** Linear flows and simple branching
* **Expected Accuracy:** 60-75% executable workflows, 80-90% correct logic
* **User Experience:** AI generates scaffold, user polishes in n8n UI

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────┐
│         Browser Extension (local folder)        │
│   - Chatbar injected into n8n UI                │
│   - Makes fetch() calls to FastAPI              │
│   - No hosting, no port, just mounted on n8n    │
└──────────────────┬──────────────────────────────┘
                   │ HTTP POST (localhost:8000)
                   ▼
┌─────────────────────────────────────────────────┐
│         FastAPI Backend (localhost:8000)         │
│                                                 │
│   ┌─────────────────────────────────────────┐   │
│   │  Fine-tuned LLM (3B-4B params)          │   │
│   │  - Generates simplified workflow JSON   │   │
│   └──────────────┬──────────────────────────┘   │
│                  │                               │
│   ┌──────────────▼──────────────────────────┐   │
│   │  Post-Processor (Python)                │   │
│   │  - Converts simplified → full n8n JSON  │   │
│   │  - Adds UUIDs, positions, metadata      │   │
│   │  - Fills parameter templates            │   │
│   └──────────────┬──────────────────────────┘   │
└──────────────────┼──────────────────────────────┘
                   │ HTTP POST (localhost:5678)
                   ▼
┌─────────────────────────────────────────────────┐
│         n8n Instance (localhost:5678)           │
│   - Receives workflow JSON via API              │
│   - Renders visual workflow UI automatically    │
│   - User edits credentials and parameters       │
└─────────────────────────────────────────────────┘
```

### Component Breakdown

**1. Browser Extension**

* HTML + CSS + JS files in a local folder
* Injects chatbar UI into n8n page
* Makes two fetch() calls: model API + n8n API
* No deployment or hosting needed
* Loaded via Chrome Developer Mode

**2. FastAPI Backend**

* Full backend server running locally
* Loads and runs fine-tuned model
* Handles post-processing logic
* Exposes `/generate` endpoint

**3. AI Model**

* Base: Qwen2.5-7B or Llama-3.1-8B
* Fine-tuned with QLoRA on n8n workflow dataset
* Outputs simplified JSON format
* Runs locally inside FastAPI server

**4. Post-Processor**

* Python script inside FastAPI
* Transforms simplified JSON to full n8n format
* Handles UUIDs, positioning, parameter templates

**5. n8n**

* Runs separately as workflow engine
* Receives final JSON via REST API
* Renders visual workflow automatically

---

## Two-Stage JSON Approach

### Stage 1: Model Output (Simplified JSON)

```json
{
  "workflow_name": "Webhook to Slack",
  "nodes": [
    {"id": "trigger", "type": "webhook", "method": "POST"},
    {"id": "slack", "type": "slack_send_message",
     "channel": "#general", "message": "{{$json.body}}"}
  ],
  "connections": [
    {"from": "trigger", "to": "slack"}
  ]
}
```

### Stage 2: Post-Processed (Full n8n JSON)

```json
{
  "name": "Webhook to Slack",
  "nodes": [
    {
      "id": "uuid-1234-5678",
      "name": "Trigger",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 1,
      "position": [250, 300],
      "parameters": {"path": "webhook-path", "httpMethod": "POST"}
    }
  ],
  "connections": {
    "uuid-1234-5678": {
      "main": [[{"node": "uuid-9012-3456", "type": "main", "index": 0}]]
    }
  }
}
```

---

## Speed Expectation

| **Step**             | **Time**         |
| -------------------------- | ---------------------- |
| Extension fetch call       | ~10ms                  |
| Model inference (3B local) | 3-8 seconds            |
| Post-processing            | ~50ms                  |
| n8n API import             | ~200ms                 |
| **Total**            | **~4-9 seconds** |

---

## Recommended Setup

### Hardware

* **Training:** Kaggle Free GPU (2x T4, 30GB VRAM)
* **Local Inference:** 16GB RAM minimum

### Software Stack

**Backend:**

* Python 3.10+
* FastAPI + Uvicorn
* Transformers + PyTorch
* PEFT + BitsandBytes (QLoRA)
* uv (package manager)

**Extension:**

* HTML + CSS + Vanilla JS
* No framework needed

**Training:**

* Kaggle Notebook
* Unsloth (3x faster QLoRA)
* Hugging Face Transformers

### Installation

```bash
# 1. Install n8n
npx n8n

# 2. Setup AutoFlow backend
git clone <your-repo>
cd autoflow

# Using uv
uv venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
uv pip install fastapi uvicorn transformers torch peft bitsandbytes

# 3. Run backend
uv run uvicorn server:app --port 8000
```

```javascript
// 4. Load Extension in Chrome
// Go to chrome://extensions
// Enable Developer Mode
// Click "Load Unpacked"
// Select /extension folder
// Done - chatbar appears in n8n!
```

### Running AutoFlow

```bash
# Terminal 1: Start n8n
npx n8n

# Terminal 2: Start AutoFlow backend
uv run uvicorn server:app --port 8000

# Open Chrome → go to localhost:5678
# AutoFlow chatbar is injected automatically
```

---

## 4-Week Timeline

**Week 1:** Dataset prep - scrape 500-1000 workflows, generate descriptions, clean data

**Week 2:** Fine-tune model on Kaggle using QLoRA + Unsloth

**Week 3:** Build FastAPI backend + post-processor, test workflow generation

**Week 4:** Build browser extension, integrate everything, test end-to-end

---

## Data Pipeline — Formatting, Preprocessing & Cleaning

### Overview

The training dataset is built in two stages from raw n8n community workflows. The goal is to produce clean `(instruction, simplified_json)` pairs that teach the model **workflow logic only** — all formatting concerns (UUIDs, positions, credentials, typeVersions) are left to the deterministic post-processor.

### Stage 1: Raw Extraction (`data_collection.py`)

**Source:** [nusquama/n8nworkflows.xyz](https://github.com/nusquama/n8nworkflows.xyz) cloned locally.

**What it does:**

* Iterates every workflow folder under `workflows/`
* Reads three files per folder via glob (handles inconsistent naming):
  * `readme*` — human description of the workflow
  * `metada*` — metadata JSON (note: repo typo, no `.json` extension)
  * `*.json` (excluding metadata) — full n8n workflow JSON
* Extracts: instruction (title from readme), context (first few lines of readme), full workflow JSON, metadata (tags, author, services, difficulty)
* Writes one JSONL record per workflow to `n8n_dataset.jsonl`

**Output:** `training/data/n8n_dataset.jsonl` — 7,633 raw records

**Raw record structure:**

```json
{
  "id": "4448",
  "instruction": "AI Client Onboarding Agent: Auto Welcome Email Generator",
  "context": "This workflow automates the onboarding process for new clients...",
  "output": { /* full n8n JSON with UUIDs, positions, stickyNotes, etc. */ },
  "meta": {
    "folder_name": "...",
    "tags": [],
    "created_at": "",
    "author": "yaron-nofluff",
    "source_url": "...",
    "services": ["gmail", "googleSheetsTrigger", "langchain.chainLlm"],
    "node_count": 20,
    "difficulty": "complex"
  }
}
```

### Stage 2: Cleaning & Rewriting (`build_dataset.py`)

**What it does (per record):**

**1. Instruction Rewrite (via Groq API)**

* Raw instructions are workflow titles, not user prompts — unusable for training
* Each title + context is sent to `llama-3.1-8b-instant` on Groq (free tier)
* Groq rewrites it as a natural user request starting with "Create", "Build", "Make", or "Set up"
* URLs are stripped from context before sending

Before:

```
"AI Client Onboarding Agent: Auto Welcome Email Generator"
```

After:

```
"Create a workflow that sends a personalized welcome email to new clients when they submit a Google Form."
```

**2. Output JSON Simplification**

The full n8n JSON is stripped down to only what the model needs to learn:

| Removed (post-processor handles)     | Kept (model must learn)                            |
| ------------------------------------ | -------------------------------------------------- |
| `meta.instanceId`                  | `name` (workflow name)                           |
| `node.id` (UUIDs)                  | `node.name` (e.g. "Send Email")                  |
| `node.position`                    | `node.type` → simplified (e.g. "gmail")         |
| `node.typeVersion`                 | `node.parameters` → cleaned                     |
| `node.disabled`                    | `connections` → flat edge list `[{from, to}]` |
| `credentials` block                |                                                    |
| `stickyNote` nodes (UI decoration) |                                                    |
| `noOp` nodes (UI decoration)       |                                                    |

**Type simplification rules:**

```
"n8n-nodes-base.gmail"              → "gmail"
"n8n-nodes-base.googleSheets"       → "googleSheets"
"@n8n/n8n-nodes-langchain.chainLlm" → "langchain.chainLlm"
```

**Parameter cleaning:** Removes noisy/irrelevant keys: `authentication`, `options`, `sendHeaders`, `sendQuery`, `sendBody`, `specifyBody`, `contentType`, `jsonBody`, and any keys starting with `__` or having empty values.

**Connection flattening:** n8n's nested connection dict is converted to a simple edge list:

```json
// Before (n8n format):
{ "Send Email": { "main": [[{"node": "Log Result", "type": "main", "index": 0}]] } }

// After (simplified):
[{"from": "Send Email", "to": "Log Result"}]
```

**3. Validation Checks**

Every record is validated before writing. Rejected if:

* Zero nodes after stripping UI nodes
* Workflow name is empty
* Instruction is too short (< 15 chars) or echoes the prompt
* Any node has an empty name or type
* Duplicate node names exist
* Any connection references a non-existent node
* Self-loop connections exist

**4. Checkpointing & Rate Limiting**

* Saves checkpoint after every record — safe to stop/resume anytime
* Groq free tier: 30 req/min → 2.1s sleep between calls
* On 429 rate limit: sleeps 60s and retries the same record
* Failed IDs logged to `.failed_ids.txt` for manual review
* Current limit: 1,000 records per run (configurable via `MAX_RECORDS`)

### Final Cleaned Record Structure (`n8n_dataset_clean.jsonl`)

```json
{
  "instruction": "Create a workflow that sends a personalized welcome email to new clients when they submit a Google Form.",
  "output": {
    "name": "Onboarding",
    "nodes": [
      {"name": "Form Trigger",   "type": "googleSheetsTrigger", "parameters": {"sheetName": "Clients"}},
      {"name": "Generate Email", "type": "langchain.chainLlm",  "parameters": {"prompt": "..."}},
      {"name": "Send Email",     "type": "gmail",               "parameters": {"to": "={{$json.email}}", "subject": "Welcome!"}}
    ],
    "connections": [
      {"from": "Form Trigger",   "to": "Generate Email"},
      {"from": "Generate Email", "to": "Send Email"}
    ]
  },
  "meta": {
    "id": "4448",
    "tags": [],
    "services": ["googleSheetsTrigger", "langchain.chainLlm", "gmail"],
    "node_count": 9,
    "difficulty": "complex",
    "author": "yaron-nofluff"
  }
}
```

* `instruction` — model input during training
* `output` — model target output (simplified JSON string)
* `meta` — never used in training, only for filtering and train/val splitting
