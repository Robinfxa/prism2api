# core-runtime Specification

## Purpose
TBD - created by archiving change add-prism2api-core-implementation. Update Purpose after archive.
## Requirements
### Requirement: Native Run Execution
The system SHALL enqueue and execute native generation runs with single-owner resource leases and atomic intent logging before dispatch.

#### Scenario: Successful Native Run Execution
- Given a valid NativeRunRequest
- When enqueue_run and execute_run are invoked
- Then the run transitions to SUCCEEDED and persisted results are stored in SQLite and results directory.

### Requirement: Idempotency Key Deduplication
The system SHALL deduplicate requests using salted SHA-256 idempotency key digests and reject conflicting parameters with 409 Conflict.

#### Scenario: Idempotency Key Conflict Rejection
- Given an existing Idempotency-Key
- When a new request with a different payload fingerprint is submitted
- Then the system raises an IdempotencyConflictError.

### Requirement: API Authentication and Loopback Security
The system SHALL enforce X-API-Key or Authorization Bearer header authentication and restrict connections to loopback hosts.

#### Scenario: Unauthenticated Request Rejection
- Given an HTTP request without a valid API key
- When processed by security middleware
- Then the server returns 401 Unauthorized.

### Requirement: Terminal Evidence Verification
The supervisor SHALL only transition a run to `SUCCEEDED` state when an explicit, authenticated `RunCompleted` event is observed in the normalized event stream.
Runs with `RunFailed`, `CancellationConfirmed`, `ProtocolUnknown`, or incomplete event streams SHALL NOT transition to `SUCCEEDED`.

#### Scenario: Terminal RunCompleted Event Required for Succeeded
- Given an active generation run
- When event stream is observed
- Then state only transitions to SUCCEEDED if a valid RunCompleted event is present.

### Requirement: Unobserved Metadata Integrity
The supervisor and gateway API SHALL NOT fabricate provider model identifiers or token usage counts. Unobserved fields SHALL remain `None`.

#### Scenario: Unobserved Metadata Kept Null
- Given a generation response without provider model ID
- When GenerationResult is built
- Then provider_model_id_confirmed remains null.

### Requirement: Persisted Evidence Link Integrity
The `GenerationResult` persisted to storage SHALL contain a non-null `manifest_ref` pointing to the corresponding `EvidenceManifest` file.

#### Scenario: Manifest Link Present in Result
- Given a successful generation result
- When saved to storage
- Then manifest_ref points to the evidence manifest file path.

