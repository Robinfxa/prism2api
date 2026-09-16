"""Safe public errors; raw provider exceptions are never HTTP messages."""

class PrismError(RuntimeError):
    code = "prism_error"
    http_status = 502

    def __init__(self, message=None, *, run_id=None):
        super().__init__(message or self.code)
        self.run_id = run_id

class AdmissionBlockedError(PrismError):
    code = "admission_blocked"
    http_status = 503

class UnsupportedRequestError(PrismError):
    code = "unsupported_request"
    http_status = 400

class InputTooLargeError(PrismError):
    code = "input_too_large"
    http_status = 413

class QueueFullError(PrismError):
    code = "queue_full"
    http_status = 429

class ResultUnavailableError(PrismError):
    code = "result_unavailable"
    http_status = 410

class OutcomeError(PrismError):
    def __init__(self, state, *, run_id):
        self.state = str(getattr(state, "value", state))
        self.code = "run_" + self.state
        self.http_status = 409 if self.state == "cancelled" else 502
        super().__init__(self.code, run_id=run_id)

class WaitTimeoutError(PrismError, TimeoutError):
    code = "wait_timeout"
    http_status = 504

class ProtocolError(PrismError):
    code = "protocol_uncertain"
