from pydantic import BaseModel, Field
from typing import List, Optional


class JobDescriptionRequest(BaseModel):
    """
    Schema for job description input.
    """
    job_title: Optional[str] = Field(
        default=None,
        description="Target job title"
    )
    job_description: str = Field(
        ...,
        min_length=50,
        description="Full job description text"
    )


class SkillGapResponse(BaseModel):
    """
    Response schema for skill gap analysis.
    """
    matched_skills: List[str]
    missing_skills: List[str]
    partial_skills: List[str]


class CoverLetterResponse(BaseModel):
    """
    Response schema for AI-generated cover letter.
    """
    cover_letter: str


class ResumeUpdateResponse(BaseModel):
    """
    Response schema for resume enhancement suggestions.
    """
    updated_resume_text: str
    suggestions: List[str]
