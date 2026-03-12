import json
import re

from app.core.config import settings
from app.llm.client import LocalLLMClient
from app.llm.prompts import skill_gap_prompt
from app.services.skill_extractor import extract_skills


SKILL_CATEGORIES = {
    "programming": {
        "python", "java", "javascript", "typescript", "c", "c++", "c#", "go",
        "rust", "php", "ruby", "swift", "kotlin", "scala", "r", "bash", "powershell"
    },
    "frameworks": {
        "react", "next.js", "vue.js", "angular", "node.js", "express",
        "django", "flask", "fastapi", "spring", "graphql", "microservices"
    },
    "data_ai": {
        "sql", "data analysis", "data science", "machine learning", "deep learning",
        "nlp", "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "spark",
        "tableau", "power bi"
    },
    "cloud_devops": {
        "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible",
        "jenkins", "github actions", "ci/cd", "linux", "prometheus", "grafana"
    },
    "product_design": {
        "product management", "roadmap", "agile", "scrum", "jira", "ux", "ui", "figma"
    },
    "security_qa": {
        "qa", "testing", "selenium", "cypress", "playwright", "cybersecurity",
        "owasp", "threat modeling", "penetration testing"
    },
}


def _categorize_skill(skill: str) -> str:
    for category, skills in SKILL_CATEGORIES.items():
        if skill in skills:
            return category
    return "other"


