import uuid
from app.services.analysis_state_service import AnalysisStateService
from app.services.job_recommender import JobRecommender
from app.services.user_context_service import UserContextService


def test_skill_gap_empty_description(client):
    email = f"test-{uuid.uuid4()}@example.com"
    signup = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "password123"}
    )
    assert signup.status_code == 200
    token = signup.json()["token"]

    response = client.post(
        "/api/skill-gap",
        json={
            "resume_text": "Python developer with FastAPI experience.",
            "job_description": ""
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200


def test_user_context_is_isolated_per_account(client):
    user1_email = f"user1-{uuid.uuid4()}@example.com"
    user2_email = f"user2-{uuid.uuid4()}@example.com"

    user1_signup = client.post(
        "/api/auth/signup",
        json={"email": user1_email, "password": "password123"}
    )
    user2_signup = client.post(
        "/api/auth/signup",
        json={"email": user2_email, "password": "password123"}
    )
    assert user1_signup.status_code == 200
    assert user2_signup.status_code == 200

    token1 = user1_signup.json()["token"]
    token2 = user2_signup.json()["token"]

    save_user1 = client.put(
        "/api/context",
        json={"resume_text": "User1 Resume", "job_description": "User1 JD"},
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert save_user1.status_code == 200

    user1_context = client.get(
        "/api/context",
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert user1_context.status_code == 200
    assert user1_context.json()["resume_text"] == "User1 Resume"
    assert user1_context.json()["job_description"] == "User1 JD"

    user2_context = client.get(
        "/api/context",
        headers={"Authorization": f"Bearer {token2}"}
    )
    assert user2_context.status_code == 200
    assert user2_context.json()["resume_text"] == ""
    assert user2_context.json()["job_description"] == ""

    clear_user1_resume = client.delete(
        "/api/context/resume",
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert clear_user1_resume.status_code == 200
    assert clear_user1_resume.json()["resume_text"] == ""
    assert clear_user1_resume.json()["job_description"] == "User1 JD"


def test_dashboard_isolated_per_user_artifacts(client):
    user1_email = f"dash1-{uuid.uuid4()}@example.com"
    user2_email = f"dash2-{uuid.uuid4()}@example.com"

    signup1 = client.post(
        "/api/auth/signup",
        json={"email": user1_email, "password": "password123"}
    )
    signup2 = client.post(
        "/api/auth/signup",
        json={"email": user2_email, "password": "password123"}
    )
    assert signup1.status_code == 200
    assert signup2.status_code == 200

    token1 = signup1.json()["token"]
    token2 = signup2.json()["token"]
    user1_id = signup1.json()["user"]["id"]

    resume_text = "Python engineer"
    job_description = "Need Python engineer"
    UserContextService.save_context(
        user_id=user1_id,
        resume_text=resume_text,
        job_description=job_description
    )
    UserContextService.save_artifacts(
        user_id=user1_id,
        cover_letter="User1 cover letter",
        updated_resume="User1 updated resume"
    )
    AnalysisStateService.tag_cover_letter_context(
        user_id=user1_id,
        resume_text=resume_text,
        job_description=job_description
    )

    dashboard1 = client.get(
        "/api/dashboard",
        headers={"Authorization": f"Bearer {token1}"}
    )
    dashboard2 = client.get(
        "/api/dashboard",
        headers={"Authorization": f"Bearer {token2}"}
    )

    assert dashboard1.status_code == 200
    assert dashboard2.status_code == 200

    payload1 = dashboard1.json()
    payload2 = dashboard2.json()

    assert payload1["has_context"] is True
    assert payload1["cover_letter"] == "User1 cover letter"
    assert payload1["updated_resume"] == ""

    assert payload2["has_context"] is False
    assert payload2["cover_letter"] == ""
    assert payload2["updated_resume"] == ""


def test_universal_ats_scores_reused_across_endpoints(client):
    email = f"universal-{uuid.uuid4()}@example.com"
    signup = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "password123"}
    )
    assert signup.status_code == 200
    token = signup.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    resume_text = "Python developer with FastAPI, SQL, AWS, Docker, and Git experience."
    job_description = "Looking for a Python FastAPI engineer with SQL, AWS, Docker, Git, and CI/CD."

    save_context = client.put(
        "/api/context",
        json={"resume_text": resume_text, "job_description": job_description},
        headers=headers
    )
    assert save_context.status_code == 200

    gap_response = client.post(
        "/api/skill-gap",
        json={"resume_text": resume_text, "job_description": job_description},
        headers=headers
    )
    assert gap_response.status_code == 200
    gap_payload = gap_response.json()
    gap_score = gap_payload.get("ats_score", gap_payload.get("readiness_score"))

    dashboard_response = client.get("/api/dashboard", headers=headers)
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["resume_ats_score"] == gap_score

    update_one = client.post(
        "/api/resume-update",
        json={"resume_text": resume_text, "job_description": job_description},
        headers=headers
    )
    assert update_one.status_code == 200
    update_payload_one = update_one.json()
    assert update_payload_one["ats_current_score"] == gap_score

    update_two = client.post(
        "/api/resume-update",
        json={"resume_text": resume_text, "job_description": job_description},
        headers=headers
    )
    assert update_two.status_code == 200
    update_payload_two = update_two.json()

    assert update_payload_two["updated_resume"] == update_payload_one["updated_resume"]
    assert update_payload_two["ats_current_score"] == update_payload_one["ats_current_score"]
    assert update_payload_two["ats_updated_score"] == update_payload_one["ats_updated_score"]


def test_job_recommendations_return_tavily_mode_without_fallback_links(client, monkeypatch):
    email = f"jobs-{uuid.uuid4()}@example.com"
    signup = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "password123"}
    )
    assert signup.status_code == 200
    token = signup.json()["token"]

    def _empty_tavily(*_args, **_kwargs):
        return []

    monkeypatch.setattr(
        JobRecommender,
        "_tavily_job_results",
        staticmethod(_empty_tavily)
    )

    response = client.post(
        "/api/job-recommendations",
        json={
            "resume_text": "Python engineer with FastAPI and AWS.",
            "job_description": "Hiring a Backend Engineer in Austin, TX with Python and AWS.",
            "limit": 5
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_mode"] == "tavily"
    assert payload["jobs"] == []


def test_job_recommendations_infer_role_and_location_from_job_description(client, monkeypatch):
    email = f"jobs-jd-{uuid.uuid4()}@example.com"
    signup = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "password123"}
    )
    assert signup.status_code == 200
    token = signup.json()["token"]

    def _empty_tavily(*_args, **_kwargs):
        return []

    monkeypatch.setattr(
        JobRecommender,
        "_tavily_job_results",
        staticmethod(_empty_tavily)
    )

    jd = (
        "Job Title: Senior Data Scientist\n"
        "Location: New York, NY\n"
        "We are seeking a Senior Data Scientist with Python, SQL, and ML skills."
    )
    response = client.post(
        "/api/job-recommendations",
        json={
            "resume_text": "Experienced data professional with Python and SQL.",
            "job_description": jd,
            "limit": 5
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["inferred_role"] == "Senior Data Scientist"
    assert payload["inferred_location"] == "New York, NY"
    assert "Senior Data Scientist jobs in New York, NY" in payload["query"]
    assert payload["inferred_role"] != "Software Engineer"
    assert payload["inferred_location"] != "United States"


def test_dashboard_persists_job_listings_for_user_context(client, monkeypatch):
    email = f"jobs-dash-{uuid.uuid4()}@example.com"
    signup = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "password123"}
    )
    assert signup.status_code == 200
    token = signup.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    resume = "Backend engineer with Python and FastAPI experience."
    jd = "Job Title: Backend Engineer\nLocation: Austin, TX\nNeed Python FastAPI engineer."

    save_context = client.put(
        "/api/context",
        json={"resume_text": resume, "job_description": jd},
        headers=headers
    )
    assert save_context.status_code == 200

    def _mock_tavily(*_args, **_kwargs):
        return [
            {
                "title": "Backend Engineer",
                "company": "Example Co",
                "location": "Austin, TX",
                "url": "https://example.com/jobs/1",
                "snippet": "Python FastAPI backend role",
                "source": "tavily"
            }
        ]

    monkeypatch.setattr(
        JobRecommender,
        "_tavily_job_results",
        staticmethod(_mock_tavily)
    )

    jobs_response = client.post(
        "/api/job-recommendations",
        json={"resume_text": resume, "job_description": jd, "limit": 5},
        headers=headers
    )
    assert jobs_response.status_code == 200
    assert len(jobs_response.json()["jobs"]) == 1

    dashboard_response = client.get("/api/dashboard", headers=headers)
    assert dashboard_response.status_code == 200
    payload = dashboard_response.json()
    assert len(payload["top_job_listings"]) == 1
    assert payload["top_job_listings"][0]["title"] == "Backend Engineer"
