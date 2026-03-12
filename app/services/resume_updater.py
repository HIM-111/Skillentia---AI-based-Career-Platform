import re
from app.llm.client import LocalLLMClient
from app.llm.prompts import resume_update_prompt
from app.services.skill_extractor import extract_skills

class ResumeUpdater:
    SECTION_ORDER = [
        "SUMMARY",
        "PROFILE",
        "SKILLS",
        "SOFT SKILLS",
        "EXPERIENCE",
        "PROJECTS",
        "EDUCATION",
        "LANGUAGES",
        "REFERENCES",
        "CERTIFICATIONS",
        "AWARDS",
        "PUBLICATIONS",
        "VOLUNTEER",
        "ACTIVITIES",
        "LEADERSHIP",
        "OTHER"
    ]
    SKILL_HEADER_ALIASES = {
        "programming languages": "Programming Skills",
        "programming skills": "Programming Skills",
        "development skills": "Development Skills",
        "wireframe and mockups": "Wireframe and Mockups",
        "operating systems": "Operating Systems",
        "visualization programs": "Visualization Programs",
        "tools": "Tools",
        "technologies": "Technologies",
        "frameworks": "Frameworks",
        "libraries": "Libraries",
        "databases": "Databases",
        "cloud": "Cloud Platforms",
        "cloud platforms": "Cloud Platforms",
    }

    @staticmethod
    def update(
        resume_text: str,
        missing_skills: list[str],
        job_description: str = "",
        matched_skills: list[str] | None = None
    ) -> str:
        if not resume_text:
            return ""

        allowed_skills = extract_skills(resume_text)
        prompt = resume_update_prompt(
            resume=resume_text,
            allowed_skills=allowed_skills,
            job_desc=job_description,
            matched_skills=matched_skills or []
        )

        try:
            updated = LocalLLMClient.generate(prompt)
            if not updated:
                raise ValueError("Empty resume update")

            cleaned = ResumeUpdater._sanitize_generated_resume(updated)
            sanitized = ResumeUpdater._ensure_skills_inventory(cleaned, allowed_skills)
            if ResumeUpdater._contains_disallowed_skills(sanitized, allowed_skills):
                return ResumeUpdater._ats_reformat(
                    resume_text,
                    allowed_skills,
                    section_template_text=resume_text
                )

            formatted = ResumeUpdater._ats_reformat(
                sanitized,
                allowed_skills,
                section_template_text=resume_text
            )
            return formatted.strip() or ResumeUpdater._ats_reformat(
                resume_text,
                allowed_skills,
                section_template_text=resume_text
            )
        except Exception:
            return ResumeUpdater._ats_reformat(
                resume_text,
                allowed_skills,
                section_template_text=resume_text
            )

    @staticmethod
    def strict_ats_reformat(resume_text: str) -> str:
        if not resume_text:
            return ""
        allowed_skills = extract_skills(resume_text)
        return ResumeUpdater._ats_reformat(
            resume_text,
            allowed_skills,
            section_template_text=resume_text
        )

    @staticmethod
    def _contains_disallowed_skills(updated_text: str, allowed_skills: list[str]) -> bool:
        updated_skills = set(extract_skills(updated_text))
        return bool(updated_skills - set(allowed_skills))

    @staticmethod
    def _ensure_skills_inventory(updated_text: str, allowed_skills: list[str]) -> str:
        if not updated_text or not allowed_skills:
            return updated_text

        skills_line = ", ".join(allowed_skills)
        text_lower = updated_text.lower()
        all_present = all(skill.lower() in text_lower for skill in allowed_skills)
        if all_present:
            return updated_text

        if re.search(r"(^|\n)SKILLS\s*$", updated_text, flags=re.IGNORECASE | re.MULTILINE):
            return f"{updated_text}\n{skills_line}".strip()

        return f"{updated_text}\n\nSKILLS\n{skills_line}".strip()

    @staticmethod
    def _sanitize_generated_resume(text: str) -> str:
        cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not cleaned:
            return ""

        cleaned = re.sub(r"(?m)^\s*```[a-zA-Z]*\s*$", "", cleaned)
        cleaned = cleaned.replace("```", "")
        cleaned = cleaned.replace("\\n", "\n")
        cleaned = re.sub(
            r"^\s*(here(?:'s| is)|below is|updated resume|resume update|enhanced resume|optimized resume)\b.*$",
            "",
            cleaned,
            flags=re.IGNORECASE | re.MULTILINE
        )
        cleaned = re.sub(r"^\s*#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.replace("**", "")

        section_headers = [
            "SUMMARY",
            "SKILLS",
            "EXPERIENCE",
            "PROJECTS",
            "EDUCATION",
            "CERTIFICATIONS",
            "AWARDS",
            "PUBLICATIONS",
            "VOLUNTEER",
            "ACTIVITIES",
            "LEADERSHIP",
        ]
        normalized_headers = {header.lower(): header for header in section_headers}

        rebuilt_lines: list[str] = []
        for raw_line in cleaned.split("\n"):
            line = raw_line.strip()
            if not line:
                continue

            inline_match = re.match(r"^([A-Za-z ]{3,30})\s*[:\-]\s*(.+)$", line)
            if inline_match:
                maybe_header = inline_match.group(1).strip().lower()
                remainder = inline_match.group(2).strip()
                if maybe_header in normalized_headers:
                    rebuilt_lines.append(normalized_headers[maybe_header])
                    if remainder:
                        rebuilt_lines.append(remainder)
                    continue

            line_header = line.rstrip(":").strip().lower()
            if line_header in normalized_headers:
                rebuilt_lines.append(normalized_headers[line_header])
                continue

            rebuilt_lines.append(line)

        return "\n".join(rebuilt_lines).strip()

    @staticmethod
    def _ats_reformat(
        resume_text: str,
        allowed_skills: list[str],
        section_template_text: str = ""
    ) -> str:
        lines = ResumeUpdater._normalize_lines(resume_text)
        sections, header_lines, detected_order = ResumeUpdater._split_into_sections(lines)
        output: list[str] = []

        header_block = ResumeUpdater._build_header_block(header_lines)
        if header_block:
            output.extend(header_block)
            output.append("")

        normalized_sections = ResumeUpdater._normalize_sections(sections, allowed_skills)
        template_order: list[str] = []
        if section_template_text.strip():
            template_lines = ResumeUpdater._normalize_lines(section_template_text)
            _, _, template_order = ResumeUpdater._split_into_sections(template_lines)

        # Ensure a summary section exists by deriving from non-bullet factual lines.
        if not normalized_sections.get("SUMMARY") and not normalized_sections.get("PROFILE"):
            summary = ResumeUpdater._derive_summary_from_sections(normalized_sections)
            if summary:
                normalized_sections["SUMMARY"] = summary

        has_named_sections = any(section != "OTHER" for section in detected_order)
        ordered_sections = ResumeUpdater._build_section_order(
            template_order=template_order,
            detected_order=detected_order,
            sections=normalized_sections
        )
        for section in ordered_sections:
            content = normalized_sections.get(section, [])
            if not content:
                continue
            if section == "OTHER" and not has_named_sections:
                continue
            output.append(section)
            output.extend(content)
            output.append("")

        return "\n".join(output).strip()

    @staticmethod
    def _normalize_lines(text: str) -> list[str]:
        cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
        raw_lines = cleaned.split("\n")

        normalized = []
        for line in raw_lines:
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"\s+", " ", line)
            line = line.replace("|", " - ")
            line = re.sub(r"^[•\-\–\—\*]\s*", "- ", line)
            normalized.append(line)

        return normalized

    @staticmethod
    def _split_into_sections(lines: list[str]) -> tuple[dict, list[str], list[str]]:
        section_map = {
            "summary": "SUMMARY",
            "professional summary": "SUMMARY",
            "profile": "PROFILE",
            "experience": "EXPERIENCE",
            "work experience": "EXPERIENCE",
            "employment": "EXPERIENCE",
            "projects": "PROJECTS",
            "education": "EDUCATION",
            "skills": "SKILLS",
            "technical skills": "SKILLS",
            "soft skills": "SOFT SKILLS",
            "tools": "SKILLS",
            "technologies": "SKILLS",
            "languages": "LANGUAGES",
            "references": "REFERENCES",
            "certifications": "CERTIFICATIONS",
            "awards": "AWARDS",
            "publications": "PUBLICATIONS",
            "volunteer": "VOLUNTEER",
            "volunteer experience": "VOLUNTEER",
            "activities": "ACTIVITIES",
            "leadership": "LEADERSHIP",
            "contact": "CONTACT",
            "interests": "INTERESTS",
            "objective": "SUMMARY"
        }

        sections = {}
        section_order: list[str] = []
        header_lines = []
        current_section = None
        has_section = False

        for line in lines:
            normalized = re.sub(r"[:\-]+$", "", line).strip().lower()
            if normalized in section_map:
                current_section = section_map[normalized]
                if current_section not in sections:
                    sections[current_section] = []
                    section_order.append(current_section)
                has_section = True
                continue

            inline = re.match(r"^([A-Za-z][A-Za-z &/]{2,40})\s*[:\-]\s*(.+)$", line)
            if inline:
                maybe_heading = inline.group(1).strip().lower()
                remainder = inline.group(2).strip()
                if maybe_heading in section_map:
                    current_section = section_map[maybe_heading]
                    if current_section not in sections:
                        sections[current_section] = []
                        section_order.append(current_section)
                    if remainder:
                        sections[current_section].append(remainder)
                    has_section = True
                    continue

            if current_section is None:
                header_lines.append(line)
            else:
                sections[current_section].append(line)

        if not has_section:
            return {"OTHER": lines}, [], ["OTHER"]

        return sections, header_lines, section_order

    @staticmethod
    def _build_header_block(header_lines: list[str]) -> list[str]:
        if not header_lines:
            return []

        # Keep top personal/contact lines only; avoid long paragraph spillover in header.
        trimmed = [line for line in header_lines if line][:6]
        return trimmed

    @staticmethod
    def _normalize_sections(sections: dict, allowed_skills: list[str]) -> dict:
        normalized = {key: list(value or []) for key, value in sections.items()}
        normalized["SKILLS"] = ResumeUpdater._format_skills_section(
            normalized.get("SKILLS", []),
            allowed_skills
        )

        for section in ["EXPERIENCE", "PROJECTS", "VOLUNTEER", "LEADERSHIP", "OTHER"]:
            if section == "PROJECTS":
                normalized[section] = ResumeUpdater._format_projects_section(
                    normalized.get(section, [])
                )
            else:
                normalized[section] = ResumeUpdater._format_section_lines(
                    normalized.get(section, []),
                    bulletize=True
                )

        for section in [
            "EDUCATION",
            "CERTIFICATIONS",
            "AWARDS",
            "PUBLICATIONS",
            "ACTIVITIES",
            "LANGUAGES",
            "REFERENCES",
            "CONTACT",
            "INTERESTS"
        ]:
            normalized[section] = ResumeUpdater._format_section_lines(
                normalized.get(section, []),
                bulletize=False
            )

        normalized["SUMMARY"] = ResumeUpdater._format_summary(normalized.get("SUMMARY", []))
        normalized["PROFILE"] = ResumeUpdater._format_summary(normalized.get("PROFILE", []))
        normalized["SOFT SKILLS"] = ResumeUpdater._format_section_lines(
            normalized.get("SOFT SKILLS", []),
            bulletize=False
        )
        normalized = ResumeUpdater._ensure_bullet_density(normalized)
        return normalized

    @staticmethod
    def _merge_skill_inventory(allowed_skills: list[str], parsed_skills: list[str]) -> list[str]:
        ordered = []
        seen = set()

        for skill in allowed_skills:
            key = skill.lower().strip()
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(skill.strip())

        for skill in parsed_skills:
            key = skill.lower().strip()
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(skill.strip())

        return ordered

    @staticmethod
    def _wrap_csv(items: list[str], max_chars: int = 92) -> list[str]:
        if not items:
            return []
        lines = []
        current = ""
        for item in items:
            candidate = item if not current else f"{current}, {item}"
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = item
        if current:
            lines.append(current)
        return lines

    @staticmethod
    def _format_section_lines(lines: list[str], bulletize: bool) -> list[str]:
        source_lines = ResumeUpdater._coalesce_wrapped_lines(lines) if bulletize else list(lines or [])
        cleaned = []
        for raw in source_lines:
            line = str(raw or "").strip()
            if not line:
                continue
            line = re.sub(r"\s+", " ", line)
            line = line.replace("•", "-")
            line = re.sub(r"^-+\s*", "", line).strip()
            if not line:
                continue

            if bulletize and not ResumeUpdater._looks_like_heading_line(line):
                cleaned.append(f"- {line}")
            else:
                cleaned.append(line)

        # De-duplicate while preserving order.
        deduped = []
        seen = set()
        for line in cleaned:
            key = line.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(line)
        return deduped

    @staticmethod
    def _coalesce_wrapped_lines(lines: list[str]) -> list[str]:
        normalized = []
        for raw in lines or []:
            line = re.sub(r"\s+", " ", str(raw or "").strip())
            if line:
                normalized.append(line)

        if len(normalized) <= 1:
            return normalized

        merged: list[str] = [normalized[0]]
        for line in normalized[1:]:
            current = merged[-1]
            words = [word for word in re.split(r"\s+", current) if word]
            title_like_ratio = (
                sum(1 for word in words if word[:1].isupper()) / len(words)
                if words else 0.0
            )
            current_is_title = (
                len(words) <= 6
                and not current.endswith((".", "!", "?", ":"))
                and current[:1].isupper()
                and title_like_ratio >= 0.65
                and not re.search(r"\b(19|20)\d{2}\b", current)
            )
            hard_break = (
                line.startswith("- ")
                or ResumeUpdater._looks_like_heading_line(line)
                or current_is_title
                or (current.endswith((".", "!", "?")) and line[:1].isupper())
            )
            if hard_break:
                merged.append(line)
            else:
                merged[-1] = f"{current.rstrip()} {line.lstrip()}"
        return merged

    @staticmethod
    def _format_projects_section(lines: list[str]) -> list[str]:
        normalized_lines = []
        for raw in lines or []:
            line = re.sub(r"\s+", " ", str(raw or "").strip())
            line = re.sub(r"^[•\-\–\—]\s*", "", line).strip()
            if line:
                normalized_lines.append(line)

        normalized_lines = ResumeUpdater._split_combined_project_lines(normalized_lines)
        if not normalized_lines:
            return []

        entries: list[str] = []
        current_title = ""
        current_desc: list[str] = []

        def flush_current() -> None:
            nonlocal current_title, current_desc
            if current_title and current_desc:
                entries.append(f"{current_title}: {' '.join(current_desc).strip()}")
            elif current_title:
                entries.append(current_title)
            elif current_desc:
                entries.append(" ".join(current_desc).strip())
            current_title = ""
            current_desc = []

        for line in normalized_lines:
            if ResumeUpdater._is_project_entry_line(line):
                flush_current()
                entries.append(line)
            elif ResumeUpdater._is_probable_project_title(line):
                flush_current()
                current_title = line.rstrip(":")
            elif (
                current_title
                and not current_desc
                and ResumeUpdater._is_project_title_continuation(line)
            ):
                current_title = f"{current_title} {line}".strip()
            else:
                current_desc.append(line)

        flush_current()

        deduped: list[str] = []
        seen: set[str] = set()
        for entry in entries:
            key = entry.lower().strip()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(entry)
        return deduped

    @staticmethod
    def _split_combined_project_lines(lines: list[str]) -> list[str]:
        split_lines: list[str] = []
        title_pattern = re.compile(r"([A-Z][A-Za-z0-9()&+/'\-\s]{2,80}):\s*")

        for raw in lines or []:
            text = str(raw or "").strip()
            if not text:
                continue

            matches = list(title_pattern.finditer(text))
            if len(matches) <= 1:
                split_lines.append(text)
                continue

            for idx, match in enumerate(matches):
                start = match.start()
                end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
                chunk = text[start:end].strip()
                chunk = re.sub(r"\s+", " ", chunk)
                if chunk:
                    split_lines.append(chunk)

        # Secondary split: handle lines where project entries are sentence-joined
        # as "... . Next Project: ...", which may evade title matching.
        secondary: list[str] = []
        boundary_pattern = re.compile(r"(?<=\.)\s+(?=[A-Z][A-Za-z0-9()&+/'\-\s]{2,80}:\s*)")
        for raw in split_lines:
            parts = [re.sub(r"\s+", " ", part).strip() for part in boundary_pattern.split(raw) if part.strip()]
            if parts:
                secondary.extend(parts)
            else:
                secondary.append(raw)

        return secondary

    @staticmethod
    def _is_probable_project_title(line: str) -> bool:
        text = str(line or "").strip()
        if not text:
            return False
        if text.endswith((".", "!", "?")):
            return False

        words = [word for word in re.split(r"\s+", text) if word]
        if len(words) < 2 or len(words) > 12:
            return False

        lower = text.lower()
        if re.search(r"\b(was|were|is|are|built|developed|implemented|created|designed|using|required|helped|allow|allowed)\b", lower):
            return False
        if lower.startswith(("the ", "an ", "a ")) and len(words) > 5:
            return False

        title_case_ratio = sum(1 for word in words if word[:1].isupper()) / len(words)
        return title_case_ratio >= 0.55

    @staticmethod
    def _is_project_title_continuation(line: str) -> bool:
        text = str(line or "").strip()
        if not text or text.endswith((".", "!", "?")):
            return False
        words = [word for word in re.split(r"\s+", text) if word]
        if len(words) > 4:
            return False
        if text.endswith(")") or text.startswith("("):
            return True
        return bool(text[:1].isupper() and sum(1 for word in words if word[:1].isupper()) / max(1, len(words)) >= 0.7)

    @staticmethod
    def _is_project_entry_line(line: str) -> bool:
        text = str(line or "").strip()
        if not text:
            return False
        match = re.match(r"^([A-Z][A-Za-z0-9()&+/'\-\s]{2,80}):\s*(.+)$", text)
        if not match:
            return False
        title = match.group(1).strip()
        description = match.group(2).strip()
        if not title or not description:
            return False
        return len(title.split()) <= 14

    @staticmethod
    def _looks_like_heading_line(line: str) -> bool:
        lower = line.lower()
        if re.search(r"\b(19|20)\d{2}\b", lower):
            return True
        if re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", lower):
            return True
        if " - " in line and len(line) <= 90:
            return True
        if " at " in lower and len(line) <= 90:
            return True
        if len(line.split()) <= 5 and line.upper() == line:
            return True
        return False

    @staticmethod
    def _format_summary(lines: list[str]) -> list[str]:
        cleaned = []
        for raw in lines or []:
            line = re.sub(r"^-\s*", "", str(raw or "").strip())
            if not line:
                continue
            cleaned.append(line)
        merged = ResumeUpdater._merge_paragraph_lines(cleaned)
        return merged[:4]

    @staticmethod
    def _derive_summary_from_sections(sections: dict) -> list[str]:
        for section in ["PROFILE", "EXPERIENCE", "PROJECTS", "OTHER"]:
            for line in sections.get(section, []):
                plain = re.sub(r"^-\s*", "", line).strip()
                if not plain:
                    continue
                if ResumeUpdater._looks_like_heading_line(plain):
                    continue
                if len(plain.split()) < 4:
                    continue
                return [plain]
        return []

    @staticmethod
    def _merge_paragraph_lines(lines: list[str]) -> list[str]:
        if not lines:
            return []
        merged: list[str] = [str(lines[0]).strip()]
        for raw in lines[1:]:
            line = str(raw or "").strip()
            if not line:
                continue
            previous = merged[-1]
            hard_break = (
                previous.endswith((".", "!", "?"))
                or ResumeUpdater._looks_like_heading_line(line)
            )
            if hard_break:
                merged.append(line)
            else:
                merged[-1] = f"{previous} {line}".strip()
        return merged

    @staticmethod
    def _normalize_skill_header(text: str) -> str:
        normalized = re.sub(r"[:\-]+$", "", str(text or "").strip()).lower()
        if normalized in ResumeUpdater.SKILL_HEADER_ALIASES:
            return ResumeUpdater.SKILL_HEADER_ALIASES[normalized]
        return ""

    @staticmethod
    def _dedupe_preserve(items: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for raw in items:
            item = str(raw or "").strip()
            key = item.lower()
            if not item or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    @staticmethod
    def _format_skills_section(lines: list[str], allowed_skills: list[str]) -> list[str]:
        skill_lines = ResumeUpdater._format_section_lines(lines, bulletize=False)
        groups: dict[str, list[str]] = {}
        order: list[str] = []
        ungrouped: list[str] = []
        current_header = ""

        def ensure_group(header: str) -> None:
            if header not in groups:
                groups[header] = []
                order.append(header)

        for raw in skill_lines:
            line = str(raw or "").strip()
            if not line:
                continue

            inline = re.match(r"^([A-Za-z][A-Za-z &/]{2,40})\s*[:\-]\s*(.+)$", line)
            if inline:
                maybe_header = ResumeUpdater._normalize_skill_header(inline.group(1))
                if maybe_header:
                    current_header = maybe_header
                    ensure_group(current_header)
                    groups[current_header].extend(
                        token.strip()
                        for token in re.split(r"[;,]\s*", inline.group(2))
                        if token.strip()
                    )
                    continue

            header_only = ResumeUpdater._normalize_skill_header(line)
            if header_only:
                current_header = header_only
                ensure_group(current_header)
                continue

            tokens = [token.strip() for token in line.split(",") if token.strip()]
            if len(tokens) > 1:
                for token in tokens:
                    maybe_header = ResumeUpdater._normalize_skill_header(token)
                    if maybe_header:
                        current_header = maybe_header
                        ensure_group(current_header)
                        continue
                    if current_header:
                        groups[current_header].append(token)
                    else:
                        ungrouped.append(token)
            elif current_header:
                groups[current_header].append(line)
            else:
                ungrouped.append(line)

        merged_core = ResumeUpdater._merge_skill_inventory(allowed_skills, ungrouped)
        if merged_core:
            ensure_group("Core Skills")
            groups["Core Skills"] = ResumeUpdater._merge_skill_inventory(
                groups.get("Core Skills", []),
                merged_core
            )

        output: list[str] = []
        for header in order:
            items = ResumeUpdater._dedupe_preserve(groups.get(header, []))
            if not items:
                continue
            wrapped = ResumeUpdater._wrap_csv(items, max_chars=84)
            if not wrapped:
                continue
            output.append(f"{header}: {wrapped[0]}")
            for chunk in wrapped[1:]:
                output.append(f"  {chunk}")

        if not output and merged_core:
            return ResumeUpdater._wrap_csv(ResumeUpdater._dedupe_preserve(merged_core), max_chars=84)

        return output

    @staticmethod
    def _ensure_bullet_density(sections: dict, target_bullets: int = 8) -> dict:
        normalized = {key: list(value or []) for key, value in (sections or {}).items()}
        experience_lines = list(normalized.get("EXPERIENCE", []))
        existing_bullets = [line for line in experience_lines if str(line).strip().startswith("- ")]
        bullet_count = len(existing_bullets)
        if bullet_count >= target_bullets:
            return normalized

        candidates: list[str] = []
        project_lines = normalized.get("PROJECTS", [])
        for entry in project_lines:
            text = str(entry or "").strip()
            if not text:
                continue
            if ":" in text:
                text = text.split(":", 1)[1].strip()
            candidates.extend(ResumeUpdater._split_into_sentences(text))

        for source_line in normalized.get("PROFILE", []) + normalized.get("SUMMARY", []):
            candidates.extend(ResumeUpdater._split_into_sentences(str(source_line or "").strip()))

        deduped_candidates = ResumeUpdater._dedupe_preserve(
            [
                re.sub(r"\s+", " ", item.strip())
                for item in candidates
                if item and len(item.split()) >= 4
            ]
        )
        existing_line_keys = {str(line).lower().strip() for line in experience_lines}

        for sentence in deduped_candidates:
            if bullet_count >= target_bullets:
                break
            bullet = f"- {sentence}"
            key = bullet.lower().strip()
            if key in existing_line_keys:
                continue
            experience_lines.append(bullet)
            existing_line_keys.add(key)
            bullet_count += 1

        if experience_lines:
            normalized["EXPERIENCE"] = experience_lines

        return normalized

    @staticmethod
    def _split_into_sentences(text: str) -> list[str]:
        line = str(text or "").strip()
        if not line:
            return []
        parts = re.split(r"(?<=[.!?])\s+", line)
        sentences = [re.sub(r"\s+", " ", part).strip() for part in parts if part and part.strip()]
        return sentences or [line]

    @staticmethod
    def _build_section_order(
        template_order: list[str],
        detected_order: list[str],
        sections: dict
    ) -> list[str]:
        order: list[str] = []
        seen: set[str] = set()

        for candidate in template_order + detected_order + ResumeUpdater.SECTION_ORDER + sorted(sections.keys()):
            section = str(candidate or "").strip().upper()
            if not section or section in seen:
                continue
            if not sections.get(section):
                continue
            seen.add(section)
            order.append(section)

        return order
