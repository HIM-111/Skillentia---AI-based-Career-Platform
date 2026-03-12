from app.services.gap_analyzer import SkillGapAnalyzer

def test_skill_gap_logic():
    resume_skills = ["Python", "FastAPI", "Git"]
    job_skills = ["Python", "FastAPI", "SQL", "Docker"]

    analyzer = SkillGapAnalyzer()
    result = analyzer.compare_skills(resume_skills, job_skills)

    assert "matching_skills" in result
    assert "missing_skills" in result
    assert "readiness_score" in result
    assert "category_breakdown" in result
    assert "SQL" in result["missing_skills"]
