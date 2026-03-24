"""Manual integration test for AutoFlow workflow import.

This file is intentionally isolated under testing/ so production flow files stay unchanged.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Ensure imports work when running this file directly via `python testing/connection_test.py`.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

from ai_service.post_processor import build_n8n_workflow
from n8n_connection.server import import_workflow_to_n8n


def mock_model_output(user_prompt: str) -> dict[str, Any]:
	"""Return one pre-made simplified workflow regardless of prompt content.

	We keep this deterministic so the test validates integration, not model quality.
	"""

	return {
		"name": f"AutoFlow Test - {user_prompt[:35]}",
		"nodes": [
			{
				"name": "Manual Trigger",
				"type": "manualTrigger",
				"parameters": {},
			},
			{
				"name": "Prepare Payload",
				"type": "set",
				"parameters": {
					"assignments": {
						"assignments": [
							{
								"id": "test-message",
								"name": "message",
								"type": "string",
								"value": "Hello from AutoFlow connection test",
							}
						]
					}
				},
			},
			{
				"name": "Send Request",
				"type": "httpRequest",
				"parameters": {
					"url": "https://httpbin.org/post",
					"method": "POST",
				},
			},
		],
		"connections": [
			{"from": "Manual Trigger", "to": "Prepare Payload"},
			{"from": "Prepare Payload", "to": "Send Request"},
		],
	}


def process_prompt(user_prompt: str) -> dict[str, Any]:
	"""Process a prompt through mock-model -> post-processor -> n8n import."""

	# Step 1: Simulate model output with a fixed simplified JSON workflow.
	simplified = mock_model_output(user_prompt)

	# Step 2: Use the real post-processor to build n8n-compatible JSON.
	workflow_payload = build_n8n_workflow(simplified)

	# Step 3: Use the same import helper used by the FastAPI backend.
	n8n_response = import_workflow_to_n8n(workflow_payload)

	return {
		"message": "Workflow generated and sent to n8n via test harness",
		"workflow_name": workflow_payload.get("name", ""),
		"workflow_payload": workflow_payload,
		"n8n": n8n_response,
	}


def run_connection_test() -> None:
	"""Run one manual test from terminal input."""

	user_prompt = input("Type your workflow request: ").strip()
	if not user_prompt:
		print("Prompt cannot be empty.")
		return

	try:
		result = process_prompt(user_prompt)
	except Exception as exc:  # noqa: BLE001 - keep broad for a simple test harness.
		print("\nImport failed. Check n8n/backend status and API key settings.")
		print(f"Error: {exc}")
		return

	print("\nBuilt n8n workflow payload:")
	print(json.dumps(result["workflow_payload"], indent=2))

	print("\nImport succeeded. n8n response:")
	print(json.dumps(result["n8n"], indent=2, ensure_ascii=True))


class GenerateRequest(BaseModel):
	"""Request schema used by the test backend endpoint."""

	prompt: str = Field(min_length=1, max_length=2000)


def create_test_app() -> FastAPI:
	"""Create a small test backend compatible with the extension fetch call."""

	app = FastAPI(title="AutoFlow Test Backend", version="0.1.0-test")

	@app.get("/health")
	def health() -> dict[str, str]:
		return {"status": "ok", "mode": "test"}

	@app.post("/generate")
	def generate(payload: GenerateRequest) -> dict[str, Any]:
		try:
			result = process_prompt(payload.prompt)
		except Exception as exc:  # noqa: BLE001 - keep broad for integration troubleshooting.
			raise HTTPException(status_code=502, detail=str(exc)) from exc

		# Hide full payload from extension response while keeping workflow metadata.
		return {
			"message": result["message"],
			"workflow_name": result["workflow_name"],
			"n8n": result["n8n"],
		}

	return app


def run_test_server(host: str, port: int) -> None:
	"""Run an always-on test server so extension input can trigger workflow imports."""

	import uvicorn

	uvicorn.run(create_test_app(), host=host, port=port)


def parse_args() -> argparse.Namespace:
	"""Parse CLI flags for one-shot mode vs always-on server mode."""

	parser = argparse.ArgumentParser(description="AutoFlow connection test harness")
	parser.add_argument(
		"--serve",
		action="store_true",
		help="Run as a live mock backend endpoint for extension testing",
	)
	parser.add_argument("--host", default="127.0.0.1", help="Host for --serve mode")
	parser.add_argument("--port", type=int, default=8000, help="Port for --serve mode")
	return parser.parse_args()


if __name__ == "__main__":
	args = parse_args()
	if args.serve:
		run_test_server(args.host, args.port)
	else:
		run_connection_test()
