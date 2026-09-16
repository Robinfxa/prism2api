# offline-readiness Specification

## Purpose
TBD - created by archiving change complete-offline-core-asf. Update Purpose after archive.
## Requirements
### Requirement: Honest terminal evidence
The runtime SHALL publish success only after identity-bound, non-contradictory terminal and output evidence is durably stored. Missing, foreign or conflicting evidence SHALL NOT become success.

#### Scenario: Conflicting terminal evidence
- **GIVEN** a run receiving completed followed by failed or foreign-task evidence
- **WHEN** the full observed evidence is normalized
- **THEN** the run remains uncertain and no successful result is published.

#### Scenario: Explicit empty final output
- **GIVEN** a final completion explicitly contains an empty string
- **WHEN** the response is persisted
- **THEN** the empty result is preserved rather than replaced with stale text.

### Requirement: Frozen request and idempotent execution
The runtime SHALL persist accepted input, account and context semantics before execution and SHALL never replace them from a later execute argument or repeat a completed idempotent request.

#### Scenario: Execute argument differs
- **GIVEN** an accepted input A
- **WHEN** execute is asked to send B
- **THEN** the request is rejected before any upstream operation.

#### Scenario: Concurrent duplicate admission
- **GIVEN** concurrent calls with the same principal, idempotency key and intent
- **WHEN** they are admitted
- **THEN** they reference one durable run and at most one submission attempt is dispatched.

### Requirement: Durable intent and exact read-only reconciliation
The runtime SHALL commit intent before remote side effects, retain known receipts even when validation fails, and resolve uncertain work only from the original account and exact non-conflicting handle without submitting again.

#### Scenario: Crash after dispatch intent
- **GIVEN** a process exits after submit intent is committed
- **WHEN** another runtime starts with the same home
- **THEN** the task becomes uncertain, new generation is blocked, and submit count does not increase.

#### Scenario: Receipt conflicts with prepared context
- **GIVEN** a receipt contains a different workspace
- **WHEN** validation or reconciliation is attempted
- **THEN** the receipt remains recorded, uncertainty is preserved and lookup is not redirected to that workspace.

### Requirement: Single owner and bounded work
Every embedded or HTTP writer SHALL hold the same home lock. A live worker SHALL retain the lock until it actually stops, and requests and events SHALL obey configured local budgets.

#### Scenario: Shutdown cannot stop a blocking worker
- **GIVEN** an upstream call does not return before cleanup deadline
- **WHEN** close is requested
- **THEN** shutdown reports failure and another writer cannot acquire the home.

### Requirement: Shared authorization and explicit transport
Default runtime SHALL be unconfigured. Mock operation SHALL require explicit selection. All run mutation and context reuse paths SHALL enforce their principal and account ownership.

#### Scenario: Cross-principal cancellation
- **GIVEN** an authenticated local principal and another principal's run
- **WHEN** cancellation is requested
- **THEN** the response does not expose the run and its state or cancellation flag is unchanged.

### Requirement: Executable local API and SDK
The native API SHALL execute accepted queued work through the single worker and expose result retrieval. The daemon SDK SHALL use loopback HTTP without creating a second local writer or retrying POST automatically.

#### Scenario: Native submit to result
- **GIVEN** an explicitly configured mock local service
- **WHEN** a native request is accepted
- **THEN** the worker produces a retrievable result labeled mock and idempotent replay does not submit again.

