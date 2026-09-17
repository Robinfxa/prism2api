# Verification: offline core

**Implementation:** complete locally. **Live Prism:** not exercised. **Remote publication:** blocked403. **OpenSpec CLI:** unavailable, validation/archive pending.

Observed commands and results:

```text
Original baseline: python -m pytest <baseline/tests>              19 passed
Prior 43 audit cases on unchanged baseline                       22 failed, 21 passed
Patched source: python -m pytest -q                               103 passed (4.11s)
Repeated source suite                                            103 passed (4.02s)
Installed wheel from outside source tree                         103 passed (3.55s)
python -m pip wheel . --no-deps --no-build-isolation --no-index    succeeded
python -m prism2api smoke --mock --home <scratch>                  synthetic output; no Prism call
```

Archive evidence is in the delivery package `evidence/`. The complete validation statement, including RED limits, environment reuse during wheel installation, unverified macOS/Python3.12 and deferred features, is [the report](../../../../docs/validation/offline-runtime-asf.md).

19 old tests retained; 43 prior audit tests now pass; 41 new runtime cases. Tests target real public/core paths with a synthetic external transport and default network guard. One explicit loopback case uses a real local HTTP server; a process-crash case exits a subprocess and proves no resubmit after restart.

No production caller was stubbed out to force GREEN. The original cross-principal cancellation setup now holds the actual generation mutex to control a worker race while asserting unchanged queued state/cancel flag. Source and all installed wheel production files matched byte-for-byte.

Ponytail: reuse original modules; stdlib synchronization/SQLite/durable files; existing HTTP dependencies. No distributed queue, provider platform or account pool added.

Remaining local gates are explicitly unchecked in tasks.md; this file is not a forged openspec validate result.
