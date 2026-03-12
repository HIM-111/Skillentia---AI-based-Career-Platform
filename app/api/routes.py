import hashlib

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.services.analysis_state_service import AnalysisStateService
from app.services.auth_service import AuthService
from app.services.cover_letter import CoverLetterGenerator
from app.services.job_recommender import JobRecommender
from app.services.resume_parser import ResumeParser
from app.services.user_context_service import UserContextService

router = APIRouter()


class SkillGapRequest(BaseModel):
    resume_text: str
    job_description: str


class AuthRequest(BaseModel):
    email: str
    password: str


class ResumeUpdateRequest(BaseModel):
    resume_text: str
    job_description: str


class JobRecommendationRequest(BaseModel):
    resume_text: str
    job_description: str
    limit: int = 5


class UserContextUpdateRequest(BaseModel):
    resume_text: str | None = None
    job_description: str | None = None


class DashboardResponse(BaseModel):
    has_context: bool
    resume_ats_score: int | None = None
    updated_resume_ats_score: int | None = None
    updated_resume: str = ""
    cover_letter: str = ""
    current_analysis: dict = Field(default_factory=dict)
    skills_to_develop: list[str] = Field(default_factory=list)
    development_plan: list[str] = Field(default_factory=list)
    prioritized_gaps: list[dict] = Field(default_factory=list)
    recommendations: str = ""
    top_job_listings: list[dict] = Field(default_factory=list)
    job_listings_updated_at: str = ""
    artifact_updated_at: str = ""


def _extract_bearer_token(authorization: str) -> str:
    value = (authorization or "").strip()
    if not value.lower().startswith("bearer "):
        return ""
    return value.split(" ", 1)[1].strip()


def _context_hash(*parts: str) -> str:
    normalized = []
    for part in parts:
        text = (part or "").replace("\r\n", "\n").replace("\r", "\n")
        text = " ".join(text.split())
        normalized.append(text.strip())
    joined = "||".join(normalized)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def get_current_user(authorization: str = Header(default="")):
    token = _extract_bearer_token(authorization)
    user = AuthService.get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user


