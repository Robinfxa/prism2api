"""PrismHttpTransport: Production HTTP transport for prism.openai.com based on Grade A wire traces."""

import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx

from prism2api.provider.models import (
    CapabilitySnapshot,
    CapabilityId,
    EvidenceState,
    ActivationState,
    RemoteHandle,
)
from prism2api.transport.base import (
    BaseTransport,
    TransportSession,
    AuthProfile,
    AuthStatus,
)
from prism2api.transport.prism_web.parser import PrismWireParser
from prism2api.transport.prism_web.protocol import PrismStartRequest, PrismStartMetadata, PrismMessage, PrismMessageContent
from prism2api.errors import AdmissionBlockedError, ProtocolError


class PrismHttpTransport(BaseTransport):
    """Production HTTP transport communicating directly with prism.openai.com endpoints."""

    kind = "prism_http"
    handle_scoped_events = True

    def __init__(self, auth_profile: Optional[AuthProfile] = None, base_url: str = "https://prism.openai.com"):
        self.base_url = base_url.rstrip("/")
        self._auth_profile = auth_profile or AuthProfile(
            profile_id="prism_http_default",
            account_scope="prism_web_account",
            auth_status=AuthStatus.NOT_CONFIGURED,
        )
        self.parser = PrismWireParser()
        self.cookie_header: Optional[str] = None
        self._load_credentials()

    def _load_credentials(self) -> None:
        """Locate credentials from credential_locator, environment, or $HOME/.prism2api/credentials.json."""
        locator_path = None
        if self._auth_profile.credential_locator:
            locator_path = Path(self._auth_profile.credential_locator)
        else:
            default_path = Path.home() / ".prism2api" / "credentials.json"
            if default_path.exists():
                locator_path = default_path

        if locator_path and locator_path.exists():
            try:
                with open(locator_path, "r", encoding="utf-8") as f:
                    cred_data = json.load(f)
                    self.cookie_header = cred_data.get("cookie")
                    if self.cookie_header:
                        self._auth_profile.auth_status = AuthStatus.READY
            except Exception:
                pass

        if not self.cookie_header:
            env_cookie = os.getenv("PRISM_COOKIE") or os.getenv("PRISM_SESSION_COOKIE")
            if env_cookie:
                self.cookie_header = env_cookie
                self._auth_profile.auth_status = AuthStatus.READY

    @property
    def auth_profile(self) -> AuthProfile:
        return self._auth_profile

    def inspect_capabilities(self, session: TransportSession) -> List[CapabilitySnapshot]:
        """Inspect capabilities.
        
        TEXT_GENERATION is EvidenceState.VERIFIED.
        ActivationState is ENABLED if auth_profile status is READY and cookie is present, else DISABLED.
        
        All other capabilities remain EvidenceState.UNKNOWN and ActivationState.DISABLED.
        """
        is_ready = self._auth_profile.auth_status == AuthStatus.READY and bool(self.cookie_header)
        text_gen_activation = ActivationState.ENABLED if is_ready else ActivationState.DISABLED

        caps = [
            CapabilitySnapshot(
                capability_id=CapabilityId.TEXT_GENERATION,
                evidence_state=EvidenceState.VERIFIED,
                activation_state=text_gen_activation,
                account_scope=self._auth_profile.account_scope,
                evidence_refs=["Grade_A_live_network_trace"],
                tested_at="2026-09-17T00:09:35Z",
                review_due_at="2026-10-17T00:09:35Z",
            ),
        ]
        
        other_ids = [
            CapabilityId.ISOLATED_CONTEXT,
            CapabilityId.TASK_LOOKUP,
            CapabilityId.DELTA_STREAM,
            CapabilityId.CANCEL_CONFIRMATION,
            CapabilityId.MODEL_SELECTION,
            CapabilityId.USAGE_REPORTING,
        ]
        for cap_id in other_ids:
            caps.append(
                CapabilitySnapshot(
                    capability_id=cap_id,
                    evidence_state=EvidenceState.UNKNOWN,
                    activation_state=ActivationState.DISABLED,
                    account_scope=self._auth_profile.account_scope,
                )
            )
        return caps

    def prepare_context(self, session: TransportSession, context: Any, operation_id: str) -> RemoteHandle:
        """Prepare context workspace binding without synthetic identity fallback."""
        if isinstance(context, dict):
            workspace_ref = context.get("workspace_ref") or context.get("project_id")
            conversation_ref = context.get("conversation_ref") or context.get("conversation_id")
        else:
            workspace_ref = getattr(context, "workspace_ref", None) or getattr(context, "project_id", None)
            conversation_ref = getattr(context, "conversation_ref", None) or getattr(context, "conversation_id", None)

        if not workspace_ref or not conversation_ref:
            raise AdmissionBlockedError("Missing required context identity (workspace_ref/project_id or conversation_ref/conversation_id)")

        return RemoteHandle(
            workspace_ref=workspace_ref,
            conversation_ref=conversation_ref,
            task_ref=f"task_{operation_id}",
        )

    def submit(
        self,
        run_id: str,
        attempt_id: str,
        session: TransportSession,
        input_text: str,
        model_alias: str,
    ) -> RemoteHandle:
        """Submit generation request exactly ONCE to prism.openai.com.

        NEVER re-post or retry on network errors.
        Fails closed on missing context or missing remote receipts.
        """
        if self._auth_profile.auth_status != AuthStatus.READY or not self.cookie_header:
            raise AdmissionBlockedError("PrismHttpTransport: Auth profile is not ready or missing cookie")

        timeout_sec = session.io_timeout_seconds or 30.0
        if session.deadline_monotonic:
            remaining = session.deadline_monotonic - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Session deadline exceeded before submit")
            timeout_sec = min(timeout_sec, remaining)

        project_id = session.context_binding.get("workspace_ref") or session.context_binding.get("project_id")
        conversation_id = session.context_binding.get("conversation_ref") or session.context_binding.get("conversation_id")
        user_id = session.context_binding.get("user_id")

        if not project_id or not conversation_id or not user_id:
            raise AdmissionBlockedError("Missing required live context identity (workspace_ref/project_id, conversation_ref/conversation_id, or user_id)")

        sb_url = session.context_binding.get("sandbox_url")
        sb_token = session.context_binding.get("sandbox_token")
        if not sb_url or not sb_token:
            raise AdmissionBlockedError("Missing required live context sandbox material (sandbox_url or sandbox_token)")

        url = f"{self.base_url}/api/llm/response_with_tools_start"
        headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "cookie": self.cookie_header,
            "origin": self.base_url,
            "referer": f"{self.base_url}/",
            "user-agent": "prism2api-client/0.1.1",
        }

        meta = {
            "projectId": project_id,
            "userId": user_id,
            "model": "gpt-6-astra",
            "reasoning_effort": "medium",
            "frontend_origin": self.base_url,
            "sandbox_url": sb_url,
            "sandbox_token": sb_token,
        }

        payload = {
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": input_text}],
                }
            ],
            "metadata": meta,
            "conversationId": conversation_id,
        }

        try:
            with httpx.Client(timeout=timeout_sec) as client:
                response = client.post(url, headers=headers, json=payload)
                if response.status_code != 200:
                    raise ProtocolError(f"HTTP submit failed with status {response.status_code}: {response.text}")
                res_data = response.json()
        except httpx.RequestError as exc:
            raise ProtocolError(f"Network error during submit: {str(exc)}") from exc
        except ValueError as exc:
            raise ProtocolError(f"Malformed submit JSON response: {str(exc)}") from exc

        task_id = res_data.get("request_id") or res_data.get("async_job_id") or res_data.get("job_id")
        turn_state = res_data.get("turn_state")

        if not task_id or not turn_state:
            raise ProtocolError("Submit response missing required remote receipt (request_id/async_job_id or turn_state)")

        raw_meta = {
            "endpoint": "/api/llm/response_with_tools_start",
            "http_status": response.status_code,
            "turn_state": turn_state,
        }
        if res_data.get("status") == "completed":
            raw_meta["initial_response"] = res_data

        return RemoteHandle(
            workspace_ref=project_id,
            conversation_ref=conversation_id,
            task_ref=task_id,
            message_ref=f"msg_{attempt_id}",
            server_event_cursor="seq_0",
            raw_metadata=raw_meta,
        )

    def observe_events(self, handle: RemoteHandle) -> List[Dict[str, Any]]:
        """Read-only observation calling /api/llm/response_with_tools_status.

        Enforces strict identity validation and raises ProtocolError on network/HTTP errors.
        """
        if not self.cookie_header:
            raise AdmissionBlockedError("PrismHttpTransport: Auth cookie missing for event observation")

        turn_state = (handle.raw_metadata or {}).get("turn_state")
        if not turn_state or not isinstance(turn_state, dict):
            raise ProtocolError("Missing valid turn_state in RemoteHandle for status observation")

        # If submit response was already completed inline
        if handle.raw_metadata and "initial_response" in handle.raw_metadata:
            res_data = handle.raw_metadata["initial_response"]
            self._validate_status_identity(res_data, handle, turn_state)
            return self.parser.parse_status_response(
                res_data,
                task_ref=handle.task_ref or "unknown"
            )

        url = f"{self.base_url}/api/llm/response_with_tools_status"
        headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "cookie": self.cookie_header,
            "origin": self.base_url,
            "referer": f"{self.base_url}/?u={handle.workspace_ref}&pg=1&m=main.tex",
            "user-agent": "prism2api-client/0.1.1",
        }

        payload = {
            "request_id": handle.task_ref,
            "turn_state": turn_state,
        }

        start_time = time.monotonic()
        timeout = 45.0
        while time.monotonic() - start_time < timeout:
            try:
                with httpx.Client(timeout=30.0) as client:
                    response = client.post(url, headers=headers, json=payload)
                    if response.status_code != 200:
                        raise ProtocolError(f"HTTP status endpoint returned code {response.status_code}")
                    try:
                        res_data = response.json()
                    except ValueError as exc:
                        raise ProtocolError(f"Malformed status JSON response: {str(exc)}") from exc

                    self._validate_status_identity(res_data, handle, turn_state)

                    parsed = self.parser.parse_status_response(res_data, task_ref=handle.task_ref or "unknown")
                    if any(e.get("type") in ("RunCompleted", "RunFailed", "CancellationConfirmed") for e in parsed):
                        return parsed
                    
                    time.sleep(1.0)
            except httpx.RequestError as exc:
                raise ProtocolError(f"Network error during status observation: {str(exc)}") from exc

        raise ProtocolError("Status observation timed out without terminal state")

    def _validate_status_identity(self, res_data: Dict[str, Any], handle: RemoteHandle, turn_state: Dict[str, Any]) -> None:
        """Strictly validate identity parameters in status response."""
        res_req_id = res_data.get("request_id")
        if res_req_id and handle.task_ref and res_req_id != handle.task_ref:
            raise ProtocolError(f"Identity mismatch in status response: request_id '{res_req_id}' != expected '{handle.task_ref}'")

        expected_async_job_id = turn_state.get("async_job_id")
        res_async_job_id = res_data.get("codex_async_job_id") or res_data.get("async_job_id")
        if res_async_job_id and expected_async_job_id and res_async_job_id != expected_async_job_id:
            raise ProtocolError(f"Identity mismatch in status response: codex_async_job_id '{res_async_job_id}' != expected '{expected_async_job_id}'")

        res_conv_id = res_data.get("conversationId") or res_data.get("conversation_id")
        if res_conv_id and handle.conversation_ref and res_conv_id != handle.conversation_ref:
            raise ProtocolError(f"Identity mismatch in status response: conversationId '{res_conv_id}' != expected '{handle.conversation_ref}'")

    def lookup_events(self, session: TransportSession, handle: RemoteHandle) -> Dict[str, Any]:
        """Read-only lookup for task status on prism.openai.com."""
        events = self.observe_events(handle)
        return {"task_ref": handle.task_ref, "events": events}

    def request_cancel(self, handle: RemoteHandle) -> bool:
        """Cancellation endpoint unverified on wire. Returns False without remote cancel receipt."""
        return False

    def close(self) -> None:
        """Close transport resources."""
        pass


def create_prism_http_transport(auth_profile: Optional[AuthProfile] = None, settings: Optional[Any] = None) -> PrismHttpTransport:
    """Factory function for PrismHttpTransport."""
    return PrismHttpTransport(auth_profile=auth_profile)

