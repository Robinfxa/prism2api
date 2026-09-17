# Prism Web Live Protocol Analysis

## Overview & Evidence Grade

All statements below are assigned evidence grades:
- **Grade A**: Captured directly via live browser network trace on `prism.openai.com`
- **Grade B**: Third-party runtime evidence
- **Grade C**: User documentation or forum posts
- **Grade D**: Speculation

---

## Endpoint Specification

### A. Generation Submit (`response_with_tools_start`) [Grade A]

- **HTTP Method**: `POST`
- **URL Path**: `/api/llm/response_with_tools_start`
- **Headers**:
  - `content-type`: `application/json`
  - `origin`: `https://prism.openai.com`
  - `referer`: `https://prism.openai.com/?u=<project_id>&pg=1&m=main.tex`
  - `cookie`: Contains `prism_session_token`, `prism_oai_access_token`, `__cf_bm`, `cf_clearance`
- **Request Schema**:
  ```json
  {
    "input": [
      {
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": "..."}]
      }
    ],
    "metadata": {
      "projectId": "<uuid>",
      "userId": "<user_id>",
      "model": "gpt-6-astra",
      "reasoning_effort": "medium"
    },
    "conversationId": "cdx1_<conversation_uuid>"
  }
  ```

### B. Status & Observation (`response_with_tools_status`) [Grade A]

- **HTTP Method**: `POST`
- **URL Path**: `/api/llm/response_with_tools_status`
- **Headers**: `content-type: application/json`, Cookie-authenticated
- **Request Schema**:
  ```json
  {
    "request_id": "<request_uuid>",
    "turn_state": {
      "version": 1,
      "conversation_id": "cdx1_<conversation_uuid>",
      "prompt": "...",
      "user_id": "<user_id>",
      "project_id": "<project_id>",
      "async_job_id": "<job_id>"
    }
  }
  ```

---

## Authentication Mechanism [Grade A]

Authentication relies on dual cookie-based tokens:
1. `prism_session_token`: JWT issued by `crixet.prism.session` encoding `user_id` and `selected_workspace`.
2. `prism_oai_access_token`: JWT issued by `auth.openai.com` containing OpenAI OAuth scope permissions.

Secrets are stored outside repository in `$HOME/.prism2api/research/raw/`.

---

## Key Context Identifiers [Grade A]

1. `projectId`: Target LaTeX workspace GUID (e.g., `proj_fixture_001`).
2. `conversationId`: Active thread identifier prefixed with `cdx1_` (e.g., `cdx1_cdx1_fixture_001`).
3. `userId`: Account user reference (e.g., `user_fixture_001`).
