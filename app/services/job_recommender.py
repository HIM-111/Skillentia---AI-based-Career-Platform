import logging
import re
from typing import Any
from urllib.parse import urlparse

import requests

from app.core.config import settings
from app.services.skill_extractor import extract_skills

try:
    from tavily import TavilyClient
except Exception:  # pragma: no cover
    TavilyClient = None


ROLE_HINTS = [
    "Software Engineer",
    "Backend Engineer",
    "Frontend Engineer",
    "Full Stack Engineer",
    "Data Scientist",
    "Data Analyst",
    "Machine Learning Engineer",
    "DevOps Engineer",
    "Cloud Engineer",
    "Product Manager",
    "UX Designer",
    "QA Engineer",
    "Cybersecurity Analyst",
]
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
PREFERRED_JOB_DOMAINS = [
    "linkedin.com",
    "indeed.com",
    "jobs.lever.co",
    "boards.greenhouse.io",
    "ziprecruiter.com",
    "wellfound.com",
    "builtin.com",
]
LOGGER = logging.getLogger(__name__)


class JobRecommender:
    @staticmethod
    def recommend_jobs(
        resume_text: str,
        job_description: str,
        limit: int = 5
    ) -> dict[str, Any]:
        max_items = max(1, min(limit, 10))
        inferred_role = JobRecommender._infer_role(job_description)
        inferred_location = JobRecommender._infer_location(job_description)
        resume_skills = extract_skills(resume_text)

        query = JobRecommender._build_search_query(
            role=inferred_role,
            location=inferred_location,
            job_description=job_description
        )

        results = JobRecommender._tavily_job_results(
            query=query,
            role=inferred_role,
            location=inferred_location,
            limit=max_items
        )

        source_mode = "tavily"

        scored = [
            JobRecommender._score_result(result, resume_skills, inferred_role, inferred_location)
            for result in results
        ]
        scored.sort(key=lambda item: item["compatibility_score"], reverse=True)

        return {
            "inferred_role": inferred_role,
            "inferred_location": inferred_location,
            "source_mode": source_mode,
            "query": query,
            "jobs": scored[:max_items]
        }

    @staticmethod
    def _build_search_query(role: str, location: str, job_description: str) -> str:
        jd = " ".join((job_description or "").split())
        jd_focus = jd[:250]
        if role != "Not specified" and location != "Not specified":
            opener = f"{role} jobs in {location}. "
        elif role != "Not specified":
            opener = f"{role} jobs. "
        elif location != "Not specified":
            opener = f"Jobs in {location}. "
        else:
            opener = "Jobs matching this job description. "
        return (
            opener +
            f"Use role and location from this context: {jd_focus}. "
            "Find active job listings with direct application links from LinkedIn, Indeed, Lever, Greenhouse, ZipRecruiter, and company career pages."
        )

    @staticmethod
    def _infer_role(job_description: str) -> str:
        jd = " ".join((job_description or "").split())
        if not jd:
            return "Not specified"

        role_patterns = [
            r"(?:job\s*title|title|position|role)\s*[:\-]\s*([A-Za-z][A-Za-z0-9/&+,\- ]{3,80}?)(?=\s+(?:location|job\s*location|responsibilities|requirements)\s*:|[.;,\n]|$)",
            r"(?:we(?:'re| are)?\s+hiring|hiring|seeking|looking for|need)\s+(?:for\s+)?(?:an?\s+|the\s+)?([A-Za-z][A-Za-z0-9/&+,\- ]{3,80}?)(?:\s+(?:in|at|for|to)\b|[.;,\n]|$)",
            r"(?:role|position)\s+of\s+([A-Za-z][A-Za-z0-9/&+,\- ]{3,80})(?:[.;,\n]|$)",
        ]
        for pattern in role_patterns:
            match = re.search(pattern, jd, flags=re.IGNORECASE)
            if match:
                cleaned = JobRecommender._clean_role(match.group(1))
                if cleaned:
                    return cleaned

        for role in ROLE_HINTS:
            if re.search(rf"\b{re.escape(role)}\b", jd, flags=re.IGNORECASE):
                return role

        lines = [line.strip() for line in (job_description or "").splitlines() if line.strip()]
        for line in lines[:4]:
            if 3 <= len(line) <= 80 and re.search(
                r"\b(engineer|developer|analyst|manager|scientist|designer|consultant|specialist|architect|administrator|coordinator)\b",
                line,
                flags=re.IGNORECASE
            ):
                cleaned = JobRecommender._clean_role(line)
                if cleaned:
                    return cleaned

        return "Not specified"

    @staticmethod
    def _infer_location(job_description: str) -> str:
        jd = " ".join((job_description or "").split())
        if not jd:
            return "Not specified"
        jd_lower = jd.lower()

        if "remote" in jd_lower and "hybrid" in jd_lower:
            return "Remote / Hybrid"
        if "remote" in jd_lower:
            return "Remote"
        if "hybrid" in jd_lower:
            return "Hybrid"
        if "on-site" in jd_lower or "onsite" in jd_lower:
            return "On-site"

        loc_line = re.search(
            r"(location|job location|work location|based in|office in|located in)\s*[:\-]?\s*([A-Za-z .'-]+(?:,\s*[A-Za-z]{2,})?)",
            jd,
            flags=re.IGNORECASE
        )
        if loc_line:
            return loc_line.group(2).strip()

        city_state = re.search(r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*,\s*[A-Z]{2})\b", jd)
        if city_state:
            return city_state.group(1).strip()

        city_country = re.search(
            r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*,\s*(?:United States|USA|United Kingdom|UK|Canada|India|Australia|Germany|France|Netherlands|Singapore))\b",
            jd
        )
        if city_country:
            return city_country.group(1).strip()

        phrase_location = re.search(
            r"(?:hiring|role|position|job).{0,80}?\bin\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*(?:,\s*[A-Z]{2})?)",
            jd,
            flags=re.IGNORECASE
        )
        if phrase_location:
            return phrase_location.group(1).strip()

        return "Not specified"

    @staticmethod
    def _clean_role(value: str) -> str:
        role = " ".join((value or "").split()).strip(" -,:;")
        role = re.sub(r"^(an?|the)\s+", "", role, flags=re.IGNORECASE)
        role = re.sub(r"\s+(?:role|position)$", "", role, flags=re.IGNORECASE)
        role = re.sub(r"\s+location$", "", role, flags=re.IGNORECASE)
        role = role.strip(" -,:;")
        return role[:80].strip() if role else ""

    @staticmethod
    def _tavily_job_results(query: str, role: str, location: str, limit: int) -> list[dict[str, str]]:
        api_key = (settings.TAVILY_API_KEY or "").strip()
        if not api_key:
            LOGGER.warning("Tavily search skipped because TAVILY_API_KEY is not set.")
            return []

        max_results = max(limit * 4, 12)
        data = JobRecommender._search_with_tavily_sdk(
            api_key,
            query,
            max_results,
            restrict_domains=True
        )
        if not data:
            data = JobRecommender._search_with_tavily_http(
                api_key,
                query,
                max_results,
                restrict_domains=True
            )
        if not data:
            broad_query = f"{role} jobs {location} apply now"
            data = JobRecommender._search_with_tavily_sdk(
                api_key,
                broad_query,
                max_results,
                restrict_domains=False
            )
            if not data:
                data = JobRecommender._search_with_tavily_http(
                    api_key,
                    broad_query,
                    max_results,
                    restrict_domains=False
                )
        if not data:
            return []

        raw_results = data.get("results", []) if isinstance(data, dict) else []
        jobs: list[dict[str, str]] = []
        seen_urls = set()

        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or item.get("link") or "").strip()
            if not url or url in seen_urls:
                continue

            title = str(item.get("title") or "").strip()
            content = " ".join(str(item.get("content") or "").split())
            if not title:
                title = f"{role} opportunity"

            seen_urls.add(url)
            jobs.append(
                {
                    "title": title,
                    "company": JobRecommender._infer_company_from_url(url),
                    "location": location,
                    "url": url,
                    "source": "Tavily",
                    "snippet": content[:260]
                }
            )

            if len(jobs) >= limit:
                break

        if not jobs:
            LOGGER.warning(
                "Tavily returned no job URLs. role=%s location=%s query=%s",
                role,
                location,
                query
            )

        return jobs

    @staticmethod
    def _search_with_tavily_sdk(
        api_key: str,
        query: str,
        max_results: int,
        restrict_domains: bool = True
    ) -> dict[str, Any] | None:
        if TavilyClient is None:
            return None
        try:
            client = TavilyClient(api_key)
        except Exception:
            try:
                client = TavilyClient(api_key=api_key)
            except Exception:
                return None

        try:
            payload = {
                "query": query,
                "search_depth": "advanced",
                "max_results": max_results
            }
            if restrict_domains:
                payload["include_domains"] = PREFERRED_JOB_DOMAINS
            response = client.search(**payload)
            if isinstance(response, dict):
                return response
            return None
        except TypeError:
            try:
                response = client.search(
                    query=query,
                    search_depth="advanced",
                    max_results=max_results
                )
                return response if isinstance(response, dict) else None
            except Exception:
                return None
        except Exception:
            return None

    @staticmethod
    def _search_with_tavily_http(
        api_key: str,
        query: str,
        max_results: int,
        restrict_domains: bool = True
    ) -> dict[str, Any] | None:
        payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results
        }
        if restrict_domains:
            payload["include_domains"] = PREFERRED_JOB_DOMAINS

        try:
            response = requests.post(
                TAVILY_SEARCH_URL,
                json=payload,
                timeout=20
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                return data
        except Exception as exc:
            LOGGER.warning("Tavily HTTP search (body key) failed: %s", exc)

        # Secondary format for compatibility with alternate gateway behavior.
        try:
            response = requests.post(
                TAVILY_SEARCH_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": max_results,
                    **({"include_domains": PREFERRED_JOB_DOMAINS} if restrict_domains else {})
                },
                timeout=20
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                return data
        except Exception as exc:
            LOGGER.warning("Tavily HTTP search (bearer key) failed: %s", exc)
            return None

        return None

    @staticmethod
    def _infer_company_from_url(url: str) -> str:
        try:
            host = urlparse(url).netloc.lower()
        except Exception:
            return "Unknown company"

        if "linkedin" in host:
            return "LinkedIn Listing"
        if "indeed" in host:
            return "Indeed Listing"
        if "greenhouse" in host:
            return "Greenhouse Listing"
        if "lever" in host:
            return "Lever Listing"
        if "ziprecruiter" in host:
            return "ZipRecruiter Listing"
        return host.replace("www.", "").split(".")[0].title()

    @staticmethod
    def _score_result(result: dict[str, str], skills: list[str], role: str, location: str) -> dict[str, Any]:
        searchable = " ".join(
            [
                result.get("title", ""),
                result.get("company", ""),
                result.get("location", ""),
                result.get("snippet", "")
            ]
        ).lower()

        matched_skills = [
            skill for skill in skills
            if re.search(rf"\b{re.escape(skill)}\b", searchable)
        ]

        role_score = 40 if role.lower() in searchable else 18
        location_score = 30 if location.lower() in searchable else (18 if "remote" in searchable else 10)
        skill_score = min(30, len(matched_skills) * 5)
        total = min(100, role_score + location_score + skill_score)

        return {
            "title": result.get("title", "Job listing"),
            "company": result.get("company", "Unknown"),
            "location": result.get("location", "Not specified"),
            "url": result.get("url", ""),
            "source": result.get("source", "Web"),
            "matched_skills": matched_skills[:6],
            "compatibility_score": total
        }
