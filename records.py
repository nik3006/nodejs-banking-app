from flask import Blueprint, request, jsonify
from db import get_db, row_to_dict, rows_to_list
from middleware import require_auth, require_role, current_user_id, is_admin
from validators import (
    validate_create_record,
    validate_update_record,
    validate_record_filters,
    ValidationError,
)

records_bp = Blueprint("records", __name__)

# ---------------------------------------------------------------------------
# List records — viewer+  (with filtering and pagination)
# ---------------------------------------------------------------------------

@records_bp.route("/", methods=["GET"])
@require_auth
@require_role("viewer")
def list_records():
    """
    GET /records/
    Query params:
      type        income | expense
      category    string
      from_date   YYYY-MM-DD
      to_date     YYYY-MM-DD
      page        int (default 1)
      per_page    int (default 20, max 100)
    """
    try:
        filters = validate_record_filters(request.args)
    except ValidationError as e:
        return jsonify({"error": "Invalid query parameters", "fields": e.errors}), 422

    conditions = ["deleted_at IS NULL"]
    params     = []

    if "type" in filters:
        conditions.append("type = ?")
        params.append(filters["type"])

    if "category" in filters:
        conditions.append("category LIKE ?")
        params.append(f"%{filters['category']}%")

    if "from_date" in filters:
        conditions.append("date >= ?")
        params.append(filters["from_date"])

    if "to_date" in filters:
        conditions.append("date <= ?")
        params.append(filters["to_date"])

    where     = " AND ".join(conditions)
    page      = filters["page"]
    per_page  = filters["per_page"]
    offset    = (page - 1) * per_page

    with get_db() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM financial_records WHERE {where}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"""SELECT r.*, u.username as created_by_username
                FROM financial_records r
                JOIN users u ON r.created_by = u.id
                WHERE {where}
                ORDER BY r.date DESC, r.id DESC
                LIMIT ? OFFSET ?""",
            params + [per_page, offset],
        ).fetchall()

    return jsonify({
        "records":    rows_to_list(rows),
        "pagination": {
            "total":    total,
            "page":     page,
            "per_page": per_page,
            "pages":    (total + per_page - 1) // per_page,
        },
    }), 200


# ---------------------------------------------------------------------------
# Get single record — viewer+
# ---------------------------------------------------------------------------

@records_bp.route("/<int:record_id>", methods=["GET"])
@require_auth
@require_role("viewer")
def get_record(record_id):
    """GET /records/<id>"""
    with get_db() as conn:
        row = conn.execute(
            """SELECT r.*, u.username as created_by_username
               FROM financial_records r
               JOIN users u ON r.created_by = u.id
               WHERE r.id = ? AND r.deleted_at IS NULL""",
            (record_id,),
        ).fetchone()

    if not row:
        return jsonify({"error": "Record not found"}), 404

    return jsonify({"record": dict(row)}), 200


# ---------------------------------------------------------------------------
# Create record — analyst+
# ---------------------------------------------------------------------------

@records_bp.route("/", methods=["POST"])
@require_auth
@require_role("analyst")
def create_record():
    """POST /records/  —  Available to analysts and admins."""
    data = request.get_json(silent=True) or {}

    try:
        cleaned = validate_create_record(data)
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "fields": e.errors}), 422

    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO financial_records
               (amount, type, category, date, notes, created_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                cleaned["amount"],
                cleaned["type"],
                cleaned["category"],
                cleaned["date"],
                cleaned["notes"],
                current_user_id(),
            ),
        )
        record = row_to_dict(
            conn.execute(
                "SELECT * FROM financial_records WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        )

    return jsonify({"message": "Record created", "record": record}), 201


# ---------------------------------------------------------------------------
# Update record — admin only
# ---------------------------------------------------------------------------

@records_bp.route("/<int:record_id>", methods=["PATCH"])
@require_auth
@require_role("admin")
def update_record(record_id):
    """PATCH /records/<id>  —  Admin only."""
    data = request.get_json(silent=True) or {}

    try:
        cleaned = validate_update_record(data)
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "fields": e.errors}), 422

    if not cleaned:
        return jsonify({"error": "No valid fields provided for update"}), 400

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM financial_records WHERE id = ? AND deleted_at IS NULL",
            (record_id,),
        ).fetchone()
        if not existing:
            return jsonify({"error": "Record not found"}), 404

        set_clause = ", ".join(f"{col} = ?" for col in cleaned)
        set_clause += ", updated_at = datetime('now')"
        values     = list(cleaned.values()) + [record_id]
        conn.execute(
            f"UPDATE financial_records SET {set_clause} WHERE id = ?", values
        )
        record = row_to_dict(
            conn.execute(
                "SELECT * FROM financial_records WHERE id = ?", (record_id,)
            ).fetchone()
        )

    return jsonify({"message": "Record updated", "record": record}), 200


# ---------------------------------------------------------------------------
# Soft delete — admin only
# ---------------------------------------------------------------------------

@records_bp.route("/<int:record_id>", methods=["DELETE"])
@require_auth
@require_role("admin")
def delete_record(record_id):
    """DELETE /records/<id>  —  Soft delete (admin only)."""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM financial_records WHERE id = ? AND deleted_at IS NULL",
            (record_id,),
        ).fetchone()
        if not existing:
            return jsonify({"error": "Record not found"}), 404

        conn.execute(
            "UPDATE financial_records SET deleted_at = datetime('now') WHERE id = ?",
            (record_id,),
        )

    return jsonify({"message": "Record deleted"}), 200
