from functools import wraps
from flask import request, jsonify, g
from auth_utils import decode_token
from config import Config


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def require_auth(f):
    """
    Validate the Bearer token and attach the decoded payload to Flask's g.
    Any downstream decorator or route can read g.current_user.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header[len("Bearer "):]
        try:
            g.current_user = decode_token(token)
        except ValueError as e:
            return jsonify({"error": str(e)}), 401

        return f(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Role-based access control
# ---------------------------------------------------------------------------

def require_role(minimum_role: str):
    """
    Decorator factory. Ensures the authenticated user's role meets the
    minimum required level (viewer < analyst < admin).

    Usage:
        @require_auth
        @require_role("admin")
        def my_route(): ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user_role  = g.current_user.get("role", "viewer")
            user_level = Config.ROLES.get(user_role, 0)
            min_level  = Config.ROLES.get(minimum_role, 999)

            if user_level < min_level:
                return jsonify({
                    "error": "Forbidden",
                    "detail": f"This action requires the '{minimum_role}' role or higher."
                }), 403

            return f(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Ownership helper (non-decorator)
# ---------------------------------------------------------------------------

def is_admin() -> bool:
    return g.current_user.get("role") == "admin"


def current_user_id() -> int:
    return g.current_user["sub"]