class SkillGapAnalyzer:
    @staticmethod
    def analyze(resume_text: str, job_description: str):
        # Deterministic core for ATS scoring consistency across pages and calls.
        resume_skills = extract_skills(resume_text)
        job_skills = extract_skills(job_description)
        matching = sorted(set(resume_skills) & set(job_skills))
        missing = sorted(set(job_skills) - set(resume_skills))

        semantic = SkillGapAnalyzer._semantic_analyze(resume_text, job_description)
        if semantic:
            prioritized = semantic.get("prioritized_gaps", [])
            strengths = semantic.get("strengths", [])
            recommendations = semantic.get("recommendations", "")
            development_plan = semantic.get("development_plan", [])
            return SkillGapAnalyzer._build_analysis(
                matching_skills=matching,
                missing_skills=missing,
                job_description=job_description,
                recommendations_override=recommendations,
                prioritized_override=prioritized,
                strengths_override=strengths,
                development_plan_override=development_plan,
                analysis_engine=f"ollama:{settings.OLLAMA_MODEL}"
            )

        # Fallback when LLM is unavailable or output is invalid.
        return SkillGapAnalyzer.compare_skills(
            resume_skills=resume_skills,
            job_skills=job_skills,
            job_description=job_description
        )

    @staticmethod
    def compare_skills(
        resume_skills: list[str],
        job_skills: list[str],
        job_description: str = ""
    ):
        resume_set = set(resume_skills)
        job_set = set(job_skills)
        return SkillGapAnalyzer._build_analysis(
            matching_skills=sorted(resume_set & job_set),
            missing_skills=sorted(job_set - resume_set),
            job_description=job_description,
            analysis_engine="deterministic-fallback"
        )

    @staticmethod
    def _build_analysis(
        matching_skills: list[str],
        missing_skills: list[str],
        job_description: str,
        recommendations_override: str = "",
        prioritized_override: list | None = None,
        strengths_override: list | None = None,
        development_plan_override: list | None = None,
        analysis_engine: str = "deterministic-fallback"
    ) -> dict:
        matching = sorted(set(matching_skills))
        missing = sorted(set(missing_skills))
        total = len(matching) + len(missing)
        readiness_score = round((len(matching) / total) * 100) if total else 0

        recommendations = recommendations_override.strip() if recommendations_override else (
            "Focus on building experience with: "
            + ", ".join(missing)
            if missing
            else "Your resume already matches the listed requirements."
        )

        category_breakdown = SkillGapAnalyzer._build_category_breakdown(matching, missing)
        prioritized_gaps = (
            SkillGapAnalyzer._normalize_prioritized_gaps(prioritized_override)
            if prioritized_override
            else SkillGapAnalyzer._prioritize_gaps(missing, job_description)
        )
        strengths = strengths_override[:8] if strengths_override else matching[:8]
        development_plan = (
            development_plan_override[:5]
            if development_plan_override
            else [f"Prioritize {item['skill']} ({item['priority']} impact)" for item in prioritized_gaps[:5]]
        )

        return {
            "matching_skills": matching,
            "matched_skills": matching,
            "missing_skills": missing,
            "recommendations": recommendations,
            "readiness_score": readiness_score,
            "total_target_skills": total,
            "category_breakdown": category_breakdown,
            "prioritized_gaps": prioritized_gaps,
            "strengths": strengths,
            "development_plan": development_plan,
            "analysis_engine": analysis_engine,
            "llm_used": analysis_engine.startswith("ollama:")
        }

    @staticmethod
    def _semantic_analyze(resume_text: str, job_description: str) -> dict | None:
        if not resume_text.strip() or not job_description.strip():
            return None
        prompt = skill_gap_prompt(resume_text, job_description)

        try:
            raw = LocalLLMClient.generate(prompt, timeout=120)
            return SkillGapAnalyzer._extract_json(raw)
        except Exception:
            return None

    @staticmethod
    def _extract_json(raw: str) -> dict | None:
        if not raw:
            return None
        snippet = raw.strip()
        match = re.search(r"\{.*\}", snippet, flags=re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return {
            "matching_skills": [str(x).strip() for x in payload.get("matching_skills", []) if str(x).strip()],
            "missing_skills": [str(x).strip() for x in payload.get("missing_skills", []) if str(x).strip()],
            "prioritized_gaps": payload.get("prioritized_gaps", []),
            "recommendations": str(payload.get("recommendations", "")).strip(),
            "strengths": [str(x).strip() for x in payload.get("strengths", []) if str(x).strip()],
            "development_plan": SkillGapAnalyzer._normalize_development_plan(payload.get("development_plan", [])),
        }

    @staticmethod
    def _normalize_development_plan(items: list) -> list[str]:
        normalized = []
        for item in items:
            if isinstance(item, dict):
                skill = str(item.get("skill", "")).strip()
                action = str(item.get("action", "")).strip() or str(item.get("step", "")).strip()
                if skill and action:
                    normalized.append(f"{skill}: {action}")
                elif action:
                    normalized.append(action)
                elif skill:
                    normalized.append(f"Develop {skill}")
                continue

            text = str(item).strip()
            if not text:
                continue

            # Support legacy stringified-dict outputs from previous cached runs.
            skill_match = re.search(r"['\"]skill['\"]\s*:\s*['\"]([^'\"]+)['\"]", text, flags=re.IGNORECASE)
            action_match = re.search(r"['\"]action['\"]\s*:\s*['\"]([^'\"]+)['\"]", text, flags=re.IGNORECASE)
            if skill_match and action_match:
                normalized.append(f"{skill_match.group(1).strip()}: {action_match.group(1).strip()}")
            else:
                normalized.append(text)

        return normalized

    @staticmethod
    def _normalize_prioritized_gaps(items: list) -> list[dict]:
        normalized = []
        for item in items:
            if not isinstance(item, dict):
                continue
            skill = str(item.get("skill", "")).strip()
            priority = str(item.get("priority", "Medium")).strip().title()
            reason = str(item.get("reason", "")).strip()
            if not skill:
                continue
            if priority not in {"High", "Medium", "Low"}:
                priority = "Medium"
            normalized.append(
                {
                    "skill": skill,
                    "priority": priority,
                    "mention_count": 0,
                    "reason": reason
                }
            )
        return normalized

    @staticmethod
    def _build_category_breakdown(matching: list[str], missing: list[str]) -> list[dict]:
        categories = {}

        for skill in matching:
            category = _categorize_skill(skill)
            categories.setdefault(category, {"category": category, "matched": 0, "missing": 0})
            categories[category]["matched"] += 1

        for skill in missing:
            category = _categorize_skill(skill)
            categories.setdefault(category, {"category": category, "matched": 0, "missing": 0})
            categories[category]["missing"] += 1

        result = []
        for item in categories.values():
            total = item["matched"] + item["missing"]
            item["coverage"] = round((item["matched"] / total) * 100) if total else 0
            result.append(item)

        result.sort(key=lambda x: (x["missing"], -x["coverage"]), reverse=True)
        return result

    @staticmethod
    def _prioritize_gaps(missing_skills: list[str], job_description: str) -> list[dict]:
        jd_lower = job_description.lower()
        prioritized = []

        for skill in missing_skills:
            mention_count = jd_lower.count(skill.lower())
            if mention_count >= 2:
                priority = "High"
            elif mention_count == 1:
                priority = "Medium"
            else:
                priority = "Low"

            prioritized.append({
                "skill": skill,
                "priority": priority,
                "mention_count": mention_count
            })

        priority_order = {"High": 3, "Medium": 2, "Low": 1}
        prioritized.sort(
            key=lambda item: (priority_order[item["priority"]], item["mention_count"], item["skill"]),
            reverse=True
        )
        return prioritized
