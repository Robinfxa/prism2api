# api-contract Specification

## Purpose
TBD - created by archiving change 2026-09-16-reject-unsupported-api-inputs. Update Purpose after archive.
## Requirements
### Requirement: Pre-Submit Parameter Rejection
The gateway API SHALL reject requests containing unsupported parameters (`stream=True`, `n != 1`, `tools`, `max_tokens`, `temperature`, `top_p`) with HTTP 400 before enqueuing or submitting any execution run.

#### Scenario: Unsupported Parameter Rejected
- Given a request with stream=True or tools
- When received by completions endpoint
- Then HTTP 400 Bad Request is returned.

### Requirement: Pre-Submit Payload Rejection
The gateway API SHALL reject requests containing multi-turn conversation messages or non-user roles with HTTP 400 before enqueuing or submitting any execution run.

#### Scenario: Multi-turn Payload Rejected
- Given a request with multiple messages
- When received by completions endpoint
- Then HTTP 400 Bad Request is returned.

### Requirement: Pre-Submit Model Validation
The gateway API SHALL reject requests specifying unlisted or unregistered model identifiers with HTTP 404 before enqueuing or submitting any execution run.

#### Scenario: Unknown Model Alias Rejected
- Given a request with unknown model alias
- When received by completions endpoint
- Then HTTP 404 Not Found is returned.

