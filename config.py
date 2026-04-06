import os


class Config:
    # Change this to a long random string in production
    JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
    JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", 24))

    DATABASE_PATH = os.environ.get("DATABASE_PATH", "finance.db")

    # Role hierarchy — higher value = more permissions
    ROLES = {
        "viewer":  1,
        "analyst": 2,
        "admin":   3,
    }
