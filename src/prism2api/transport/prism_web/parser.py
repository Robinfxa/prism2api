"""Parser mapping Grade A live wire payloads from prism.openai.com to canonical internal events."""

from typing import Dict, Any, List


class PrismWireParser:
    """Parses raw HTTP wire responses from Prism web endpoints."""

    @staticmethod
    def parse_start_response(response_json: Dict[str, Any], task_ref: str) -> List[Dict[str, Any]]:
        """Parse response from /api/llm/response_with_tools_start."""
        events = []
        if response_json.get("status") == "accepted" or "request_id" in response_json or "job_id" in response_json:
            events.append({
                "type": "SubmissionObserved",
                "payload": {"task_ref": task_ref, "status": "accepted"}
            })
        else:
            events.append({
                "type": "ProtocolUnknown",
                "payload": {"task_ref": task_ref, "raw": response_json}
            })
        return events

    @staticmethod
    def parse_status_response(response_json: Dict[str, Any], task_ref: str) -> List[Dict[str, Any]]:
        """Parse response from /api/llm/response_with_tools_status."""
        events = []
        status = response_json.get("status", "").lower()
        
        # Incremental text or snapshots
        if "text" in response_json:
            events.append({
                "type": "TextDelta",
                "payload": {"task_ref": task_ref, "text": response_json["text"]}
            })

        if status in ("completed", "finished", "success", "done"):
            events.append({
                "type": "RunCompleted",
                "payload": {
                    "task_ref": task_ref,
                    "finish_reason": response_json.get("finish_reason", "stop"),
                    "text": response_json.get("text", "")
                }
            })
        elif status in ("failed", "error"):
            events.append({
                "type": "RunFailed",
                "payload": {
                    "task_ref": task_ref,
                    "error": response_json.get("error", "Remote execution failed")
                }
            })
        elif status in ("cancelled", "canceled"):
            events.append({
                "type": "CancellationConfirmed",
                "payload": {"task_ref": task_ref}
            })
        elif not events:
            events.append({
                "type": "ProtocolUnknown",
                "payload": {"task_ref": task_ref, "raw": response_json}
            })
            
        return events
