from flask import Blueprint, request, jsonify, g
from db import get_db, row_to_dict, rows_to_list
from auth_utils import hash_password
from middleware import require_auth, require_role, current_user_id
from validators import validate_create_user, validate_update_user, ValidationError

users_bp = Blueprint("users", __name__)


def _safe_user(user: dict) -> dict:
    """Strip the password hash before returning user data."""
    return {k: v for k, v in user.items() if k != "password"}


# ---------------------------------------------------------------------------
# List users — admin only
# ---------------------------------------------------------------------------

@users_bp.route("/", methods=["GET"])
@require_auth
@require_role("admin")
def list_users():
    """GET /users/  —  Returns all users (admin only)."""
    status_filter = request.args.get("status")  # optional ?status=active|inactive

    with get_db() as conn:
        if status_filter in ("active", "inactive"):
            rows = conn.execute(
                "SELECT * FROM users WHERE status = ? ORDER BY created_at DESC",
                (status_filter,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM users ORDER BY created_at DESC"
            ).fetchall()

    users = [_safe_user(dict(r)) for r in rows]
    return jsonify({"users": users, "total": len(users)}), 200


# ---------------------------------------------------------------------------
# Create user — admin only
# ---------------------------------------------------------------------------

@users_bp.route("/", methods=["POST"])
@require_auth
@require_role("admin")
def create_user():
    """POST /users/  —  Create a new user (admin only)."""
    data = request.get_json(silent=True) or {}

    try:
        cleaned = validate_create_user(data)
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "fields": e.errors}), 422

    with get_db() as conn:
        # Uniqueness checks
        if conn.execute(
            "SELECT id FROM users WHERE username = ?", (cleaned["username"],)
        ).fetchone():
            return jsonify({"error": "Username already taken"}), 409

        if conn.execute(
            "SELECT id FROM users WHERE email = ?", (cleaned["email"],)
        ).fetchone():
            return jsonify({"error": "Email already in use"}), 409

        cursor = conn.execute(
            """INSERT INTO users (username, email, password, role)
               VALUES (?, ?, ?, ?)""",
            (
                cleaned["username"],
                cleaned["email"],
                hash_password(cleaned["password"]),
                cleaned["role"],
            ),
        )
        user = row_to_dict(
            conn.execute(
                "SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        )

    return jsonify({"message": "User created", "user": _safe_user(user)}), 201


# ---------------------------------------------------------------------------
# Get single user — admin can fetch any; others can only fetch themselves
# ---------------------------------------------------------------------------

@users_bp.route("/<int:user_id>", methods=["GET"])
@require_auth
def get_user(user_id):
    """GET /users/<id>  —  Admins see any user; others only see themselves."""
    if g.current_user["role"] != "admin" and current_user_id() != user_id:
        return jsonify({"error": "Forbidden"}), 403

    with get_db() as conn:
        user = row_to_dict(
            conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        )

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"user": _safe_user(user)}), 200


# ---------------------------------------------------------------------------
# Update user — admin only
# ---------------------------------------------------------------------------

@users_bp.route("/<int:user_id>", methods=["PATCH"])
@require_auth
@require_role("admin")
def update_user(user_id):
    """PATCH /users/<id>  —  Partial update of a user (admin only)."""
    data = request.get_json(silent=True) or {}

    try:
        cleaned = validate_update_user(data)
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "fields": e.errors}), 422

    if not cleaned:
        return jsonify({"error": "No valid fields provided for update"}), 400

    with get_db() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404

        set_clause = ", ".join(f"{col} = ?" for col in cleaned)
        set_clause += ", updated_at = datetime('now')"
        values     = list(cleaned.values()) + [user_id]
        conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)

        updated = row_to_dict(
            conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        )

    return jsonify({"message": "User updated", "user": _safe_user(updated)}), 200


# ---------------------------------------------------------------------------
# Delete user — admin only (hard delete)
# ---------------------------------------------------------------------------

@users_bp.route("/<int:user_id>", methods=["DELETE"])
@require_auth
@require_role("admin")
def delete_user(user_id):
    """DELETE /users/<id>  —  Permanently removes a user (admin only)."""
    if current_user_id() == user_id:
        return jsonify({"error": "You cannot delete your own account"}), 400

    with get_db() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404

        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    return jsonify({"message": "User deleted"}), 200