@router.post("/auth/signup")
def signup(payload: AuthRequest):
    try:
        return AuthService.signup(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/auth/login")
def login(payload: AuthRequest):
    try:
        return AuthService.login(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.get("/auth/me")
def me(user=Depends(get_current_user)):
    return {"user": user}


@router.post("/auth/logout")
def logout(authorization: str = Header(default=""), user=Depends(get_current_user)):
    token = _extract_bearer_token(authorization)
    AuthService.logout(token)
    return {"message": "Logged out."}


@router.post("/resume-upload")
async def upload_resume(file: UploadFile = File(...), user=Depends(get_current_user)):
    filename = file.filename or ""
    if "." not in filename:
        raise HTTPException(status_code=400, detail="File must have an extension")

    extension = filename.rsplit(".", 1)[-1].lower()
    if extension not in {"pdf", "docx", "doc", "docs", "txt"}:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Please upload a PDF, DOCX, DOC/DOCS, or TXT file."
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    resume_text = ResumeParser.parse(file_bytes, extension)
    if not resume_text:
        raise HTTPException(
            status_code=422,
            detail="Unable to extract text from the resume. Please try another file."
        )

    UserContextService.save_context(user_id=user["id"], resume_text=resume_text)

    return {"resume_text": resume_text}


@router.get("/context")
def get_user_context(user=Depends(get_current_user)):
    return UserContextService.get_context(user_id=user["id"])


@router.put("/context")
def save_user_context(payload: UserContextUpdateRequest, user=Depends(get_current_user)):
    if payload.resume_text is None and payload.job_description is None:
        raise HTTPException(status_code=400, detail="Provide resume_text and/or job_description.")

    return UserContextService.save_context(
        user_id=user["id"],
        resume_text=payload.resume_text,
        job_description=payload.job_description
    )


@router.delete("/context/resume")
def clear_user_resume_context(user=Depends(get_current_user)):
    return UserContextService.clear_resume(user_id=user["id"])


@router.post("/skill-gap")
def analyze_skill_gap(payload: SkillGapRequest, user=Depends(get_current_user)):
    analysis, _state = AnalysisStateService.ensure_current_analysis(
        user_id=user["id"],
        resume_text=payload.resume_text,
        job_description=payload.job_description
    )
    return analysis


@router.post("/cover-letter")
def generate_cover_letter(payload: SkillGapRequest, user=Depends(get_current_user)):
    try:
        cover_letter = CoverLetterGenerator.generate(payload.resume_text, payload.job_description)
        UserContextService.save_artifacts(user_id=user["id"], cover_letter=cover_letter)
        AnalysisStateService.tag_cover_letter_context(
            user_id=user["id"],
            resume_text=payload.resume_text,
            job_description=payload.job_description
        )
        return {"cover_letter": cover_letter}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Cover letter generation failed: {exc}")


@router.post("/resume-update")
def update_resume(payload: ResumeUpdateRequest, user=Depends(get_current_user)):
    try:
        result = AnalysisStateService.ensure_updated_resume(
            user_id=user["id"],
            resume_text=payload.resume_text,
            job_description=payload.job_description
        )
        baseline_gap = result["baseline_analysis"]
        return {
            "updated_resume": result["updated_resume"],
            "missing_skills": baseline_gap.get("missing_skills", []),
            "ats_current_score": result["ats_current_score"],
            "ats_updated_score": result["ats_updated_score"],
            "ats_score_delta": result["ats_score_delta"]
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Resume update failed: {exc}")


@router.post("/job-recommendations")
def recommend_jobs(payload: JobRecommendationRequest, user=Depends(get_current_user)):
    try:
        response = JobRecommender.recommend_jobs(
            resume_text=payload.resume_text,
            job_description=payload.job_description,
            limit=payload.limit
        )
        UserContextService.save_artifacts(
            user_id=user["id"],
            job_listings={
                "context_hash": _context_hash(payload.resume_text, payload.job_description),
                "payload": response
            }
        )
        return response
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Job recommendations failed: {exc}")


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(user=Depends(get_current_user)):
    context = UserContextService.get_context(user_id=user["id"])
    artifacts = UserContextService.get_artifacts(user_id=user["id"])

    resume_text = (context.get("resume_text") or "").strip()
    job_description = (context.get("job_description") or "").strip()

    if not resume_text or not job_description:
        return DashboardResponse(
            has_context=False,
            cover_letter="",
            updated_resume="",
            current_analysis={},
            artifact_updated_at=artifacts.get("updated_at", "")
        )

    _, state = AnalysisStateService.get_cached_state(
        user_id=user["id"],
        resume_text=resume_text,
        job_description=job_description
    )
    requested_hash = _context_hash(resume_text, job_description)
    current_gap = state.get("current_analysis", {})
    updated_resume = artifacts.get("updated_resume", "") if state.get("updated_resume_hash") else ""
    cover_letter = artifacts.get("cover_letter", "") if state.get("cover_letter_context_hash") else ""
    stored_jobs = artifacts.get("job_listings", {})
    stored_jobs_payload = {}
    if (
        isinstance(stored_jobs, dict)
        and stored_jobs.get("context_hash") == requested_hash
        and isinstance(stored_jobs.get("payload"), dict)
    ):
        stored_jobs_payload = stored_jobs.get("payload", {})
    top_jobs = (stored_jobs_payload.get("jobs", []) if isinstance(stored_jobs_payload, dict) else [])[:3]
    if not isinstance(top_jobs, list):
        top_jobs = []

    return DashboardResponse(
        has_context=True,
        resume_ats_score=state.get("current_ats_score"),
        updated_resume_ats_score=state.get("updated_ats_score"),
        updated_resume=updated_resume,
        cover_letter=cover_letter,
        current_analysis=current_gap,
        skills_to_develop=current_gap.get("missing_skills", []),
        development_plan=current_gap.get("development_plan", []),
        prioritized_gaps=current_gap.get("prioritized_gaps", []),
        recommendations=current_gap.get("recommendations", ""),
        top_job_listings=top_jobs,
        job_listings_updated_at=artifacts.get("job_listings_updated_at", ""),
        artifact_updated_at=artifacts.get("updated_at", "")
    )


# Backwards-compatible routes (deprecated)
@router.post("/skill-gap-analysis")
def analyze_skill_gap_legacy(payload: SkillGapRequest, user=Depends(get_current_user)):
    return analyze_skill_gap(payload, user)


@router.post("/generate-cover-letter")
def generate_cover_letter_legacy(payload: SkillGapRequest, user=Depends(get_current_user)):
    return generate_cover_letter(payload, user)


@router.post("/update-resume")
def update_resume_legacy(payload: ResumeUpdateRequest, user=Depends(get_current_user)):
    return update_resume(payload, user)
