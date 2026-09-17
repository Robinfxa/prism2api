"""PrismBrowserTransport: Single-session browser-assisted transport for Prism2API v0.1 MVP."""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from prism2api.errors import AdmissionBlockedError, ProtocolError
from prism2api.transport.prism_web.live_profile import PrismLiveProfile

logger = logging.getLogger(__name__)


class PrismBrowserTransport:
    """Browser-assisted transport for executing Prism generation requests inside a Playwright page context.

    Enforces concurrency = 1 via an internal asyncio.Lock.
    """

    def __init__(
        self,
        project_id: str,
        conversation_id: str,
        profile_path: Optional[Path] = None,
        headless: bool = True,
        browser_channel: str = "msedge",
        user_data_dir: Optional[str] = None,
    ):
        self.project_id = project_id
        self.conversation_id = conversation_id
        self.profile_path = profile_path
        self.headless = headless
        self.browser_channel = browser_channel
        self.user_data_dir = user_data_dir or "/tmp/prism2api_browser_profile"

        self._playwright = None
        self._browser_context = None
        self._page = None
        self._live_profile = None
        self._lock = asyncio.Lock()  # Serialized execution
        self._is_ready = False

    @property
    def is_ready(self) -> bool:
        """Return True if browser runtime is initialized and ready for requests."""
        return self._is_ready and self._page is not None and not self._page.is_closed()

    async def initialize(self) -> None:
        """Launch Playwright browser context, load live profile session cookies, and navigate to Prism."""
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise AdmissionBlockedError("Playwright is not installed. Please install playwright to run serve-browser.") from exc

        live_profile = PrismLiveProfile.load(self.profile_path)
        cookies_list = []
        if live_profile.cookie_header:
            for item in live_profile.cookie_header.split(";"):
                item = item.strip()
                if "=" in item:
                    k, v = item.split("=", 1)
                    k_str = k.strip()
                    v_str = v.strip()
                    cookies_list.append({
                        "name": k_str,
                        "value": v_str,
                        "domain": ".openai.com",
                        "path": "/",
                    })
                    cookies_list.append({
                        "name": k_str,
                        "value": v_str,
                        "domain": "prism.openai.com",
                        "path": "/",
                    })

        self._playwright = await async_playwright().start()

        launch_kwargs: Dict[str, Any] = {
            "headless": self.headless,
        }
        if self.browser_channel:
            launch_kwargs["channel"] = self.browser_channel

        try:
            self._browser_context = await self._playwright.chromium.launch_persistent_context(
                self.user_data_dir,
                **launch_kwargs,
            )
        except Exception:
            # Fallback to default chromium channel if specified channel fails
            if "channel" in launch_kwargs:
                del launch_kwargs["channel"]
            self._browser_context = await self._playwright.chromium.launch_persistent_context(
                self.user_data_dir,
                **launch_kwargs,
            )

        if cookies_list:
            await self._browser_context.add_cookies(cookies_list)

        self._page = await self._browser_context.new_page()

        target_url = f"https://prism.openai.com/c/{self.conversation_id}?u={self.project_id}"
        logger.info("Navigating Prism Browser Transport to %s", target_url)
        await self._page.goto(target_url)

        self._live_profile = live_profile
        self._is_ready = True
        logger.info("Prism Browser Transport initialization complete.")

    async def submit_and_poll(self, prompt: str, timeout: float = 60.0) -> str:
        """Submit a user prompt via page.evaluate fetch and poll status until completion.

        Enforces concurrency = 1 via lock.
        """
        if not self.is_ready:
            raise AdmissionBlockedError("Prism Browser Transport is not ready or browser page is closed.")

        async with self._lock:
            meta_obj = {
                "projectId": self.project_id,
                "userId": self._live_profile.user_id if self._live_profile else "",
                "model": "gpt-6-astra",
                "reasoning_effort": "medium",
                "frontend_origin": "https://prism.openai.com",
                "sandbox_url": self._live_profile.sandbox_url if self._live_profile else "",
                "sandbox_token": self._live_profile.sandbox_token if self._live_profile else "",
            }

            # Helper JS function for start call
            start_eval_js = """
                async ({ projectId, conversationId, promptText, metaObj }) => {
                    try {
                        const resp = await fetch("/api/llm/response_with_tools_start", {
                            method: "POST",
                            headers: {
                                "content-type": "application/json"
                            },
                            credentials: "include",
                            body: JSON.stringify({
                                conversationId: conversationId,
                                input: [
                                    {
                                        type: "message",
                                        role: "user",
                                        content: [{ type: "input_text", text: promptText }]
                                    }
                                ],
                                metadata: metaObj
                            })
                        });
                        if (!resp.ok) {
                            const text = await resp.text();
                            return { error: `HTTP ${resp.status}: ${text}` };
                        }
                        const data = await resp.json();
                        return { data };
                    } catch (e) {
                        return { error: e.toString() };
                    }
                }
            """

            # Step 1: Trigger response_with_tools_start inside page context
            start_result = await self._page.evaluate(start_eval_js, {
                "projectId": self.project_id,
                "conversationId": self.conversation_id,
                "promptText": prompt,
                "metaObj": meta_obj
            })

            data = start_result.get("data", {}) if start_result else {}
            resp_obj = data.get("response", {}) if isinstance(data, dict) else {}
            payload_obj = resp_obj.get("payload", {}) if isinstance(resp_obj, dict) else {}

            # If sandbox is reconnecting, provision fresh sandbox credentials from /api/backend/1/new and retry once
            if payload_obj.get("reason") in ("sandbox_reconnecting", "unknown"):
                logger.info("Sandbox reconnecting detected. Provisioning fresh sandbox credentials via /api/backend/1/new...")
                sb_result = await self._page.evaluate("""
                    async ({ projectId }) => {
                        try {
                            const resp = await fetch("/api/backend/1/new", {
                                method: "POST",
                                headers: { "content-type": "application/json" },
                                credentials: "include",
                                body: JSON.stringify({ projectId })
                            });
                            return await resp.json();
                        } catch (e) {
                            return null;
                        }
                    }
                """, {"projectId": self.project_id})

                if sb_result and isinstance(sb_result, dict):
                    fresh_url = sb_result.get("url")
                    fresh_token = sb_result.get("token")
                    if fresh_url and fresh_token:
                        meta_obj["sandbox_url"] = fresh_url
                        meta_obj["sandbox_token"] = fresh_token
                        logger.info("Retrying start request with fresh sandbox token...")
                        start_result = await self._page.evaluate(start_eval_js, {
                            "projectId": self.project_id,
                            "conversationId": self.conversation_id,
                            "promptText": prompt,
                            "metaObj": meta_obj
                        })

            if not start_result or "error" in start_result:
                err_msg = start_result.get("error", "Unknown error") if start_result else "No response from evaluate"
                raise ProtocolError(f"Prism upstream start failed: {err_msg}")

            data = start_result.get("data", {})
            request_id = data.get("request_id")
            turn_state = data.get("turn_state")

            if not request_id or not turn_state:
                raise ProtocolError(
                    f"Prism start payload missing required request_id or turn_state (got request_id={request_id})"
                )

            # Step 2: Poll response_with_tools_status until completed
            start_time = time.time()
            while time.time() - start_time < timeout:
                status_result = await self._page.evaluate("""
                    async ({ requestId, turnState }) => {
                        try {
                            const resp = await fetch("/api/llm/response_with_tools_status", {
                                method: "POST",
                                headers: {
                                    "content-type": "application/json"
                                },
                                credentials: "include",
                                body: JSON.stringify({
                                    request_id: requestId,
                                    turn_state: turnState
                                })
                            });
                            if (!resp.ok) {
                                const text = await resp.text();
                                return { error: `HTTP ${resp.status}: ${text}` };
                            }
                            const data = await resp.json();
                            return { data };
                        } catch (e) {
                            return { error: e.toString() };
                        }
                    }
                """, {
                    "requestId": request_id,
                    "turnState": turn_state
                })

                if not status_result or "error" in status_result:
                    err_msg = status_result.get("error", "Unknown status error") if status_result else "Empty status response"
                    raise ProtocolError(f"Prism upstream status poll failed: {err_msg}")

                st_data = status_result.get("data", {})
                root_status = st_data.get("status")
                resp_obj = st_data.get("response", {})
                resp_status = resp_obj.get("status")

                if root_status == "completed" and resp_status == "success":
                    payload = resp_obj.get("payload", {})
                    output_items = payload.get("output", [])
                    extracted_texts: List[str] = []
                    found_output_text = False

                    for out_item in output_items:
                        content_list = out_item.get("content", [])
                        for c in content_list:
                            if isinstance(c, dict) and c.get("type") == "output_text":
                                found_output_text = True
                                txt = c.get("text", "")
                                extracted_texts.append(txt)

                    if not found_output_text:
                        raise ProtocolError("No output_text content item found in Prism status payload")

                    return "\n".join(extracted_texts)

                if root_status == "failed" or resp_status == "error":
                    raise ProtocolError(f"Prism upstream generation failed: {st_data}")

                await asyncio.sleep(1.0)

            raise TimeoutError(f"Prism generation timed out after {timeout} seconds (request_id={request_id})")

    async def close(self) -> None:
        """Shutdown browser context and Playwright instance."""
        self._is_ready = False
        if self._browser_context:
            try:
                await self._browser_context.close()
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
        logger.info("Prism Browser Transport closed.")
