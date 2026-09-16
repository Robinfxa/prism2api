# Design: Core Runtime Architecture for prism2api

## Architecture Layers
- `src/prism2api/config.py`: `Settings` with POSIX directory permissions (`0700`) for `PRISM2API_HOME`.
- `src/prism2api/storage/db.py`: SQLite connection with WAL mode and `check_same_thread=False` for threadpool safety.
- `src/prism2api/storage/journal.py`: Two-phase atomic file commit with SHA-256 result & manifest hashing.
- `src/prism2api/runtime/context.py`: ResourceLease compare-and-swap with ContextBusyError protection.
- `src/prism2api/runtime/supervisor.py`: Atomic intent logging before adapter dispatch; startup crash recovery.
- `src/prism2api/api/app.py`: FastAPI server with Host, Origin, and API-Key middleware.
- `src/prism2api/client.py`: `SDKClient` acquiring exclusive OS file lock (`locks/prism2api.lock`) in `embedded` mode.

## Invariants & Compliance
- **I04 / I05**: Intent logged before dispatch; results verified and persisted before marking `succeeded`.
- **I09**: Credentials and API keys redacted via sanitizer.
- **I10**: Single-instance OS file lock enforced in SDK embedded mode.
- **T01-T52**: 100% compliant test suite in `tests/`.
