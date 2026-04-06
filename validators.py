import re
from datetime import datetime


class ValidationError(Exception):
    """Raised when request data fails validation."""
    def __init__(self, errors: dict):
        self.errors = errors
        super().__init__(str(errors))


# ---------------------------------------------------------------------------
# Field validators
# ---------------------------------------------------------------------------

def _required(value, name):
    if value is None or (isinstance(value, str) and not value.strip()):
        return f"{name} is required"
    return None


def _min_length(value, name, length):
    if isinstance(value, str) and len(value.strip()) < length:
        return f"{name} must be at least {length} characters"
    return None


def _is_email(value, name):
    pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    if not re.match(pattern, str(value)):
        return f"{name} must be a valid email address"
    return None


def _is_date(value, name):
    try:
        datetime.strptime(str(value), "%Y-%m-%d")
        return None
    except ValueError:
        return f"{name} must be a valid date in YYYY-MM-DD format"


def _is_positive_number(value, name):
    try:
        if float(value) <= 0:
            return f"{name} must be a positive number"
        return None
    except (TypeError, ValueError):
        return f"{name} must be a numeric value"


def _in_set(value, name, allowed: set):
    if value not in allowed:
        return f"{name} must be one of: {', '.join(sorted(allowed))}"
    return None


# ---------------------------------------------------------------------------
# Schema validators
# ---------------------------------------------------------------------------

def validate_login(data: dict) -> dict:
    errors = {}
    for field in ("username", "password"):
        err = _required(data.get(field), field)
        if err:
            errors[field] = err
    if errors:
        raise ValidationError(errors)
    return {
        "username": data["username"].strip(),
        "password": data["password"],
    }


def validate_create_user(data: dict) -> dict:
    errors = {}

    err = _required(data.get("username"), "username")
    if not err:
        err = _min_length(data.get("username"), "username", 3)
    if err:
        errors["username"] = err

    err = _required(data.get("email"), "email")
    if not err:
        err = _is_email(data.get("email"), "email")
    if err:
        errors["email"] = err

    err = _required(data.get("password"), "password")
    if not err:
        err = _min_length(data.get("password"), "password", 8)
    if err:
        errors["password"] = err

    role = data.get("role", "viewer")
    err = _in_set(role, "role", {"viewer", "analyst", "admin"})
    if err:
        errors["role"] = err

    if errors:
        raise ValidationError(errors)

    return {
        "username": data["username"].strip(),
        "email":    data["email"].strip().lower(),
        "password": data["password"],
        "role":     role,
    }


def validate_update_user(data: dict) -> dict:
    """Partial update — only validates fields that are present."""
    errors = {}
    cleaned = {}

    if "email" in data:
        err = _is_email(data["email"], "email")
        if err:
            errors["email"] = err
        else:
            cleaned["email"] = data["email"].strip().lower()

    if "role" in data:
        err = _in_set(data["role"], "role", {"viewer", "analyst", "admin"})
        if err:
            errors["role"] = err
        else:
            cleaned["role"] = data["role"]

    if "status" in data:
        err = _in_set(data["status"], "status", {"active", "inactive"})
        if err:
            errors["status"] = err
        else:
            cleaned["status"] = data["status"]

    if "username" in data:
        err = _min_length(data["username"], "username", 3)
        if err:
            errors["username"] = err
        else:
            cleaned["username"] = data["username"].strip()

    if errors:
        raise ValidationError(errors)
    return cleaned


def validate_create_record(data: dict) -> dict:
    errors = {}

    err = _required(data.get("amount"), "amount")
    if not err:
        err = _is_positive_number(data.get("amount"), "amount")
    if err:
        errors["amount"] = err

    err = _required(data.get("type"), "type")
    if not err:
        err = _in_set(data.get("type"), "type", {"income", "expense"})
    if err:
        errors["type"] = err

    err = _required(data.get("category"), "category")
    if err:
        errors["category"] = err

    err = _required(data.get("date"), "date")
    if not err:
        err = _is_date(data.get("date"), "date")
    if err:
        errors["date"] = err

    if errors:
        raise ValidationError(errors)

    return {
        "amount":   float(data["amount"]),
        "type":     data["type"],
        "category": data["category"].strip(),
        "date":     data["date"],
        "notes":    data.get("notes", ""),
    }


def validate_update_record(data: dict) -> dict:
    errors = {}
    cleaned = {}

    if "amount" in data:
        err = _is_positive_number(data["amount"], "amount")
        if err:
            errors["amount"] = err
        else:
            cleaned["amount"] = float(data["amount"])

    if "type" in data:
        err = _in_set(data["type"], "type", {"income", "expense"})
        if err:
            errors["type"] = err
        else:
            cleaned["type"] = data["type"]

    if "category" in data:
        if not data["category"] or not str(data["category"]).strip():
            errors["category"] = "category cannot be empty"
        else:
            cleaned["category"] = data["category"].strip()

    if "date" in data:
        err = _is_date(data["date"], "date")
        if err:
            errors["date"] = err
        else:
            cleaned["date"] = data["date"]

    if "notes" in data:
        cleaned["notes"] = data["notes"]

    if errors:
        raise ValidationError(errors)
    return cleaned


def validate_record_filters(args) -> dict:
    """Parse and validate query string filters for record listing."""
    errors = {}
    filters = {}

    if args.get("type"):
        err = _in_set(args["type"], "type", {"income", "expense"})
        if err:
            errors["type"] = err
        else:
            filters["type"] = args["type"]

    if args.get("category"):
        filters["category"] = args["category"].strip()

    if args.get("from_date"):
        err = _is_date(args["from_date"], "from_date")
        if err:
            errors["from_date"] = err
        else:
            filters["from_date"] = args["from_date"]

    if args.get("to_date"):
        err = _is_date(args["to_date"], "to_date")
        if err:
            errors["to_date"] = err
        else:
            filters["to_date"] = args["to_date"]

    page = args.get("page", "1")
    per_page = args.get("per_page", "20")
    try:
        filters["page"]     = max(1, int(page))
        filters["per_page"] = min(100, max(1, int(per_page)))
    except ValueError:
        errors["pagination"] = "page and per_page must be integers"

    if errors:
        raise ValidationError(errors)
    return filters
