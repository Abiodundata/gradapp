from rest_framework.views import exception_handler


def _first_message(details):
    """Return the first human-readable message found in DRF error details."""
    if isinstance(details, str):
        return details
    if isinstance(details, list):
        for item in details:
            message = _first_message(item)
            if message:
                return message
    if isinstance(details, dict):
        for key, value in details.items():
            message = _first_message(value)
            if message:
                if key in ("detail", "non_field_errors"):
                    return message
                label = key.replace("_", " ").capitalize()
                return f"{label}: {message}"
    return ""


def api_exception_handler(exc, context):
    """Wrap every API error in one consistent shape.

    {
        "error": {
            "status": 400,
            "message": "Password confirm: Passwords do not match.",
            "details": {...original DRF details...}
        }
    }
    """
    response = exception_handler(exc, context)
    if response is not None:
        details = response.data
        response.data = {
            "error": {
                "status": response.status_code,
                "message": _first_message(details) or "Request failed.",
                "details": details,
            }
        }
    return response
