# Design: Fix Honest Generation Outcome and Terminal Evidence

## Architecture & Data Flow

1. **`EventNormalizer`**:
   - Collect normalized events into `events`.
   - Maintain authoritative text buffer from `TEXT_DELTA` and `TEXT_SNAPSHOT`.
   - Track terminal events (`RUN_COMPLETED`, `RUN_FAILED`, `CANCELLATION_CONFIRMED`, `PROTOCOL_UNKNOWN`).

2. **`RunSupervisor.execute_run`**:
   - Inspect `EventNormalizer.events` for terminal event.
   - If `RUN_COMPLETED` is found:
     - Set `result.text` from normalizer or `payload.text`.
     - Populate `manifest.completion_evidence` with terminal event info.
     - `result.provider_model_id_confirmed` remains `None` unless confirmed by event evidence.
   - If `RUN_FAILED` or `CANCELLATION_CONFIRMED` or `PROTOCOL_UNKNOWN` or no terminal event:
     - Transition state to `FAILED`, `CANCELLED`, or `UNCERTAIN` accordingly.
     - Raise an error so the caller receives the non-success state.

3. **`StorageJournal.save_result_and_manifest`**:
   - Compute `res_final` and `man_final` file paths.
   - Set `result.manifest_ref = str(man_final)` before dumping JSON to `res_tmp`.

4. **`FastAPI Gateway (app.py)`**:
   - Omit `usage` (return `None`) in `ChatCompletionResponse` when token usage is unknown.
