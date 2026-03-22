import json
import os
import time
import re
import random
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

# Load environment variables from .env at project root
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
INPUT_FILE      = Path("training/data/n8n_dataset.jsonl")
OUTPUT_FILE     = Path("training/data/n8n_dataset_clean.jsonl")
CHECKPOINT_FILE = Path("training/data/.checkpoint")
FAILED_FILE     = Path("training/data/.failed_ids.txt")

GROQ_API_KEY    = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY or GROQ_API_KEY == "YOUR_GROQ_API_KEY":
    raise RuntimeError("Set GROQ_API_KEY in .env file (project root)")

MODEL           = "llama-3.1-8b-instant"
MAX_RECORDS     = 500

# Nodes that are pure UI decoration — strip them from output
SKIP_NODE_TYPES = {
    "n8n-nodes-base.stickyNote",
    "n8n-nodes-base.noOp",
}

# Parameters that are noisy / irrelevant for model to learn
STRIP_PARAMS = {
    "authentication", "options", "sendHeaders",
    "sendQuery", "sendBody", "specifyBody",
    "contentType", "jsonBody"
}

client = Groq(api_key=GROQ_API_KEY)

# ─────────────────────────────────────────────────────────────────────────────
# IMPROVED SYSTEM PROMPTS — Rotate between them for variety
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPTS = [
    # Style 1: Direct/Imperative (like giving orders)
    """Convert this n8n workflow title into how a user would naturally ask for it.

Write 1-2 short sentences. Be direct and specific. Use real service names.

Examples:
Title: "Gmail to Slack Notifier"
→ "Send new Gmail emails to a Slack channel."

Title: "Form Submissions to Airtable"
→ "Add Google Form responses to an Airtable base."

Title: "Daily Twitter Digest"
→ "Post a summary of my RSS feeds to Twitter every morning."

Title: "Webhook Logger"
→ "Save incoming webhook data to Google Sheets."

Title: "Customer Onboarding Email"
→ "Generate a welcome email with AI when someone fills out the signup form."
""",

    # Style 2: Conversational/Natural (like chatting)
    """Rewrite this workflow title as a natural user request.

Write how someone would actually ask for this in conversation. 1-2 sentences max.

Examples:
Title: "Slack Reminder Bot"
→ "I need reminders posted to Slack based on my calendar events."

Title: "Invoice Generator"
→ "Create PDF invoices from Airtable records and email them to clients."

Title: "Bug Reporter"
→ "Post new GitHub issues to our Discord channel."

Title: "Lead Capture"
→ "Save contact form submissions to my CRM and send a thank you email."

Title: "Content Scheduler"
→ "Pull scheduled posts from Notion and publish them to LinkedIn automatically."
""",

    # Style 3: Problem/Solution (explaining the need)
    """Transform this workflow title into a user's request that explains what they want automated.

Be natural and concise. 1-2 sentences.

Examples:
Title: "Email Parser"
→ "Extract data from incoming emails and add it to a spreadsheet."

Title: "Social Media Cross-poster"
→ "Publish new blog posts to Twitter and LinkedIn at the same time."

Title: "Support Ticket Router"
→ "Send high-priority Zendesk tickets to Slack immediately."

Title: "Meeting Notes Organizer"
→ "Upload meeting recordings to Google Drive and summarize them with AI."

Title: "Payment Notifications"
→ "Alert me on Telegram whenever a Stripe payment comes through."
""",

    # Style 4: Goal-oriented (focused on outcome)
    """Rewrite this workflow title as what the user wants to achieve.

Keep it natural and specific. 1-2 sentences.

Examples:
Title: "Newsletter Automation"
→ "Send weekly newsletters to subscribers from my Mailchimp list."

Title: "Data Backup"
→ "Back up my Airtable data to Google Sheets every night."

Title: "Event Registrations"
→ "Add Eventbrite registrants to my email list and send confirmation."

Title: "Image Processor"
→ "Resize uploaded images and save them to Cloudinary."

Title: "Expense Tracker"
→ "Log business expenses from email receipts into a spreadsheet."
"""
]

