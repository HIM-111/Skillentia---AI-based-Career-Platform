import hashlib
from typing import Any

from app.services.ats_scorer import ATSScorer
from app.services.resume_updater import ResumeUpdater
from app.services.skill_gap import SkillGapAnalyzer
from app.services.user_context_service import UserContextService

UPDATED_RESUME_TEMPLATE_VERSION = 7


def _hash_text(*parts: str) -> str:
    normalized = []
    for part in parts:
        text = (part or "").replace("\r\n", "\n").replace("\r", "\n")
        text = " ".join(text.split())
        normalized.append(text.strip())
    joined = "||".join(normalized)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


class AnalysisStateService:
    @staticmethod
    def _normalize_state(raw: dict[str, Any] | None) -> dict[str, Any]:
        payload = raw if isinstance(raw, dict) else {}

        # Backward compatibility: old payload may be plain analysis output.
        if (
            "current_analysis" in payload
            or "context_hash" in payload
            or "cover_letter_context_hash" in payload
        ):
            current = payload.get("current_analysis")
            updated = payload.get("updated_analysis")
            return {
                "context_hash": str(payload.get("context_hash", "")),
                "current_analysis": current if isinstance(current, dict) else {},
                "current_ats_score": payload.get("current_ats_score"),
                "updated_resume_hash": str(payload.get("updated_resume_hash", "")),
                "updated_analysis": updated if isinstance(updated, dict) else {},
                "updated_ats_score": payload.get("updated_ats_score"),
                "cover_letter_context_hash": str(payload.get("cover_letter_context_hash", "")),
                "updated_resume_template_version": int(payload.get("updated_resume_template_version", 0) or 0)
            }

        if payload.get("matching_skills") is not None and payload.get("missing_skills") is not None:
            score = payload.get("readiness_score", 0)
            return {
                "context_hash": "",
                "current_analysis": payload,
                "current_ats_score": score,
                "updated_resume_hash": "",
                "updated_analysis": {},
                "updated_ats_score": None,
                "cover_letter_context_hash": "",
                "updated_resume_template_version": 0
            }

        return {
            "context_hash": "",
            "current_analysis": {},
            "current_ats_score": None,
            "updated_resume_hash": "",
            "updated_analysis": {},
            "updated_ats_score": None,
            "cover_letter_context_hash": "",
            "updated_resume_template_version": 0
        }

    @staticmethod
    def get_cached_state(user_id: int, resume_text: str, job_description: str) -> tuple[dict[str, Any], dict[str, Any]]:
        artifacts = UserContextService.get_artifacts(user_id)
        state = AnalysisStateService._normalize_state(artifacts.get("gap_analysis"))
        requested_hash = _hash_text(resume_text, job_description)

        if state.get("context_hash") != requested_hash:
            state["context_hash"] = ""
            state["current_analysis"] = {}
            state["current_ats_score"] = None
            state["updated_analysis"] = {}
            state["updated_ats_score"] = None
            state["updated_resume_hash"] = ""
            state["updated_resume_template_version"] = 0

        if state.get("cover_letter_context_hash") != requested_hash:
            state["cover_letter_context_hash"] = ""

        cover_letter_text = (artifacts.get("cover_letter") or "").strip()
        if (
            not state.get("cover_letter_context_hash")
            and state.get("context_hash") == requested_hash
            and cover_letter_text
        ):
            state["cover_letter_context_hash"] = requested_hash

        updated_resume_text = (artifacts.get("updated_resume") or "").strip()
        if (
            not state.get("updated_resume_hash")
            and state.get("context_hash") == requested_hash
            and updated_resume_text
        ):
            state["updated_resume_hash"] = _hash_text(updated_resume_text)

        if state.get("context_hash") == requested_hash and state.get("current_analysis"):
            current_ats = state.get("current_ats_score")
            if not isinstance(current_ats, int):
                current_ats = ATSScorer.score_resume_for_job(resume_text, job_description)
                state["current_ats_score"] = current_ats
            state["current_analysis"]["ats_score"] = current_ats

        if state.get("updated_analysis"):
            updated_ats = state.get("updated_ats_score")
            if isinstance(updated_ats, int):
                state["updated_analysis"]["ats_score"] = updated_ats

        return artifacts, state

    @staticmethod
    def ensure_current_analysis(user_id: int, resume_text: str, job_description: str) -> tuple[dict[str, Any], dict[str, Any]]:
        artifacts, state = AnalysisStateService.get_cached_state(user_id, resume_text, job_description)
        current = state.get("current_analysis", {})
        if current:
            return current, state

        analysis = SkillGapAnalyzer.analyze(resume_text, job_description)
        ats_score = ATSScorer.score_resume_for_job(resume_text, job_description)
        analysis["ats_score"] = ats_score
        next_state = {
            "context_hash": _hash_text(resume_text, job_description),
            "current_analysis": analysis,
            "current_ats_score": ats_score,
            "updated_resume_hash": "",
            "updated_analysis": {},
            "updated_ats_score": None,
            "cover_letter_context_hash": state.get("cover_letter_context_hash", ""),
            "updated_resume_template_version": 0
        }
        UserContextService.save_artifacts(user_id=user_id, gap_analysis=next_state)
        return analysis, next_state

    @staticmethod
    def ensure_updated_resume(user_id: int, resume_text: str, job_description: str) -> dict[str, Any]:
        artifacts, state = AnalysisStateService.get_cached_state(user_id, resume_text, job_description)
        baseline = state.get("current_analysis", {})
        if not baseline:
            baseline, state = AnalysisStateService.ensure_current_analysis(
                user_id=user_id,
                resume_text=resume_text,
                job_description=job_description
            )
            artifacts = UserContextService.get_artifacts(user_id)

        baseline_score = int(state.get("current_ats_score") or ATSScorer.score_resume_for_job(resume_text, job_description))
        baseline["ats_score"] = baseline_score
        existing_updated = (artifacts.get("updated_resume") or "").strip()
        existing_hash = _hash_text(existing_updated)

        cached_updated_analysis = state.get("updated_analysis", {})
        if (
            existing_updated
            and state.get("updated_resume_hash") == existing_hash
            and cached_updated_analysis
            and int(state.get("updated_resume_template_version", 0) or 0) == UPDATED_RESUME_TEMPLATE_VERSION
        ):
            updated_score = int(state.get("updated_ats_score", cached_updated_analysis.get("readiness_score", 0)))
            return {
                "updated_resume": existing_updated,
                "baseline_analysis": baseline,
                "updated_analysis": cached_updated_analysis,
                "ats_current_score": baseline_score,
                "ats_updated_score": updated_score,
                "ats_score_delta": updated_score - baseline_score
            }

        missing_skills = baseline.get("missing_skills", [])
        primary = ResumeUpdater.update(
            resume_text=resume_text,
            missing_skills=missing_skills,
            job_description=job_description,
            matched_skills=baseline.get("matching_skills", [])
        ).strip()
        fallback = ResumeUpdater.strict_ats_reformat(resume_text).strip()
        original = (resume_text or "").strip()

        candidates = []
        for candidate in [primary, fallback, original]:
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        best_resume = original
        best_analysis = dict(baseline)
        best_score = baseline_score

        for candidate in candidates:
            analysis = SkillGapAnalyzer.analyze(candidate, job_description)
            score = ATSScorer.score_resume_for_job(candidate, job_description)
            analysis["ats_score"] = score
            if score > best_score:
                best_resume = candidate
                best_analysis = analysis
                best_score = score

        next_state = {
            "context_hash": _hash_text(resume_text, job_description),
            "current_analysis": baseline,
            "current_ats_score": baseline_score,
            "updated_resume_hash": _hash_text(best_resume),
            "updated_analysis": best_analysis,
            "updated_ats_score": best_score,
            "cover_letter_context_hash": state.get("cover_letter_context_hash", ""),
            "updated_resume_template_version": UPDATED_RESUME_TEMPLATE_VERSION
        }
        UserContextService.save_artifacts(
            user_id=user_id,
            updated_resume=best_resume,
            gap_analysis=next_state
        )

        return {
            "updated_resume": best_resume,
            "baseline_analysis": baseline,
            "updated_analysis": best_analysis,
            "ats_current_score": baseline_score,
            "ats_updated_score": best_score,
            "ats_score_delta": best_score - baseline_score
        }

    @staticmethod
    def tag_cover_letter_context(user_id: int, resume_text: str, job_description: str) -> None:
        artifacts = UserContextService.get_artifacts(user_id)
        state = AnalysisStateService._normalize_state(artifacts.get("gap_analysis"))
        state["cover_letter_context_hash"] = _hash_text(resume_text, job_description)
        UserContextService.save_artifacts(user_id=user_id, gap_analysis=state)
