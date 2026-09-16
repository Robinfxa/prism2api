# Proposal: Fix Honest Generation Outcome and Terminal Evidence

## Summary

Correct the generation outcome lifecycle in `prism2api` to ensure that run completion, terminal evidence, result persistence, and usage metadata reflect honest execution facts rather than pseudo-success fallbacks.

## Motivation

Audit findings (F01, F07) revealed that the current prototype accepts unverified runs as `succeeded`, returns hardcoded model names (`prism-v1-confirmed`) and token usage counts (`10/10/20`), loses `manifest_ref` in persisted result JSON, and ignores non-prefix text snapshot updates.

## Proposed Changes

1. **Terminal Evidence Verification**: Only transition runs to `SUCCEEDED` when an explicit `RunCompleted` event with valid output is present.
2. **Unobserved Metadata Removal**: Set `provider_model_id_confirmed` and API `usage` to `None` when unobserved.
3. **Persisted Reference Fix**: Assign `manifest_ref` to `GenerationResult` prior to saving to ensure disk files maintain valid manifest links.
4. **Authoritative Snapshot Updates**: Update text buffer on authoritative `TextSnapshot` events even during non-prefix rewrites.
