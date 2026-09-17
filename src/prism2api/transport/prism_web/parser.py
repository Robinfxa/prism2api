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
        """Parse response from /api/llm/response_with_tools_status.

        RunCompleted is emitted ONLY when:
        1. root status == "completed"
        2. response.status == "success"
        3. output payload structure is valid and interpretable.

        RunFailed is emitted ONLY from explicit upstream remote failure evidence.
        """
        events = []
        root_status = str(response_json.get("status", "")).lower()
        res_obj = response_json.get("response")

        # Explicit remote failure in nested response
        if isinstance(res_obj, dict) and res_obj.get("status") == "error":
            err_msg = (
                res_obj.get("payload", {}).get("message")
                or res_obj.get("payload", {}).get("reason")
                or "Upstream execution error"
            )
            return [{
                "type": "RunFailed",
                "payload": {"task_ref": task_ref, "error": err_msg}
            }]

        if root_status in ("failed", "error"):
            return [{
                "type": "RunFailed",
                "payload": {
                    "task_ref": task_ref,
                    "error": response_json.get("error", "Remote execution failed")
                }
            }]

        if root_status in ("cancelled", "canceled"):
            return [{
                "type": "CancellationConfirmed",
                "payload": {"task_ref": task_ref}
            }]

        # Strict completion check: root status completed AND response status success
        if root_status == "completed" and isinstance(res_obj, dict) and res_obj.get("status") == "success":
            res_payload = res_obj.get("payload", {})
            outputs = res_payload.get("output", [])
            extracted_text = ""
            saw_output_text_item = False

            if isinstance(outputs, list):
                for out in outputs:
                    if isinstance(out, dict):
                        contents = out.get("content", [])
                        if isinstance(contents, list):
                            for item in contents:
                                if isinstance(item, dict) and item.get("type") in ("output_text", "text") and "text" in item:
                                    saw_output_text_item = True
                                    extracted_text += str(item["text"])

            if not saw_output_text_item and "text" in response_json:
                extracted_text = str(response_json["text"])
                saw_output_text_item = True

            if saw_output_text_item:
                if extracted_text:
                    events.append({
                        "type": "TextDelta",
                        "payload": {"task_ref": task_ref, "text": extracted_text}
                    })
                events.append({
                    "type": "RunCompleted",
                    "payload": {
                        "task_ref": task_ref,
                        "finish_reason": "stop",
                        "text": extracted_text,
                    }
                })
                return events
            else:
                return [{
                    "type": "ProtocolUnknown",
                    "payload": {"task_ref": task_ref, "raw": response_json, "error": "Missing valid output text item in payload"}
                }]


        if root_status in ("pending", "in_progress", "running"):
            return events

        events.append({
            "type": "ProtocolUnknown",
            "payload": {"task_ref": task_ref, "raw": response_json}
        })
        return events

