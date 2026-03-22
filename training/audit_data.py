"""
Usage:
    uv run training/audit_data.py           # checks all records
    uv run training/audit_data.py --sample 20   # checks first 20 records
"""
import json
import re
import sys

CLEAN_FILE = "training/data/n8n_dataset_clean.jsonl"

# ── How many records to inspect (default = all)
SAMPLE = None
if "--sample" in sys.argv:
    idx = sys.argv.index("--sample")
    SAMPLE = int(sys.argv[idx + 1])

def _clean_groq_output(raw: str) -> str:
    text = raw.strip()
    if re.match(r'^(Here|Context:|Note:)', text, re.IGNORECASE):
        parts = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
        text = parts[-1] if parts else text
    if re.match(r'^\d+\.', text):
        text = re.split(r'\n\d+\.', text)[0]
        text = re.sub(r'^\d+\.\s*', '', text).strip()
    text = re.sub(r'^(→|->)\s*', '', text).strip()
    text = text.strip('"\'')
    return text.strip()

with open(CLEAN_FILE, encoding="utf-8") as f:
    lines = [l for l in f.readlines() if l.strip()]

total_in_file = len(lines)
if SAMPLE:
    lines = lines[:SAMPLE]

print(f"Total in file  : {total_in_file}")
print(f"Checking       : {len(lines)} records")
print()

fixed = 0
records = []
preamble_left = 0

for line in lines:
    r = json.loads(line)
    original = r["instruction"]
    cleaned  = _clean_groq_output(original)
    if cleaned != original:
        r["instruction"] = cleaned
        fixed += 1
    # Check if any preamble survived cleaning
    if re.match(r'^(Here|Context:|Title)', r["instruction"], re.IGNORECASE):
        preamble_left += 1
    records.append(r)

# ── Write fixes back only if checking full file
if SAMPLE is None:
    with open(CLEAN_FILE, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Fixed instructions : {fixed} / {len(records)} (written back)")
else:
    print(f"Fixed instructions : {fixed} / {len(records)} (dry run — sample mode, not written)")

print(f"Preamble remaining : {preamble_left}")
print()

# ── Stats on output structure
no_conn = sum(1 for r in records if len(r["output"]["connections"]) == 0 and len(r["output"]["nodes"]) > 1)
empty_params = sum(1 for r in records if r["output"]["nodes"] and all(len(n["parameters"]) == 0 for n in r["output"]["nodes"]))
dup_names = sum(1 for r in records if len([n["name"] for n in r["output"]["nodes"]]) != len(set(n["name"] for n in r["output"]["nodes"])))

print(f"=== Output structure ({len(records)} records) ===")
print(f"  No connections (>1 node) : {no_conn}")
print(f"  All empty params         : {empty_params}")
print(f"  Duplicate node names     : {dup_names}")
print()

# ── Print sample instructions so you can visually verify
print(f"=== Instruction samples (first {min(30, len(records))}) ===")
for r in records[:30]:
    print(" ", repr(r["instruction"][:120]))

