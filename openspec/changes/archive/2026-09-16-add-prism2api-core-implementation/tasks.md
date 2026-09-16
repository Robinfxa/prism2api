# Implementation Tasks

- [x] Create core package structure under `src/prism2api/`
- [x] Implement Settings and Configuration in `src/prism2api/config.py`
- [x] Implement SQLite DB Schema (9 tables) and Journal in `src/prism2api/storage/`
- [x] Implement ContextManager, ResourceLease, and Isolation in `src/prism2api/runtime/context.py`
- [x] Implement EventNormalizer & NormalizedEvents in `src/prism2api/runtime/events.py`
- [x] Implement RunSupervisor lifecycle, idempotency key checks, and crash recovery in `src/prism2api/runtime/supervisor.py`
- [x] Implement PrismAdapter, CapabilitySnapshot, and RemoteHandle in `src/prism2api/provider/`
- [x] Implement BaseTransport, TransportSession, and MockTransport in `src/prism2api/transport/`
- [x] Implement FastAPI HTTP Gateway (M01 API & Chat Completions) in `src/prism2api/api/app.py`
- [x] Implement SDKClient with OS single-instance lock in `src/prism2api/client.py`
- [x] Implement test suite in `tests/` and verify 100% green pytest execution
- [x] Verify `docs/validation/check_book.py` structural documentation check
