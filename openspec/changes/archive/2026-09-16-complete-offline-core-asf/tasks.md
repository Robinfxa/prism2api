# Tasks: complete offline core

- [x] Verify latest baseline and Git blob identity for 14 production files + 7 tests.
- [x] Reproduce original19 and old43 audit cases; record actual commands/results.
- [x] Fix terminal identity/conflicts, exact empty output, late text and evidence publication.
- [x] Freeze accepted inputs/config/context/account and enforce idempotent replay.
- [x] Persist submit/resource intents and receipts; retain uncertain latch across restarts.
- [x] Implement exact read-only reconciliation and prevent mismatched-context lookup.
- [x] Share OS lock and database ownership across SDK/HTTP; bound queue/events and shutdown.
- [x] Close the native worker/result loop and daemon SDK; default fail-closed and strict API rejection.
- [x] Preserve existing tests and add meaningful core / subprocess / loopback regression coverage.
- [x] Verify source tests, build wheel, install without the source tree and run installed-wheel tests.
- [x] Prepare safe patch application, source integrity and local integration handoff.
- [ ] Run OpenSpec CLI strict validation and archive in an environment with the CLI (not installed here).
- [ ] Verify macOS/Python3.12 and real Prism account/protocol in the separate local integration stage.

The final two items are explicitly not offline implementation claims. No remote push was performed. Verification details: verification.md.
