"""FastAPI backend that bridges the extension and local n8n instance.

The endpoint accepts a natural language prompt, builds a simplified workflow,
converts it to n8n JSON, and imports it into n8n.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ai_service.post_processor import build_n8n_workflow


# Load .env from project root so local API keys are available at runtime.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


# Use env vars so local URLs/keys can be changed without code edits.
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678")
N8N_API_KEY = os.getenv("N8N_API_KEY", "")


class GenerateRequest(BaseModel):
	"""Input payload sent by the browser extension."""

	prompt: str = Field(min_length=1, max_length=2000)
	workflow_id: str | None = None


def mock_generate_simplified(prompt: str) -> dict[str, Any]:
	"""Return a tiny deterministic workflow until model inference is plugged in."""

	# Keep this deterministic so frontend/backend integration is easy to verify.
	return {
		"name": f"AutoFlow - {prompt[:40]}",
		"nodes": [
			{
				"name": "Manual Trigger",
				"type": "manualTrigger",
				"parameters": {},
			},
			{
				"name": "HTTP Request",
				"type": "httpRequest",
				"parameters": {
					"url": "https://httpbin.org/post",
					"method": "POST",
				},
			},
		],
		"connections": [
			{"from": "Manual Trigger", "to": "HTTP Request"},
		],
	}


def import_workflow_to_n8n(
	workflow: dict[str, Any],
	workflow_id: str | None = None,
) -> dict[str, Any]:
	"""Create or update a workflow in n8n and return n8n's response body."""

	base_url = N8N_BASE_URL.rstrip('/')
	url = f"{base_url}/api/v1/workflows"
	method = "POST"
	if workflow_id:
		# Reuse the same workflow when caller already has an existing workflow id.
		url = f"{base_url}/api/v1/workflows/{workflow_id}"
		method = "PUT"
	headers = {"Content-Type": "application/json"}

	# n8n create-workflow endpoint rejects read-only properties on newer versions.
	# Send only fields accepted by create API to avoid version-specific schema rejections.
	workflow_to_create = {
		"name": workflow.get("name", "AutoFlow Workflow"),
		"nodes": workflow.get("nodes", []),
		"connections": workflow.get("connections", {}),
		"settings": workflow.get("settings", {}),
	}

	# Add API key only when configured, so default local setup still works.
	if N8N_API_KEY:
		headers["X-N8N-API-KEY"] = N8N_API_KEY

	request_body = json.dumps(workflow_to_create).encode("utf-8")
	request = urllib.request.Request(
		url=url,
		data=request_body,
		headers=headers,
		method=method,
	)

	try:
		with urllib.request.urlopen(request, timeout=20) as response:
			status_code = response.status
			body_text = response.read().decode("utf-8")
	except urllib.error.HTTPError as exc:
		# If update target does not exist anymore, fall back to create flow.
		if method == "PUT" and exc.code == 404:
			return import_workflow_to_n8n(workflow=workflow, workflow_id=None)

		error_text = exc.read().decode("utf-8", errors="replace")
		raise HTTPException(
			status_code=502,
			detail={
				"message": "n8n rejected workflow import",
				"status_code": exc.code,
				"body": error_text,
			},
		) from exc
	except urllib.error.URLError as exc:
		raise HTTPException(
			status_code=502,
			detail=f"Unable to reach n8n at {N8N_BASE_URL}: {exc}",
		) from exc

	try:
		return json.loads(body_text)
	except ValueError:
		# Some n8n responses can be plain text; preserve that body for debugging.
		return {"raw": body_text, "status_code": status_code}


app = FastAPI(title="AutoFlow Backend", version="0.1.0")

# Allow extension/page requests during local development.
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
	"""Basic health endpoint for quick connectivity checks."""

	return {"status": "ok"}


@app.post("/generate")
def generate(payload: GenerateRequest) -> dict[str, Any]:
	"""Generate and import a workflow based on the user's prompt."""

	simplified = mock_generate_simplified(payload.prompt)
	n8n_workflow = build_n8n_workflow(simplified)
	n8n_response = import_workflow_to_n8n(
		workflow=n8n_workflow,
		workflow_id=payload.workflow_id,
	)

	return {
		"message": "Workflow generated and sent to n8n",
		"workflow_name": n8n_workflow.get("name", ""),
		"n8n": n8n_response,
	}
