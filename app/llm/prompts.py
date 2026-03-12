def cover_letter_prompt(resume: str, job_desc: str) -> str:
    return f"""
You are an ATS-safe professional cover letter generator.

RULES:
- Use ONLY provided resume data
- Do NOT invent skills or experience
- If data is missing, state "Not specified"
- Professional, concise tone
- No emojis, no fluff
- Return only the final cover letter text
- Do not add prefacing remarks (e.g., "Here is your cover letter")
- Do not include markdown fences or explanatory notes

RESUME:
{resume}

JOB DESCRIPTION:
{job_desc}

Use the following professional template exactly.
If any detail is missing from the resume, write "Not specified".

TEMPLATE:
[Candidate Name]
[Candidate Address]
[City, State, ZIP Code]
[Candidate Email]
[Candidate Phone number]
[Date]

[Hiring Manager's Name]
[Company Name]
[Company Address]
[City, State, ZIP Code]

Dear [Hiring Manager's Name],
Paragraph 1: 2-3 sentences. Role interest + brief qualification summary based ONLY on resume.
Paragraph 2: 2-4 sentences. Match 2-3 relevant skills/experiences from resume to the job description.
Paragraph 3: 1-2 sentences. Closing statement + interest in next steps.

Best Regards,
[Candidate Name]
""".strip()


def skill_gap_prompt(resume: str, job_desc: str) -> str:
    return f"""
You are a deterministic career analysis engine.
Your task is semantic skill-gap analysis between resume and job description.

RULES:
- Use only information in RESUME and JOB DESCRIPTION.
- Do not invent skills.
- Return valid JSON only, without markdown or explanations.
- Ensure all skill names are short strings.

OUTPUT JSON SCHEMA:
{{
  "matching_skills": ["..."],
  "missing_skills": ["..."],
  "prioritized_gaps": [
    {{
      "skill": "...",
      "priority": "High|Medium|Low",
      "reason": "short reason"
    }}
  ],
  "strengths": ["..."],
  "recommendations": "short paragraph",
  "development_plan": ["...", "...", "..."]
}}

RESUME:
{resume}

JOB DESCRIPTION:
{job_desc}
""".strip()


def resume_update_prompt(
    resume: str,
    allowed_skills: list[str],
    job_desc: str = "",
    matched_skills: list[str] | None = None
) -> str:
    skills = ", ".join(allowed_skills) if allowed_skills else "None provided"
    verified_matched = ", ".join((matched_skills or [])[:20]) if matched_skills else "None provided"

    return f"""
You are an ATS-focused resume formatter and truth-preserving editor.

STRICT RULES:
- Do NOT fabricate experience, education, companies, dates, or achievements.
- Do NOT add any skills that are not in the ALLOWED SKILLS list.
- Keep all facts exactly the same as the original resume.
- ONLY reorganize and lightly rephrase existing content for ATS compatibility.
- Preserve all measurable outcomes, dates, roles, and company names exactly as provided.
- Use only these section headers when available:
  SUMMARY, SKILLS, EXPERIENCE, PROJECTS, EDUCATION, CERTIFICATIONS
- Use concise bullet points under EXPERIENCE/PROJECTS.
- Single-column, plain-text layout.
- No markdown, no tables, no icons, no decorative characters.
- Put each section header on its own line (e.g., SUMMARY, SKILLS, EXPERIENCE).
- Use one bullet per line for responsibility/achievement statements.
- Keep clear line breaks between sections and entries.
- If a detail is missing, do not invent it.
- Ensure the SKILLS section includes ONLY skills from ALLOWED SKILLS.
- Prefer terminology from the JOB DESCRIPTION only where it truthfully maps to verified resume content.
- Emphasize VERIFIED MATCHED SKILLS in summary and experience bullets when supported by original resume text.

ALLOWED SKILLS:
{skills}

VERIFIED MATCHED SKILLS:
{verified_matched}

JOB DESCRIPTION:
{job_desc}

RESUME:
{resume}

Return the updated resume only, as plain text.
""".strip()
