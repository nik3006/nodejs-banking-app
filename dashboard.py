from flask import Blueprint, request, jsonify
from db import get_db, rows_to_list
from middleware import require_auth, require_role

dashboard_bp = Blueprint("dashboard", __name__)


# ---------------------------------------------------------------------------
# Summary — viewer+
# ---------------------------------------------------------------------------

@dashboard_bp.route("/summary", methods=["GET"])
@require_auth
@require_role("viewer")
def summary():
    """
    GET /dashboard/summary
    Returns total income, total expenses, net balance, and record count.
    Optional query params: from_date, to_date (YYYY-MM-DD)
    """
    from_date = request.args.get("from_date")
    to_date   = request.args.get("to_date")

    conditions = ["deleted_at IS NULL"]
    params     = []
    if from_date:
        conditions.append("date >= ?")
        params.append(from_date)
    if to_date:
        conditions.append("date <= ?")
        params.append(to_date)
    where = " AND ".join(conditions)

    with get_db() as conn:
        row = conn.execute(
            f"""SELECT
                    COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0) AS total_income,
                    COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) AS total_expenses,
                    COUNT(*) AS record_count
                FROM financial_records
                WHERE {where}""",
            params,
        ).fetchone()

    total_income   = round(row["total_income"],   2)
    total_expenses = round(row["total_expenses"], 2)

    return jsonify({
        "summary": {
            "total_income":   total_income,
            "total_expenses": total_expenses,
            "net_balance":    round(total_income - total_expenses, 2),
            "record_count":   row["record_count"],
            "period": {
                "from": from_date or "all time",
                "to":   to_date   or "all time",
            },
        }
    }), 200


# ---------------------------------------------------------------------------
# Category breakdown — viewer+
# ---------------------------------------------------------------------------

@dashboard_bp.route("/categories", methods=["GET"])
@require_auth
@require_role("viewer")
def category_breakdown():
    """
    GET /dashboard/categories
    Returns income and expense totals grouped by category.
    Optional: ?type=income|expense to narrow down.
    """
    record_type = request.args.get("type")
    conditions  = ["deleted_at IS NULL"]
    params      = []
    if record_type in ("income", "expense"):
        conditions.append("type = ?")
        params.append(record_type)

    where = " AND ".join(conditions)

    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT
                    category,
                    type,
                    ROUND(SUM(amount), 2) AS total,
                    COUNT(*) AS count
                FROM financial_records
                WHERE {where}
                GROUP BY category, type
                ORDER BY total DESC""",
            params,
        ).fetchall()

    return jsonify({"categories": rows_to_list(rows)}), 200


# ---------------------------------------------------------------------------
# Monthly trends — analyst+
# ---------------------------------------------------------------------------

@dashboard_bp.route("/trends", methods=["GET"])
@require_auth
@require_role("analyst")
def monthly_trends():
    """
    GET /dashboard/trends
    Returns monthly income and expense totals for the past N months.
    Optional: ?months=12 (default 12, max 60)
    """
    try:
        months = min(60, max(1, int(request.args.get("months", 12))))
    except ValueError:
        return jsonify({"error": "months must be an integer"}), 422

    with get_db() as conn:
        rows = conn.execute(
            """SELECT
                   strftime('%Y-%m', date) AS month,
                   ROUND(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 2) AS income,
                   ROUND(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 2) AS expenses,
                   ROUND(
                       SUM(CASE WHEN type='income'  THEN amount ELSE 0 END) -
                       SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),
                   2) AS net
               FROM financial_records
               WHERE deleted_at IS NULL
                 AND date >= date('now', ? || ' months')
               GROUP BY month
               ORDER BY month ASC""",
            (f"-{months}",),
        ).fetchall()

    return jsonify({"trends": rows_to_list(rows), "months": months}), 200


# ---------------------------------------------------------------------------
# Recent activity — viewer+
# ---------------------------------------------------------------------------

@dashboard_bp.route("/recent", methods=["GET"])
@require_auth
@require_role("viewer")
def recent_activity():
    """
    GET /dashboard/recent
    Returns the most recent N records.
    Optional: ?limit=10 (default 10, max 50)
    """
    try:
        limit = min(50, max(1, int(request.args.get("limit", 10))))
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 422

    with get_db() as conn:
        rows = conn.execute(
            """SELECT r.id, r.amount, r.type, r.category, r.date, r.notes,
                      u.username as created_by
               FROM financial_records r
               JOIN users u ON r.created_by = u.id
               WHERE r.deleted_at IS NULL
               ORDER BY r.date DESC, r.id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

    return jsonify({"recent": rows_to_list(rows), "limit": limit}), 200


# ---------------------------------------------------------------------------
# Top categories — analyst+
# ---------------------------------------------------------------------------

@dashboard_bp.route("/insights", methods=["GET"])
@require_auth
@require_role("analyst")
def insights():
    """
    GET /dashboard/insights  (analyst+ only)
    Returns top spending categories and income sources, plus a savings rate.
    """
    with get_db() as conn:
        totals = conn.execute(
            """SELECT
                   COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0) AS income,
                   COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) AS expenses
               FROM financial_records WHERE deleted_at IS NULL"""
        ).fetchone()

        top_expenses = conn.execute(
            """SELECT category, ROUND(SUM(amount), 2) AS total
               FROM financial_records
               WHERE type = 'expense' AND deleted_at IS NULL
               GROUP BY category ORDER BY total DESC LIMIT 5"""
        ).fetchall()

        top_income = conn.execute(
            """SELECT category, ROUND(SUM(amount), 2) AS total
               FROM financial_records
               WHERE type = 'income' AND deleted_at IS NULL
               GROUP BY category ORDER BY total DESC LIMIT 5"""
        ).fetchall()

    income   = totals["income"]
    expenses = totals["expenses"]
    savings_rate = round((income - expenses) / income * 100, 1) if income > 0 else 0

    return jsonify({
        "insights": {
            "savings_rate_pct":  savings_rate,
            "top_expense_categories": rows_to_list(top_expenses),
            "top_income_sources":     rows_to_list(top_income),
        }
    }), 200