def _clean_groq_output(raw: str) -> str:
    """Strip Groq model preamble and normalize to a plain instruction sentence."""
    text = raw.strip()

    # If the model added a preamble ("Here's a rewritten..."), take last paragraph
    if re.match(r'^(Here|Context:|Note:|Sure)', text, re.IGNORECASE):
        parts = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
        text = parts[-1] if parts else text

    # If it's a numbered list, take only option 1
    if re.match(r'^\d+\.', text):
        text = re.split(r'\n\d+\.', text)[0]
        text = re.sub(r'^\d+\.\s*', '', text).strip()

    # Strip → or -> prefix
    text = re.sub(r'^(→|->)\s*', '', text).strip()

    # Strip outer quotes
    text = text.strip('"\'')

    # Last resort: scan for first real sentence
    if re.match(r'^(Here|Context:|Title|Sure|Note:|I\'ve)', text, re.IGNORECASE):
        for line in raw.splitlines():
            line = line.strip().strip('"\'').strip()
            if line and not re.match(r'^(Here|Context:|Title|Sure|Note:|\d+\.)', line, re.IGNORECASE):
                text = line
                break

    return text.strip()


def rewrite_instruction(title: str, context: str) -> str:
    """Use rotating system prompts for natural variety"""
    short_context = context[:250].strip()
    short_context = re.sub(r'https?://\S+', '', short_context).strip()
    
    # Randomly select a prompt style to avoid patterns
    system_prompt = random.choice(SYSTEM_PROMPTS)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": f"Title: {title}\nContext: {short_context}"}
        ],
        max_tokens=100,
        temperature=0.7  # ← INCREASED from 0.3 for more variety
    )
    raw = response.choices[0].message.content.strip()
    return _clean_groq_output(raw)

# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION — Reject repetitive patterns
# ─────────────────────────────────────────────────────────────────────────────
rejection_reasons: dict = {}
seen_instruction_starts = {}  # Track if too many start the same way

def is_valid_record(simplified: dict, instruction: str) -> bool:
    """Thorough sanity checks — reject anything the model shouldn't learn from"""
    nodes = simplified.get("nodes", [])
    edges = simplified.get("connections", [])
    name  = simplified.get("name", "")

    def reject(reason: str) -> bool:
        rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
        return False

    if len(nodes) == 0:
        return reject("no_nodes")

    if not name or name.strip() == "":
        return reject("empty_workflow_name")

    if len(instruction) < 15:
        return reject("instruction_too_short")

    # Reject if still looks like a preamble
    if re.match(r'^(Here|Context:|Title)', instruction, re.IGNORECASE):
        return reject("instruction_has_preamble")
    
    # NEW: Detect repetitive patterns (too many "When...", "Every...", etc.)
    first_word = instruction.split()[0].lower() if instruction.split() else ""
    if first_word:
        seen_instruction_starts[first_word] = seen_instruction_starts.get(first_word, 0) + 1
        # If more than 30% start with same word, flag it (but don't reject yet)
        # This is just for monitoring

    # Reject if no connections
    if len(edges) == 0 and len(nodes) > 1:
        return reject("no_connections")

    for node in nodes:
        if not node.get("name", "").strip():
            return reject("node_missing_name")
        if not node.get("type", "").strip():
            return reject("node_missing_type")

    node_names = [n["name"] for n in nodes]
    if len(node_names) != len(set(node_names)):
        return reject("duplicate_node_names")

    valid_names = set(node_names)
    for edge in edges:
        if edge.get("from") not in valid_names or edge.get("to") not in valid_names:
            return reject("orphan_connection")

    for edge in edges:
        if edge.get("from") == edge.get("to"):
            return reject("self_loop")

    return True

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Clean the output JSON
# ─────────────────────────────────────────────────────────────────────────────
def simplify_type(raw_type: str) -> str:
    """Convert n8n internal type string to readable label"""
    t = raw_type.replace("n8n-nodes-base.", "")
    t = t.replace("@n8n/n8n-nodes-langchain.", "langchain.")
    return t

def clean_parameters(params: dict) -> dict:
    """Keep only meaningful parameters, drop noise"""
    if not isinstance(params, dict):
        return params
    return {k: v for k, v in params.items()
            if k not in STRIP_PARAMS
            and v not in [None, "", {}, []]
            and not k.startswith("__")}

