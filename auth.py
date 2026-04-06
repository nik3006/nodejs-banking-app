from flask import Blueprint, request, jsonify
from db import get_db, row_to_dict
from auth_utils import verify_password, create_token
from validators import validate_login, ValidationError

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    POST /auth/login
    Body: { "username": str, "password": str }
    Returns a JWT on success.
    """
    data = request.get_json(silent=True) or {}

    try:
        cleaned = validate_login(data)
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "fields": e.errors}), 422

    with get_db() as conn:
        user = row_to_dict(
            conn.execute(
                "SELECT * FROM users WHERE username = ?",
                (cleaned["username"],),
            ).fetchone()
        )

    if not user or not verify_password(cleaned["password"], user["password"]):
        return jsonify({"error": "Invalid username or password"}), 401

    if user["status"] == "inactive":
        return jsonify({"error": "Account is inactive. Contact an administrator."}), 403

    token = create_token(user)
    return jsonify({
        "token": token,
        "user": {
            "id":       user["id"],
            "username": user["username"],
            "email":    user["email"],
            "role":     user["role"],
        },
    }), 200
