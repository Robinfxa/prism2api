"""Public errors deliberately contain no upstream body, credentials or remote IDs."""

class DirectError(Exception):
    def __init__(self, code: str, message: str, status: int = 502, *, run_id: str | None = None):
        self.code, self.message, self.status, self.run_id = code, message, status, run_id
        super().__init__(message)

    def public(self) -> dict:
        error = {"code": self.code, "type": "prism2api_error", "message": self.message}
        if self.run_id:
            error["run_id"] = self.run_id
        return {"error": error}


def invalid(code: str, message: str) -> DirectError:
    return DirectError(code, message, 400)