def build_simplified_output(workflow_json: dict) -> dict:
    """Convert full n8n JSON → clean simplified JSON"""
    raw_nodes   = workflow_json.get("nodes", [])
    connections = workflow_json.get("connections", {})

    name_to_type = {}
    simplified_nodes = []

    for node in raw_nodes:
        node_type = node.get("type", "")

        if node_type in SKIP_NODE_TYPES:
            continue

        name        = node.get("name", "")
        simple_type = simplify_type(node_type)
        clean_params = clean_parameters(node.get("parameters", {}))

        name_to_type[name] = simple_type

        simplified_nodes.append({
            "name":       name,
            "type":       simple_type,
            "parameters": clean_params
        })

    edges = []
    valid_names = {n["name"] for n in simplified_nodes}

    for src_name, conn_data in connections.items():
        if src_name not in valid_names:
            continue
        for port_outputs in conn_data.get("main", []):
            for edge in (port_outputs or []):
                dst_name = edge.get("node", "")
                if dst_name in valid_names:
                    edges.append({
                        "from": src_name,
                        "to":   dst_name
                    })

    return {
        "name":        workflow_json.get("name", "Untitled Workflow"),
        "nodes":       simplified_nodes,
        "connections": edges
    }

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        return CHECKPOINT_FILE.read_text().strip()
    return None

def save_checkpoint(workflow_id: str):
    CHECKPOINT_FILE.write_text(workflow_id)

def log_failed(workflow_id: str):
    with open(FAILED_FILE, "a") as f:
        f.write(workflow_id + "\n")

with open(INPUT_FILE, encoding="utf-8") as f:
    all_records = [json.loads(line) for line in f if line.strip()]

print(f"📂 Total records loaded  : {len(all_records)}")

already_done = 0
if OUTPUT_FILE.exists():
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        already_done = sum(1 for line in f if line.strip())
print(f"📊 Already cleaned       : {already_done}")

last_done_id = load_checkpoint()
skip = last_done_id is not None

if skip:
    print(f"📌 Resuming after ID     : {last_done_id}")
else:
    print("🆕 Starting fresh")

processed = failed = skipped_invalid = 0

with open(OUTPUT_FILE, "a", encoding="utf-8") as out:
    for record in all_records:

        if processed >= MAX_RECORDS:
            print(f"\n🛑 Reached limit of {MAX_RECORDS} records — stopping.")
            break

        if skip:
            if record["id"] == last_done_id:
                skip = False
            continue

        try:
            simplified = build_simplified_output(record["output"])
            new_instruction = rewrite_instruction(
                title   = record["instruction"],
                context = record["context"]
            )

            if not is_valid_record(simplified, new_instruction):
                skipped_invalid += 1
                save_checkpoint(record["id"])
                time.sleep(2)
                continue

            final_record = {
                "instruction": new_instruction,
                "output":      simplified,
                "meta": {
                    "id":         record["id"],
                    "tags":       record["meta"].get("tags", []),
                    "services":   record["meta"].get("services", []),
                    "node_count": record["meta"].get("node_count", 0),
                    "difficulty": record["meta"].get("difficulty", ""),
                    "author":     record["meta"].get("author", ""),
                }
            }

            out.write(json.dumps(final_record, ensure_ascii=False) + "\n")
            out.flush()

            save_checkpoint(record["id"])
            processed += 1

            if processed % 50 == 0:
                print(f"  ✅ {processed} records done...")

            time.sleep(2.1)

        except Exception as e:
            err_str = str(e)
            if "rate_limit" in err_str.lower() or "429" in err_str:
                print(f"\n⏳ Rate limit hit — sleeping 60s...")
                time.sleep(61)
                continue
            else:
                print(f"  ⚠️  Failed ID {record['id']}: {e}")
                log_failed(record["id"])
                save_checkpoint(record["id"])
                failed += 1
                time.sleep(2)
                continue

print(f"\n🎉 Session done!")
print(f"  ✅ This run        : {processed}")
print(f"  ❌ Failed          : {failed}")
print(f"  🚫 Invalid/Empty   : {skipped_invalid}")
if rejection_reasons:
    print(f"     Breakdown:")
    for reason, count in sorted(rejection_reasons.items(), key=lambda x: -x[1]):
        print(f"       {reason:<30} : {count}")

# Show instruction variety stats
if seen_instruction_starts:
    print(f"\n📊 Instruction Starting Words:")
    total_instructions = sum(seen_instruction_starts.values())
    sorted_starts = sorted(seen_instruction_starts.items(), key=lambda x: -x[1])[:10]
    for word, count in sorted_starts:
        percentage = (count / total_instructions) * 100
        print(f"       '{word}':{' '*(12-len(word))} {count:3d} ({percentage:5.1f}%)")
    
print(f"\n  📊 Total cleaned   : {already_done + processed}")
print(f"  📂 Total raw       : {len(all_records)}")
print(f"\n  Run again to continue from checkpoint.")