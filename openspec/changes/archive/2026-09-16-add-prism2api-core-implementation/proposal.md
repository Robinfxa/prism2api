# Proposal: Add prism2api Core Runtime Implementation and Acceptance Suite

## Goal
Implement the core runtime Python package (`src/prism2api/`) and full test suite (`tests/`) according to the architecture design book v0.1.0, covering Modules M01 through M08 and acceptance rules T01 to T52.

## Key Changes
1. **M01 API & SDK**: FastAPI gateway server with API key auth, Host/Origin headers, loopback enforcement, `/prism/v1/runs`, `/v1/chat/completions`, and Python SDK `SDKClient` with `embedded` and `daemon` mode support.
2. **M02 Provider & Capabilities**: `PrismAdapter`, `CapabilitySnapshot`, `RemoteHandle`, and capability inspection.
3. **M03 RunSupervisor & Lifecycle**: Complete state machine (`queued` -> `preparing` -> `submitting` -> `running` -> `succeeded`), atomic intent logging before dispatch, idempotency key deduplication & conflict checks, and startup crash recovery.
4. **M04 Context Isolation**: `ContextBinding`, `ResourceLease` compare-and-swap, single-owner busy checking, and nonce isolation verification.
5. **M05 Event Normalizer**: `NormalizedEvent`, `EventNormalizer` append-only text accumulator, and delivery tracking.
6. **M06 Storage & Journal**: SQLite `runtime.db` schema (9 tables), two-phase atomic file commit (`results/`, `evidence/`), `EvidenceManifest`, and log secret sanitization.
7. **M07 Auth & Transport**: `AuthProfile`, `TransportSession`, and `MockTransport` for offline contract tests.
8. **M08 Verification & Tests**: 100% green test suite in `tests/` covering unit, contract, recovery, replay, and T01-T52 acceptance rules.

## Verification
- Run `PYTHONPATH=src python3 -m pytest -v tests/` (19 passing tests).
- Run `python3 docs/validation/check_book.py` (`status: pass`).
