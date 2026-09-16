# Proposal: Reject Unsupported API Inputs Pre-Submit

## Summary

Enforce strict pre-submit validation for the OpenAI-compatible `/v1/chat/completions` API endpoint, rejecting unsupported parameters (`stream=True`, `n != 1`, `tools`, `max_tokens`), multi-turn message history, and unlisted models prior to run enqueuing or submission.

## Motivation

Audit finding F05 highlighted that requests with `stream=True`, `n=2`, `tools`, `max_tokens`, multi-turn message lists, or non-existent model IDs were returning HTTP 200 and silently discarding fields or processing invalid configurations.

## Proposed Changes

1. Declare `tools` and `max_tokens` in `ChatCompletionRequest`.
2. Reject unlisted models with HTTP 404.
3. Reject unsupported parameters (`stream=True`, `n != 1`, `tools`, `max_tokens`, `temperature`, `top_p`) with HTTP 400.
4. Reject multi-turn messages or non-user first messages with HTTP 400.
5. Ensure 0 runs are enqueued or submitted for rejected requests.
