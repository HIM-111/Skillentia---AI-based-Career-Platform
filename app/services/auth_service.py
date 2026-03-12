import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.config import settings


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuthService:
    @staticmethod
    def _connect() -> sqlite3.Connection:
        db_path = settings.AUTH_DB_PATH
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def init_db() -> None:
        with AuthService._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
                """
            )
            conn.commit()

    @staticmethod
    def _hash_password(password: str, salt: Optional[str] = None) -> str:
        salt_bytes = os.urandom(16) if salt is None else bytes.fromhex(salt)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt_bytes,
            120_000
        )
        return f"{salt_bytes.hex()}${digest.hex()}"

    @staticmethod
    def _verify_password(password: str, stored: str) -> bool:
        if "$" not in stored:
            return False
        salt, current = stored.split("$", 1)
        candidate = AuthService._hash_password(password, salt)
        return secrets.compare_digest(candidate.split("$", 1)[1], current)

    @staticmethod
    def signup(email: str, password: str) -> dict:
        AuthService.init_db()
        normalized = email.strip().lower()
        if not normalized or "@" not in normalized:
            raise ValueError("Please provide a valid email address.")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")

        password_hash = AuthService._hash_password(password)
        created_at = _utc_now().isoformat()

        with AuthService._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM users WHERE email = ?",
                (normalized,)
            ).fetchone()
            if existing:
                raise ValueError("An account with this email already exists.")

            cursor = conn.execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (normalized, password_hash, created_at)
            )
            conn.commit()
            user_id = int(cursor.lastrowid)

        token = AuthService._create_session(user_id)
        return {"token": token, "user": {"id": user_id, "email": normalized}}

    @staticmethod
    def login(email: str, password: str) -> dict:
        AuthService.init_db()
        normalized = email.strip().lower()

        with AuthService._connect() as conn:
            user = conn.execute(
                "SELECT id, email, password_hash FROM users WHERE email = ?",
                (normalized,)
            ).fetchone()

        if not user or not AuthService._verify_password(password, user["password_hash"]):
            raise ValueError("Invalid email or password.")

        token = AuthService._create_session(int(user["id"]))
        return {
            "token": token,
            "user": {"id": int(user["id"]), "email": str(user["email"])}
        }

    @staticmethod
    def _create_session(user_id: int) -> str:
        token = secrets.token_urlsafe(36)
        created_at = _utc_now()
        expires_at = created_at + timedelta(hours=settings.AUTH_SESSION_HOURS)

        with AuthService._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (token, user_id, created_at.isoformat(), expires_at.isoformat())
            )
            conn.commit()

        return token

    @staticmethod
    def get_user_from_token(token: str) -> Optional[dict]:
        AuthService.init_db()
        if not token:
            return None

        with AuthService._connect() as conn:
            row = conn.execute(
                """
                SELECT u.id as user_id, u.email as email, s.expires_at as expires_at
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = ?
                """,
                (token,)
            ).fetchone()

            if not row:
                return None

            expires_at = datetime.fromisoformat(row["expires_at"])
            if expires_at <= _utc_now():
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                conn.commit()
                return None

            return {"id": int(row["user_id"]), "email": str(row["email"])}

    @staticmethod
    def logout(token: str) -> None:
        if not token:
            return
        AuthService.init_db()
        with AuthService._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
