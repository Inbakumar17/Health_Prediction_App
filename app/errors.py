"""Turn every error into the same JSON shape for the frontend:

    {"detail": "One summary sentence", "errors": {"email": "...", "dob": "..."}}

"errors" maps a form field to its message, so the page can show it under that field.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

FIELD_LABELS = {
    "full_name": "Full name",
    "dob": "Date of birth",
    "email": "Email",
    "glucose": "Glucose",
    "haemoglobin": "Haemoglobin",
    "cholesterol": "Cholesterol",
}


class RecordError(Exception):
    """A business-rule error, e.g. duplicate record (409) or not found (404)."""

    def __init__(self, status_code: int, message: str, errors: dict[str, str] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.errors = errors or {}


def _clean(message: str) -> str:
    # Pydantic adds "Value error, " in front of our own messages.
    return message.removeprefix("Value error, ")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors: dict[str, str] = {}
        for error in exc.errors():
            location = [str(part) for part in error.get("loc", []) if part != "body"]
            field = location[0] if location else "form"
            if error.get("type") == "missing":
                message = f"{FIELD_LABELS.get(field, field)} is required."
            elif error.get("type") in ("float_parsing", "float_type"):
                message = f"{FIELD_LABELS.get(field, field)} must be a number."
            else:
                message = _clean(error.get("msg", "Invalid value."))
            errors.setdefault(field, message)  # first problem per field is enough
        count = len(errors)
        summary = f"{count} field{'s' if count != 1 else ''} need{'s' if count == 1 else ''} fixing."
        return JSONResponse(status_code=422, content={"detail": summary, "errors": errors})

    @app.exception_handler(RecordError)
    async def record_error(_: Request, exc: RecordError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "errors": exc.errors})
