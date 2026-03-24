# PURPOSE: Takes the simplified JSON that the fine-tuned model generates
#          and converts it into a full n8n-compatible workflow JSON.
#          This is then sent to the n8n API to auto-import the workflow.
#
# FLOW:
#   Model output (simplified JSON)
#        → post_processor.py
#        → full n8n JSON
#        → POST to localhost:5678/api/v1/workflows

import uuid
import json

# TYPE MAP — Converts simplified type labels back to full n8n type strings
# The model learned "gmail", "slack" etc. — n8n needs the full internal name

TYPE_MAP = {
    # Triggers
    "webhook":                "n8n-nodes-base.webhook",
    "scheduleTrigger":        "n8n-nodes-base.scheduleTrigger",
    "manualTrigger":          "n8n-nodes-base.manualTrigger",
    "googleSheetsTrigger":    "n8n-nodes-base.googleSheetsTrigger",
    "emailReadImap":          "n8n-nodes-base.emailReadImap",

    # Actions
    "httpRequest":            "n8n-nodes-base.httpRequest",
    "slack":                  "n8n-nodes-base.slack",
    "gmail":                  "n8n-nodes-base.gmail",
    "googleSheets":           "n8n-nodes-base.googleSheets",
    "discord":                "n8n-nodes-base.discord",
    "telegram":               "n8n-nodes-base.telegram",
    "airtable":               "n8n-nodes-base.airtable",
    "notion":                 "n8n-nodes-base.notion",
    "code":                   "n8n-nodes-base.code",
    "set":                    "n8n-nodes-base.set",
    "if":                     "n8n-nodes-base.if",
    "emailSend":              "n8n-nodes-base.emailSend",

    # LangChain / AI nodes
    "langchain.chainLlm":         "@n8n/n8n-nodes-langchain.chainLlm",
    "langchain.lmChatOpenAi":     "@n8n/n8n-nodes-langchain.lmChatOpenAi",
    "langchain.lmChatGoogleGemini":"@n8n/n8n-nodes-langchain.lmChatGoogleGemini",
    "langchain.toolCode":         "@n8n/n8n-nodes-langchain.toolCode",
    "langchain.agent":            "@n8n/n8n-nodes-langchain.agent",
    "langchain.outputParserStructured": "@n8n/n8n-nodes-langchain.outputParserStructured",
}

# TYPE VERSION MAP — Every n8n node has a version number
# If a node type is missing here, it defaults to 1

TYPE_VERSIONS = {
    "n8n-nodes-base.webhook":               2,
    "n8n-nodes-base.scheduleTrigger":       1,
    "n8n-nodes-base.manualTrigger":         1,
    "n8n-nodes-base.googleSheetsTrigger":   1,
    "n8n-nodes-base.httpRequest":           4,
    "n8n-nodes-base.slack":                 2,
    "n8n-nodes-base.gmail":                 2,
    "n8n-nodes-base.googleSheets":          4,
    "n8n-nodes-base.discord":               2,
    "n8n-nodes-base.telegram":              1,
    "n8n-nodes-base.airtable":              2,
    "n8n-nodes-base.notion":                2,
    "n8n-nodes-base.code":                  2,
    "n8n-nodes-base.set":                   3,
    "n8n-nodes-base.if":                    2,
    "n8n-nodes-base.emailSend":             2,
    "@n8n/n8n-nodes-langchain.chainLlm":    1,
    "@n8n/n8n-nodes-langchain.lmChatOpenAi":1,
    "@n8n/n8n-nodes-langchain.agent":       1,
}

# LAYOUT — Auto-positions nodes left to right on the n8n canvas
# n8n uses pixel coordinates [x, y] — we space them 250px apart horizontally

def calculate_positions(nodes: list) -> dict:
    """
    Returns a dict of { node_name: [x, y] }
    Simple left-to-right layout — good enough for MVP.
    All nodes sit on the same horizontal line (y=300).
    """
    positions = {}
    for i, node in enumerate(nodes):
        x = 250 + (i * 250)   # each node 250px to the right of the previous
        y = 300                # all on the same horizontal line
        positions[node["name"]] = [x, y]
    return positions

# CONNECTIONS — Converts flat edge list to n8n's nested connections format
#
# Your simplified format:
#   [{"from": "Trigger", "to": "Notify"}]
#
# n8n needs:
#   { "<trigger-uuid>": { "main": [[{"node": "<notify-uuid>", "type": "main", "index": 0}]] } }

def build_connections(edges: list, name_to_id: dict) -> dict:
    """
    edges       = simplified list of {from, to}
    name_to_id  = mapping of node name → generated UUID
    Returns the full n8n connections object
    """
    connections = {}

    for edge in edges:
        src_name = edge.get("from")
        dst_name = edge.get("to")

        # Skip if either end is missing (safety check)
        if src_name not in name_to_id or dst_name not in name_to_id:
            continue

        src_id = name_to_id[src_name]
        dst_id = name_to_id[dst_name]

        # n8n groups all outputs from a source node together
        if src_id not in connections:
            connections[src_id] = {"main": [[]]}  # main[0] = first output port

        connections[src_id]["main"][0].append({
            "node":  dst_id,
            "type":  "main",
            "index": 0
        })

    return connections

# MAIN FUNCTION — Called by FastAPI with the model's output

def build_n8n_workflow(simplified: dict) -> dict:
    """
    Takes the model's simplified JSON and returns a full n8n workflow JSON.

    simplified = {
        "name": "Webhook to Slack",
        "nodes": [
            {"name": "Trigger", "type": "webhook",  "parameters": {"httpMethod": "POST"}},
            {"name": "Notify",  "type": "slack",    "parameters": {"channel": "#general"}}
        ],
        "connections": [
            {"from": "Trigger", "to": "Notify"}
        ]
    }
    """

    raw_nodes   = simplified.get("nodes", [])
    raw_edges   = simplified.get("connections", [])
    workflow_name = simplified.get("name", "AutoFlow Workflow")

    # Step 1 — Generate a UUID for every node
    # We map node name → UUID so we can use it in connections later
    name_to_id = {
        node["name"]: str(uuid.uuid4())
        for node in raw_nodes
    }

    # Step 2 — Auto-calculate positions for each node on the canvas
    positions = calculate_positions(raw_nodes)

    # Step 3 — Build the full node list with all required n8n fields
    full_nodes = []
    for node in raw_nodes:
        name         = node["name"]
        simple_type  = node.get("type", "httpRequest")
        parameters   = node.get("parameters", {})

        # Expand simplified type → full n8n type string
        # If the type is unknown/unsupported, fall back to httpRequest
        full_type = TYPE_MAP.get(simple_type, "n8n-nodes-base.httpRequest")

        # Look up the correct typeVersion for this node
        type_version = TYPE_VERSIONS.get(full_type, 1)

        full_nodes.append({
            "id":          name_to_id[name],     # UUID generated in Step 1
            "name":        name,                  # human label, e.g. "Send Email"
            "type":        full_type,             # e.g. "n8n-nodes-base.gmail"
            "typeVersion": type_version,          # e.g. 2
            "position":    positions[name],       # e.g. [250, 300]
            "parameters":  parameters,            # the actual node config
        })

    # Step 4 — Convert simplified edge list → n8n connections object
    connections = build_connections(raw_edges, name_to_id)

    # Step 5 — Assemble the final n8n workflow payload
    n8n_workflow = {
        "name":        workflow_name,
        "nodes":       full_nodes,
        "connections": connections,
        "active":      False,     # workflow starts as inactive — user activates manually
        "settings":    {
            "executionOrder": "v1"
        },
        "tags": []
    }

    return n8n_workflow