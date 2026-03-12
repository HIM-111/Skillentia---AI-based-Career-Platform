from app.services.resume_updater import ResumeUpdater
from app.services.ats_scorer import ATSScorer


def test_resume_updater_sanitizes_llm_preamble_and_markdown(monkeypatch):
    resume_text = (
        "Jane Doe\n"
        "Skills\n"
        "Python, SQL\n"
        "Experience\n"
        "- Built APIs with FastAPI\n"
    )
    generated = (
        "Here is the generated updated resume:\n"
        "```text\n"
        "SUMMARY: Backend engineer with API development experience.\\n"
        "SKILLS: Python, SQL\\n"
        "EXPERIENCE: Built APIs with FastAPI and SQL.\n"
        "```"
    )

    monkeypatch.setattr(
        "app.services.resume_updater.LocalLLMClient.generate",
        lambda _prompt: generated
    )

    result = ResumeUpdater.update(
        resume_text=resume_text,
        missing_skills=[],
        job_description="Backend role requiring Python and SQL",
        matched_skills=["Python", "SQL"]
    )

    assert "Here is the generated updated resume" not in result
    assert "```" not in result
    assert "\nSUMMARY\n" in f"\n{result}\n"
    assert "\nSKILLS\n" in f"\n{result}\n"
    assert "\nEXPERIENCE\n" in f"\n{result}\n"


def test_resume_updater_no_other_heading_for_unsectioned_resume():
    raw_resume = (
        "Jane Doe\n"
        "Austin, TX\n"
        "jane@example.com\n"
        "Built APIs with Python and SQL.\n"
    )

    result = ResumeUpdater._ats_reformat(raw_resume, ["Python", "SQL"])
    assert not result.startswith("OTHER\n")
    assert "SKILLS" in result


def test_resume_updater_strict_template_improves_ats_structure_without_fabrication():
    resume = (
        "Alex Johnson\n"
        "Seattle, WA | alex@example.com | 555-0101\n"
        "Experience:\n"
        "Software Engineer at Example Corp 2022 - Present\n"
        "Built FastAPI services and optimized SQL queries.\n"
        "Implemented CI/CD workflows with GitHub Actions.\n"
        "Reduced API latency by 30 percent.\n"
        "Projects:\n"
        "Inventory Service\n"
        "Designed Docker-based deployment and monitoring dashboards.\n"
        "Education:\n"
        "B.S. Computer Science, University of Washington\n"
    )
    jd = "Backend Engineer with Python, FastAPI, SQL, Docker, CI/CD, GitHub Actions."

    updated = ResumeUpdater.strict_ats_reformat(resume)
    baseline_score = ATSScorer.score_resume_for_job(resume, jd)
    updated_score = ATSScorer.score_resume_for_job(updated, jd)

    assert "\nSKILLS\n" in f"\n{updated}\n"
    assert "\nEXPERIENCE\n" in f"\n{updated}\n"
    assert updated.count("\n- ") >= 2
    assert "Here is" not in updated
    assert updated_score >= baseline_score


def test_resume_updater_preserves_uploaded_section_structure():
    resume = (
        "Riwaj Singh Chaudhary\n"
        "Education\n"
        "BSc IT\n"
        "Profile\n"
        "Motivated IT student with hands-on project experience.\n"
        "Projects\n"
        "Project One\n"
        "Built an API service.\n"
        "Skills\n"
        "Python, FastAPI, SQL\n"
        "Soft Skills\n"
        "Communication\n"
        "Languages\n"
        "English, Nepali\n"
        "References\n"
        "Reference Person\n"
    )
    updated = ResumeUpdater.strict_ats_reformat(resume)

    assert "\nEDUCATION\n" in f"\n{updated}\n"
    assert "\nPROFILE\n" in f"\n{updated}\n"
    assert "\nPROJECTS\n" in f"\n{updated}\n"
    assert "\nSKILLS\n" in f"\n{updated}\n"
    assert "\nSOFT SKILLS\n" in f"\n{updated}\n"
    assert "\nLANGUAGES\n" in f"\n{updated}\n"
    assert "\nREFERENCES\n" in f"\n{updated}\n"
    assert updated.index("EDUCATION") < updated.index("PROFILE")
    assert updated.index("PROFILE") < updated.index("PROJECTS")


def test_resume_updater_coalesces_wrapped_lines_into_coherent_bullets():
    resume = (
        "Jane Doe\n"
        "Projects\n"
        "Fraud Detection Platform\n"
        "Designed and deployed an ML pipeline\n"
        "for anomaly detection in streaming data\n"
        "with FastAPI serving endpoints.\n"
    )

    updated = ResumeUpdater.strict_ats_reformat(resume)

    assert "Fraud Detection Platform: Designed and deployed an ML pipeline for anomaly detection in streaming data with FastAPI serving endpoints." in updated
    assert "- Fraud Detection Platform" not in updated


def test_resume_updater_splits_combined_project_paragraph_into_multiple_entries():
    resume = (
        "Jane Doe\n"
        "Projects\n"
        "Alpha Platform: Built APIs and dashboards. Beta Tool: Implemented data pipelines. Gamma Suite: Improved reliability.\n"
    )
    updated = ResumeUpdater.strict_ats_reformat(resume)

    assert "Alpha Platform: Built APIs and dashboards." in updated
    assert "Beta Tool: Implemented data pipelines." in updated
    assert "Gamma Suite: Improved reliability." in updated


def test_resume_updater_uses_single_header_per_skill_group():
    resume = (
        "Jane Doe\n"
        "Skills\n"
        "Programming Languages\n"
        "Python, SQL, JavaScript, TypeScript, C++, Go, Rust, Java, Kotlin, Swift, Ruby, PHP\n"
        "Development Skills\n"
        "Docker, Kubernetes, Git, CI/CD\n"
    )
    updated = ResumeUpdater.strict_ats_reformat(resume)

    assert updated.count("Programming Skills:") == 1
    assert updated.count("Development Skills:") == 1


def test_resume_updater_splits_sentence_joined_projects():
    resume = (
        "Jane Doe\n"
        "Projects\n"
        "Alpha Platform: Built APIs and dashboards. Beta Tool: Implemented data pipelines. Gamma Suite: Improved reliability.\n"
    )
    updated = ResumeUpdater.strict_ats_reformat(resume)
    project_lines = [line for line in updated.splitlines() if ": " in line and "Skills" not in line]

    assert any(line.startswith("Alpha Platform:") for line in project_lines)
    assert any(line.startswith("Beta Tool:") for line in project_lines)
    assert any(line.startswith("Gamma Suite:") for line in project_lines)


def test_resume_updater_derives_experience_bullets_from_projects_for_ats():
    resume = (
        "Jane Doe\n"
        "Projects\n"
        "Alpha Platform: Built APIs with FastAPI and SQL. Improved response times by 30 percent.\n"
        "Beta Tool: Implemented Docker-based deployments and CI/CD workflows.\n"
    )
    updated = ResumeUpdater.strict_ats_reformat(resume)
    bullet_lines = [line for line in updated.splitlines() if line.startswith("- ")]

    assert "\nEXPERIENCE\n" in f"\n{updated}\n"
    assert len(bullet_lines) >= 3
