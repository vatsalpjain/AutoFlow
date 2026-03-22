import os
import json
import re
from pathlib import Path

WORKFLOWS_DIR = Path(r"C:\dev\personal\S3Projects\n8n_Data\n8nworkflows.xyz\workflows")
OUTPUT_DIR  = Path(__file__).parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "n8n_dataset.jsonl"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def parse_readme(readme_text, fallback_name):
    lines = [l.strip().lstrip("#").strip() for l in readme_text.splitlines() if l.strip()]
    instruction = lines[0] if lines else fallback_name
    context     = " ".join(lines[1:6])
    return instruction, context

def get_node_info(workflow_json):
    nodes      = workflow_json.get("nodes", [])
    node_count = len(nodes)
    services   = list({
        n.get("type", "")
         .replace("n8n-nodes-base.", "")
         .replace("@n8n/n8n-nodes-langchain.", "langchain.")
        for n in nodes if n.get("type")
    })
    if node_count <= 3:    difficulty = "easy"
    elif node_count <= 7:  difficulty = "medium"
    else:                  difficulty = "complex"
    return services, node_count, difficulty

written = 0
skipped = 0

print(f"📂 Reading from : {WORKFLOWS_DIR}")
print(f"💾 Writing to   : {OUTPUT_FILE}")
print(f"⏳ Processing...")

with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
    for folder in sorted(WORKFLOWS_DIR.iterdir()):
        if not folder.is_dir():
            continue

        try:
            # ── Find files using glob (handles any naming pattern) ──────────
            readme_files   = list(folder.glob("readme*"))
            metadata_files = list(folder.glob("metada*"))   # repo typo: "metada" not "metadata"
            # workflow JSON = any .json file that is NOT the metadata file
            all_jsons      = list(folder.glob("*.json"))
            workflow_files = [f for f in all_jsons if not f.name.startswith("metada")]

            # Skip if any required file is missing
            if not readme_files or not metadata_files or not workflow_files:
                skipped += 1
                continue

            readme_path   = readme_files[0]
            meta_path     = metadata_files[0]
            workflow_path = workflow_files[0]  # largest JSON = likely the workflow
            if len(workflow_files) > 1:        # pick biggest if multiple JSONs
                workflow_path = max(workflow_files, key=lambda f: f.stat().st_size)

            # Skip empty/corrupt files
            if readme_path.stat().st_size < 10 or workflow_path.stat().st_size < 10:
                skipped += 1
                continue

            # ── Read files ──────────────────────────────────────────────────
            readme_text   = readme_path.read_text(encoding="utf-8", errors="ignore").strip()
            workflow_json = json.loads(workflow_path.read_text(encoding="utf-8"))
            meta_json     = json.loads(meta_path.read_text(encoding="utf-8"))

            # ── Parse ───────────────────────────────────────────────────────
            folder_name          = folder.name.strip()
            id_match             = re.search(r"-(\d+)$", folder_name)
            workflow_id          = id_match.group(1) if id_match else folder_name
            instruction, context = parse_readme(readme_text, folder_name)
            services, node_count, difficulty = get_node_info(workflow_json)

            record = {
                "id":          workflow_id,
                "instruction": instruction,
                "context":     context,
                "output":      workflow_json,
                "meta": {
                    "folder_name": folder_name,
                    "tags":        meta_json.get("tags", []),
                    "created_at":  meta_json.get("createdAt", ""),
                    "author":      meta_json.get("user_username", ""),
                    "source_url":  meta_json.get("url", ""),
                    "services":    services,
                    "node_count":  node_count,
                    "difficulty":  difficulty,
                }
            }

            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1

            if written % 500 == 0:
                print(f"  ✅ {written} workflows written...")

        except Exception as e:
            skipped += 1
            continue

print(f"\n🎉 Done!")
print(f"  ✅ Written : {written} records → {OUTPUT_FILE}")
print(f"  ⚠️  Skipped : {skipped} folders")

easy = medium = complex_ = 0
with open(OUTPUT_FILE, encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)["meta"]["difficulty"]
        if d == "easy":     easy += 1
        elif d == "medium": medium += 1
        else:               complex_ += 1

print(f"\n📊 Dataset breakdown:")
print(f"  Easy    (≤3 nodes)  : {easy}")
print(f"  Medium  (4-7 nodes) : {medium}")
print(f"  Complex (8+ nodes)  : {complex_}")
