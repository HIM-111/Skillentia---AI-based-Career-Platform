# API Documentation

## Authentication
All platform endpoints (except auth) require:
- `Authorization: Bearer <token>`

### Signup
POST `/api/auth/signup`
- Input: `email`, `password`
- Output: `token`, `user`

### Login
POST `/api/auth/login`
- Input: `email`, `password`
- Output: `token`, `user`

### Current User
GET `/api/auth/me`
- Output: `user`

### Logout
POST `/api/auth/logout`

---

## Upload Resume
POST `/api/resume-upload`

- Accepts PDF, DOCX, DOC, DOCS, or TXT
- Returns extracted resume text

Request:
- `file` (multipart form data)

Response:
- `resume_text` (string)

---

## Skill Gap Analysis
POST `/api/skill-gap`

Input:
- `resume_text` (required)
- `job_description` (required)

Output:
- `matching_skills`
- `matched_skills` (compat alias)
- `missing_skills`
- `recommendations`

---

## Generate Cover Letter
POST `/api/cover-letter`

Input:
- `resume_text` (required)
- `job_description` (required)

Output:
- `cover_letter`

---

## Update Resume
POST `/api/resume-update`

Input:
- `resume_text` (required)
- `job_description` (required)

Output:
- `updated_resume`
- `missing_skills`

---

## Job Recommendations
POST `/api/job-recommendations`

Input:
- `resume_text` (required)
- `job_description` (required)
- `limit` (optional, default 5)

Output:
- `inferred_role`
- `inferred_location`
- `source_mode` (`tavily`)
- `jobs[]` with:
  - `title`
  - `company`
  - `location`
  - `url`
  - `source`
  - `matched_skills`
  - `compatibility_score`

---

## Backwards Compatible Routes (Deprecated)
- POST `/api/skill-gap-analysis`
- POST `/api/generate-cover-letter`
- POST `/api/update-resume`
