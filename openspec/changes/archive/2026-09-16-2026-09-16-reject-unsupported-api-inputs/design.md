# Design: Reject Unsupported API Inputs Pre-Submit

## Architectural Flow

In `create_chat_completion` in `src/prism2api/api/app.py`:

```
Incoming Request
      │
      ▼
1. Validate Model (Check against list_models())
      │ (invalid -> HTTP 404)
      ▼
2. Validate Parameters (temperature, top_p, stream=True, n!=1, tools, max_tokens)
      │ (invalid -> HTTP 400)
      ▼
3. Validate Messages (len == 1, role == "user")
      │ (invalid -> HTTP 400)
      ▼
4. Enqueue Run & Execute Run
```

All validation steps occur synchronously before `app_supervisor.enqueue_run(...)`, ensuring zero adapter/transport submissions take place on invalid inputs.
