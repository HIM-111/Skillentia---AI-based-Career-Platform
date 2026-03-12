import os
import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UserContextService:
    _fernet: Optional[Fernet] = None

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
    def _get_fernet() -> Fernet:
        if UserContextService._fernet is not None:
            return UserContextService._fernet

        if settings.CONTEXT_ENCRYPTION_KEY:
            UserContextService._fernet = Fernet(settings.CONTEXT_ENCRYPTION_KEY.encode("utf-8"))
            return UserContextService._fernet

        key_path = settings.CONTEXT_KEY_PATH
        key_dir = os.path.dirname(key_path)
        if key_dir:
            os.makedirs(key_dir, exist_ok=True)

        if os.path.exists(key_path):
            with open(key_path, "rb") as file:
                key = file.read().strip()
        else:
            key = Fernet.generate_key()
            with open(key_path, "wb") as file:
                file.write(key)
            try:
                os.chmod(key_path, 0o600)
            except OSError:
                pass

        UserContextService._fernet = Fernet(key)
        return UserContextService._fernet

    @staticmethod
    def init_db() -> None:
        with UserContextService._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_contexts (
                    user_id INTEGER PRIMARY KEY,
                    resume_encrypted TEXT,
                    job_description_encrypted TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_artifacts (
                    user_id INTEGER PRIMARY KEY,
                    cover_letter_encrypted TEXT,
                    updated_resume_encrypted TEXT,
                    gap_analysis_encrypted TEXT,
                    job_listings_encrypted TEXT,
                    job_listings_updated_at TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
                """
            )
            UserContextService._ensure_user_artifact_columns(conn)
            conn.commit()

    @staticmethod
    def _ensure_user_artifact_columns(conn: sqlite3.Connection) -> None:
        existing_cols = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(user_artifacts)").fetchall()
        }

        if "job_listings_encrypted" not in existing_cols:
            conn.execute("ALTER TABLE user_artifacts ADD COLUMN job_listings_encrypted TEXT")
        if "job_listings_updated_at" not in existing_cols:
            conn.execute("ALTER TABLE user_artifacts ADD COLUMN job_listings_updated_at TEXT")

    @staticmethod
    def _encrypt(value: str) -> str:
        if not value:
            return ""
        token = UserContextService._get_fernet().encrypt(value.encode("utf-8"))
        return token.decode("utf-8")

    @staticmethod
    def _decrypt(value: str) -> str:
        if not value:
            return ""
        try:
            plain = UserContextService._get_fernet().decrypt(value.encode("utf-8"))
            return plain.decode("utf-8")
        except (InvalidToken, ValueError):
            return ""

    @staticmethod
    def get_context(user_id: int) -> dict:
        UserContextService.init_db()
        with UserContextService._connect() as conn:
            row = conn.execute(
                """
                SELECT resume_encrypted, job_description_encrypted
                FROM user_contexts
                WHERE user_id = ?
                """,
                (user_id,)
            ).fetchone()

        if not row:
            return {"resume_text": "", "job_description": ""}

        return {
            "resume_text": UserContextService._decrypt(row["resume_encrypted"] or ""),
            "job_description": UserContextService._decrypt(row["job_description_encrypted"] or ""),
        }

    @staticmethod
    def save_context(
        user_id: int,
        resume_text: Optional[str] = None,
        job_description: Optional[str] = None
    ) -> dict:
        UserContextService.init_db()

        current = UserContextService.get_context(user_id)
        next_resume = current["resume_text"] if resume_text is None else resume_text
        next_jd = current["job_description"] if job_description is None else job_description

        encrypted_resume = UserContextService._encrypt(next_resume)
        encrypted_jd = UserContextService._encrypt(next_jd)

        with UserContextService._connect() as conn:
            exists = conn.execute(
                "SELECT user_id FROM user_contexts WHERE user_id = ?",
                (user_id,)
            ).fetchone()

            if exists:
                conn.execute(
                    """
                    UPDATE user_contexts
                    SET resume_encrypted = ?, job_description_encrypted = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (encrypted_resume, encrypted_jd, _utc_now_iso(), user_id)
                )
            else:
                conn.execute(
                    """
                    INSERT INTO user_contexts (user_id, resume_encrypted, job_description_encrypted, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, encrypted_resume, encrypted_jd, _utc_now_iso())
                )
            conn.commit()

        return {"resume_text": next_resume, "job_description": next_jd}

    @staticmethod
    def clear_resume(user_id: int) -> dict:
        return UserContextService.save_context(user_id=user_id, resume_text="")

    @staticmethod
    def get_artifacts(user_id: int) -> dict:
        UserContextService.init_db()
        with UserContextService._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    cover_letter_encrypted,
                    updated_resume_encrypted,
                    gap_analysis_encrypted,
                    job_listings_encrypted,
                    job_listings_updated_at,
                    updated_at
                FROM user_artifacts
                WHERE user_id = ?
                """,
                (user_id,)
            ).fetchone()

        if not row:
            return {
                "cover_letter": "",
                "updated_resume": "",
                "gap_analysis": {},
                "job_listings": {},
                "job_listings_updated_at": "",
                "updated_at": ""
            }

        gap_raw = UserContextService._decrypt(row["gap_analysis_encrypted"] or "")
        gap_analysis = {}
        if gap_raw:
            try:
                parsed = json.loads(gap_raw)
                if isinstance(parsed, dict):
                    gap_analysis = parsed
            except json.JSONDecodeError:
                gap_analysis = {}

        jobs_raw = UserContextService._decrypt(row["job_listings_encrypted"] or "")
        job_listings = {}
        if jobs_raw:
            try:
                parsed_jobs = json.loads(jobs_raw)
                if isinstance(parsed_jobs, dict):
                    job_listings = parsed_jobs
            except json.JSONDecodeError:
                job_listings = {}

        return {
            "cover_letter": UserContextService._decrypt(row["cover_letter_encrypted"] or ""),
            "updated_resume": UserContextService._decrypt(row["updated_resume_encrypted"] or ""),
            "gap_analysis": gap_analysis,
            "job_listings": job_listings,
            "job_listings_updated_at": str(row["job_listings_updated_at"] or ""),
            "updated_at": str(row["updated_at"] or "")
        }

    @staticmethod
    def save_artifacts(
        user_id: int,
        cover_letter: Optional[str] = None,
        updated_resume: Optional[str] = None,
        gap_analysis: Optional[dict] = None,
        job_listings: Optional[dict] = None
    ) -> dict:
        UserContextService.init_db()

        current = UserContextService.get_artifacts(user_id)
        next_cover_letter = current["cover_letter"] if cover_letter is None else cover_letter
        next_updated_resume = current["updated_resume"] if updated_resume is None else updated_resume
        next_gap_analysis = current["gap_analysis"] if gap_analysis is None else gap_analysis
        next_job_listings = current["job_listings"] if job_listings is None else job_listings

        if not isinstance(next_gap_analysis, dict):
            next_gap_analysis = {}
        if not isinstance(next_job_listings, dict):
            next_job_listings = {}

        encrypted_cover_letter = UserContextService._encrypt(next_cover_letter)
        encrypted_updated_resume = UserContextService._encrypt(next_updated_resume)
        encrypted_gap_analysis = UserContextService._encrypt(json.dumps(next_gap_analysis))
        encrypted_job_listings = UserContextService._encrypt(json.dumps(next_job_listings))
        if job_listings is None:
            next_job_listings_updated_at = current.get("job_listings_updated_at", "")
        elif next_job_listings:
            next_job_listings_updated_at = _utc_now_iso()
        else:
            next_job_listings_updated_at = ""

        with UserContextService._connect() as conn:
            exists = conn.execute(
                "SELECT user_id FROM user_artifacts WHERE user_id = ?",
                (user_id,)
            ).fetchone()

            if exists:
                conn.execute(
                    """
                    UPDATE user_artifacts
                    SET cover_letter_encrypted = ?, updated_resume_encrypted = ?, gap_analysis_encrypted = ?, job_listings_encrypted = ?, job_listings_updated_at = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (
                        encrypted_cover_letter,
                        encrypted_updated_resume,
                        encrypted_gap_analysis,
                        encrypted_job_listings,
                        next_job_listings_updated_at,
                        _utc_now_iso(),
                        user_id
                    )
                )
            else:
                conn.execute(
                    """
                    INSERT INTO user_artifacts (
                        user_id,
                        cover_letter_encrypted,
                        updated_resume_encrypted,
                        gap_analysis_encrypted,
                        job_listings_encrypted,
                        job_listings_updated_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        encrypted_cover_letter,
                        encrypted_updated_resume,
                        encrypted_gap_analysis,
                        encrypted_job_listings,
                        next_job_listings_updated_at,
                        _utc_now_iso()
                    )
                )
            conn.commit()

        return {
            "cover_letter": next_cover_letter,
            "updated_resume": next_updated_resume,
            "gap_analysis": next_gap_analysis,
            "job_listings": next_job_listings,
            "job_listings_updated_at": next_job_listings_updated_at
        }
