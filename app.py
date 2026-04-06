from flask import Flask, jsonify
from config import Config
from db import init_db
from routes.auth import auth_bp
from routes.users import users_bp
from routes.records import records_bp
from routes.dashboard import dashboard_bp


def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)

    init_db()

    app.register_blueprint(auth_bp,      url_prefix="/auth")
    app.register_blueprint(users_bp,     url_prefix="/users")
    app.register_blueprint(records_bp,   url_prefix="/records")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"error": "Route not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "Internal server error", "detail": str(e)}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    print("Finance Backend running on http://localhost:5000")
    print("Seed data loaded — see README for default credentials.")
    app.run(debug=True, port=5000)
