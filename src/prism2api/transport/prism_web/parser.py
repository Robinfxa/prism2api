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
        
        extracted_text = ""
        res_payload = response_json.get("response", {}).get("payload", {})
        outputs = res_payload.get("output", [])
        if outputs and isinstance(outputs, list):
            for out in outputs:
                contents = out.get("content", [])
                for item in contents:
                    if item.get("type") in ("output_text", "text") and "text" in item:
                        extracted_text += item["text"]
                        
        if not extracted_text and "text" in response_json:
            extracted_text = response_json["text"]

        if extracted_text:
            events.append({
                "type": "TextDelta",
                "payload": {"task_ref": task_ref, "text": extracted_text}
            })

        res_obj = response_json.get("response", {})
        if isinstance(res_obj, dict) and res_obj.get("status") == "error":
            err_msg = res_obj.get("payload", {}).get("message") or res_obj.get("payload", {}).get("reason") or "Upstream error"
            events.append({
                "type": "RunFailed",
                "payload": {"task_ref": task_ref, "error": err_msg}
            })
            return events

        if status in ("completed", "finished", "success", "done"):
            finish_reason = "stop"
            events.append({
                "type": "RunCompleted",
                "payload": {
                    "task_ref": task_ref,
                    "finish_reason": finish_reason,
                    "text": extracted_text
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
        elif not events and status != "pending":
            events.append({
                "type": "ProtocolUnknown",
                "payload": {"task_ref": task_ref, "raw": response_json}
            })
            
        return events
