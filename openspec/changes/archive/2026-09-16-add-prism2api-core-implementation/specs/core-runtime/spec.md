# Core Runtime Spec

## ADDED Requirements

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
