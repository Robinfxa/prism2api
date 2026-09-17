## ADDED Requirements

### Requirement: Import one complete private request snapshot
The importer SHALL treat cURL as data, preserve captured metadata and snapshot JSON types, and atomically save one validated private bundle. It MUST NOT execute shell code or merge fallback identities.

#### Scenario: Incomplete capture
- WHEN a required captured field is absent
- THEN import fails without replacing the previous bundle or printing secrets.

### Requirement: Direct generation must be truthful
The direct runtime SHALL call the captured Prism request shape through HTTP only. It SHALL submit at most once per accepted local run and preserve updated turn_state values during status polling.

#### Scenario: Submission outcome becomes unknown
- WHEN submit may have been sent and a confirmed terminal is unavailable
- THEN the run remains uncertain across restart and no automatic new submit is permitted.

### Requirement: Fixed context must be explicit
The local authenticated API SHALL label this mode fixed/shared, serialize execution, and reject unsupported input rather than silently ignore it.

#### Scenario: Unsupported tools or multi-message request
- WHEN an unsupported request reaches the local endpoint
- THEN it is rejected before any upstream call.

### Requirement: Offline tests are not live evidence
The release SHALL distinguish fake-upstream tests from actual Prism tests.

#### Scenario: No authorized live credential in the build environment
- WHEN packaging completes without real Prism calls
- THEN live qualification remains not_run, regardless of offline pass count.
