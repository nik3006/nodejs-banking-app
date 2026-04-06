import hashlib
import hmac
import os
import time
import base64
import json
from config import Config


# ---------------------------------------------------------------------------
# Password hashing  (PBKDF2-SHA256, stdlib only — no bcrypt needed)
# ---------------------------------------------------------------------------

ITERATIONS = 260_000
HASH_NAME   = "sha256"


def hash_password(plaintext: str) -> str:
    """Return a salted PBKDF2 hash encoded as 'algo$iterations$salt$hash'."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac(HASH_NAME, plaintext.encode(), salt, ITERATIONS)
    salt_b64 = base64.b64encode(salt).decode()
    hash_b64  = base64.b64encode(dk).decode()
    return f"pbkdf2_{HASH_NAME}${ITERATIONS}${salt_b64}${hash_b64}"


def verify_password(plaintext: str, stored_hash: str) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    try:
        algo, iterations, salt_b64, hash_b64 = stored_hash.split("$")
        salt = base64.b64decode(salt_b64)
        iters = int(iterations)
        name = algo.replace("pbkdf2_", "")
        dk_attempt = hashlib.pbkdf2_hmac(name, plaintext.encode(), salt, iters)
        dk_stored  = base64.b64decode(hash_b64)
        return hmac.compare_digest(dk_attempt, dk_stored)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT  (hand-rolled HS256 — avoids third-party dep for core logic demo)
# ---------------------------------------------------------------------------

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * padding)


def create_token(user: dict) -> str:
    """Create a signed HS256 JWT containing user id, role, and expiry."""
    header  = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    expiry  = int(time.time()) + Config.JWT_EXPIRY_HOURS * 3600
    payload = _b64url_encode(json.dumps({
        "sub":      user["id"],
        "username": user["username"],
        "role":     user["role"],
        "exp":      expiry,
        "iat":      int(time.time()),
    }).encode())

    signing_input = f"{header}.{payload}"
    sig = hmac.new(
        Config.JWT_SECRET.encode(),
        signing_input.encode(),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64url_encode(sig)}"


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT.
    Raises ValueError with a descriptive message on failure.
    """
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError:
        raise ValueError("Malformed token")

    signing_input = f"{header_b64}.{payload_b64}"
    expected_sig = hmac.new(
        Config.JWT_SECRET.encode(),
        signing_input.encode(),
        hashlib.sha256,
    ).digest()

    try:
        actual_sig = _b64url_decode(sig_b64)
    except Exception:
        raise ValueError("Malformed token signature")

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("Invalid token signature")

    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception:
        raise ValueError("Malformed token payload")

    if payload.get("exp", 0) < time.time():
        raise ValueError("Token has expired")

    return payload
