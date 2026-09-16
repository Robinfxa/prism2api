# Core Runtime Spec Delta: Honest Outcome & Evidence Integrity

## ADDED Requirements

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
