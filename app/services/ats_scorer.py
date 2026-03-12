import re

from app.services.skill_extractor import extract_skills


def _normalize_line(line: str) -> str:
    return re.sub(r"[^a-z0-9\s]", "", line.lower()).strip()


def _skill_coverage_score(resume_text: str, job_description: str) -> int:
    resume_skills = set(extract_skills(resume_text))
    job_skills = set(extract_skills(job_description))
    if not job_skills:
        return 0
    matched = len(resume_skills & job_skills)
    return round((matched / len(job_skills)) * 100)


def _structure_score(resume_text: str) -> int:
    lines = [line.strip() for line in (resume_text or "").replace("\r\n", "\n").split("\n") if line.strip()]
    if not lines:
        return 0

    headings = {
        "summary",
        "professional summary",
        "skills",
        "technical skills",
        "experience",
        "work experience",
        "projects",
        "education",
        "certifications"
    }

    found_headings = set()
    for line in lines:
        normalized = _normalize_line(re.sub(r"[:\-]+$", "", line))
        if normalized in headings:
            found_headings.add(normalized)

    heading_points = min(45, round(len(found_headings) * 7.5))

    has_skills_section = "skills" in found_headings or "technical skills" in found_headings
    explicit_skills = len(extract_skills(resume_text))
    if has_skills_section and explicit_skills >= 10:
        skills_points = 18
    elif has_skills_section and explicit_skills >= 6:
        skills_points = 14
    elif explicit_skills >= 6:
        skills_points = 10
    else:
        skills_points = 6

    bullet_count = sum(1 for line in lines if re.match(r"^[-*•]\s+", line))
    if bullet_count >= 10:
        bullet_points = 20
    elif bullet_count >= 6:
        bullet_points = 16
    elif bullet_count >= 3:
        bullet_points = 11
    else:
        bullet_points = 5

    formatting_points = 17
    if "|" in resume_text:
        formatting_points -= 6
    if re.search(r"[^\x00-\x7F]", resume_text):
        formatting_points -= 4
    if any(len(line) > 200 for line in lines):
        formatting_points -= 4
    formatting_points = max(0, formatting_points)

    return min(100, heading_points + skills_points + bullet_points + formatting_points)


class ATSScorer:
    @staticmethod
    def score_resume_for_job(resume_text: str, job_description: str) -> int:
        coverage = _skill_coverage_score(resume_text, job_description)
        structure = _structure_score(resume_text)

        # Weight structure higher so ATS-oriented formatting improvements are reflected.
        score = round((coverage * 0.25) + (structure * 0.75))

        # Keep guardrails: very low skill coverage should not reach top ATS bands.
        if coverage < 35:
            score = min(score, 70)
        elif coverage < 50:
            score = min(score, 82)

        return max(0, min(100, score))
