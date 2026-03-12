import logging
import re
import subprocess
from io import BytesIO
from statistics import median
from typing import Any, Optional

import pdfplumber
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTTextLine
from docx import Document

from app.llm.client import LocalLLMClient

logger = logging.getLogger(__name__)


class ResumeParser:
    COMMON_SECTION_TITLES = {
        "summary",
        "professional summary",
        "profile",
        "education",
        "experience",
        "work experience",
        "employment",
        "skills",
        "technical skills",
        "soft skills",
        "projects",
        "certifications",
        "languages",
        "interests",
        "references",
        "awards",
        "publications",
        "volunteer",
        "achievements",
        "objective",
        "contact",
    }
    """
    Service responsible for extracting text from resume files.
    Supports PDF, DOCX, DOC, and TXT formats.
    """

    @staticmethod
    def parse(file_bytes: bytes, file_extension: str) -> Optional[str]:
        """
        Extract text from resume file bytes.

        Args:
            file_bytes (bytes): Raw file content.
            file_extension (str): File extension (pdf or docx).

        Returns:
            str: Extracted resume text or None if extraction fails.
        """

        try:
            if file_extension == "pdf":
                return ResumeParser._parse_pdf(file_bytes)

            if file_extension == "docx":
                return ResumeParser._parse_docx(file_bytes)

            if file_extension == "txt":
                return ResumeParser._parse_txt(file_bytes)

            if file_extension in {"doc", "docs"}:
                return ResumeParser._parse_doc(file_bytes)

            raise ValueError("Unsupported file type")

        except Exception as exc:
            logger.error(f"Resume parsing failed: {exc}")
            return None

    @staticmethod
    def _parse_pdf(file_bytes: bytes) -> str:
        """
        Extract text from PDF resume.
        """
        # Primary pipeline: pdfminer line extraction + layout-aware section parsing.
        miner_pages = ResumeParser._extract_pdf_lines_with_pdfminer(file_bytes)
        if miner_pages:
            rendered_pages = []
            region_state: dict[str, str] = {}
            for page in miner_pages:
                lines = page.get("lines", [])
                page_width = float(page.get("width", 0.0) or 0.0)
                if not lines:
                    continue
                rendered = ResumeParser._lines_to_text_with_layout(
                    lines,
                    page_width=page_width,
                    region_state=region_state
                )
                if rendered.strip():
                    rendered_pages.append(rendered)

            if rendered_pages:
                merged = ResumeParser._normalize_extracted_text("\n\n".join(rendered_pages))
                llm_restructured = ResumeParser._restructure_with_llm(merged)
                if llm_restructured:
                    return ResumeParser._normalize_extracted_text(llm_restructured)
                return merged

        text_content = []

        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = ResumeParser._extract_pdf_page_text(page)
                if page_text:
                    text_content.append(page_text)

        return ResumeParser._normalize_extracted_text("\n\n".join(text_content))

    @staticmethod
    def _extract_pdf_lines_with_pdfminer(file_bytes: bytes) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        try:
            for page_layout in extract_pages(BytesIO(file_bytes)):
                page_width = float(getattr(page_layout, "width", 0.0) or 0.0)
                page_height = float(getattr(page_layout, "height", 0.0) or 0.0)
                lines: list[dict[str, Any]] = []

                for element in page_layout:
                    if not isinstance(element, LTTextContainer):
                        continue
                    for line in element:
                        if not isinstance(line, LTTextLine):
                            continue
                        text = str(line.get_text() or "").strip()
                        if not text:
                            continue
                        x0, y0, x1, y1 = line.bbox
                        # pdfminer y origin is bottom-left; convert to top-down coordinates.
                        top = page_height - float(y1)
                        bottom = page_height - float(y0)
                        lines.append(
                            {
                                "text": text,
                                "top": top,
                                "bottom": bottom,
                                "x0": float(x0),
                                "x1": float(x1),
                            }
                        )

                if lines:
                    pages.append({"width": page_width, "height": page_height, "lines": lines})
        except Exception as exc:
            logger.warning("pdfminer extraction failed: %s", exc)
            return []

        return pages

    @staticmethod
    def _restructure_with_llm(text: str) -> str:
        """
        Optional LLM pass to repair section boundaries after geometric extraction.
        It is non-blocking and falls back silently on failure.
        """
        candidate = (text or "").strip()
        if not candidate:
            return ""
        if len(candidate) < 200:
            return ""

        prompt = (
            "You are a deterministic resume text organizer.\n"
            "Input may be mixed due to PDF columns.\n"
            "Task: reorganize text into sections using detected headings only.\n"
            "Rules:\n"
            "- DO NOT invent or add information.\n"
            "- Keep wording exactly as provided when possible.\n"
            "- Preserve punctuation-heavy lines (e.g., 'Python ..... 4/5').\n"
            "- Keep each section heading on its own line, followed by its lines.\n"
            "- Return plain text only, no markdown fences, no commentary.\n\n"
            f"INPUT:\n{candidate}\n"
        )

        try:
            output = LocalLLMClient.generate(prompt, timeout=25)
            cleaned = ResumeParser._normalize_extracted_text(output)
            if not cleaned:
                return ""
            # Accept only when output appears sectioned.
            heading_count = ResumeParser._count_heading_like_lines(cleaned)
            if heading_count >= 2:
                return cleaned
            return ""
        except Exception:
            return ""

    @staticmethod
    def _count_heading_like_lines(text: str) -> int:
        count = 0
        for line in (text or "").split("\n"):
            normalized = line.strip()
            if not normalized:
                continue
            if ResumeParser._looks_like_section_heading(normalized, ""):
                count += 1
        return count

    @staticmethod
    def _extract_pdf_page_text(page: Any) -> str:
        """
        Extract text from a single PDF page, with column-aware parsing to reduce
        left/right section mixing in multi-column resumes.
        """
        page_width = float(getattr(page, "width", 0.0) or 0.0)
        page_height = float(getattr(page, "height", 0.0) or 0.0)
        chars = ResumeParser._extract_page_chars(page)

        # Primary path: char-level line reconstruction with auto layout detection.
        if chars:
            lines = ResumeParser._chars_to_lines(chars)
            if lines:
                line_text = ResumeParser._lines_to_text_with_layout(lines, page_width)
                if line_text.strip():
                    return ResumeParser._normalize_extracted_text(line_text)

        words = ResumeParser._extract_page_words(page)

        if words:
            split_x = ResumeParser._detect_column_split(words, page_width)
            if split_x is not None:
                layout = ResumeParser._infer_page_layout(words, page_width, split_x)
                if not layout.get("is_two_column"):
                    split_x = None

            if split_x is not None:
                gutter = max(4.0, page_width * 0.01)
                header_bottom = float(layout.get("header_bottom", 0.0) or 0.0)
                body_top = min(page_height, max(0.0, header_bottom + 1.0))

                header_text = ""
                if header_bottom > 0:
                    header_text = ResumeParser._extract_region_text(
                        page,
                        0.0,
                        page_width,
                        y0=0.0,
                        y1=header_bottom
                    )

                left_text = ResumeParser._extract_region_text(
                    page,
                    0.0,
                    max(0.0, split_x - gutter),
                    y0=body_top,
                    y1=page_height if page_height > 0 else None
                )
                right_text = ResumeParser._extract_region_text(
                    page,
                    min(page_width, split_x + gutter),
                    page_width,
                    y0=body_top,
                    y1=page_height if page_height > 0 else None
                )

                # Fallback to word-based reconstruction if region extraction fails.
                if not header_text.strip() and not left_text.strip() and not right_text.strip():
                    left_words = [
                        word for word in words
                        if float(word.get("x0", 0.0)) < split_x and float(word.get("top", 0.0)) >= body_top
                    ]
                    right_words = [
                        word for word in words
                        if float(word.get("x0", 0.0)) >= split_x and float(word.get("top", 0.0)) >= body_top
                    ]
                    left_text = ResumeParser._words_to_text(left_words)
                    right_text = ResumeParser._words_to_text(right_words)
                    if header_bottom > 0:
                        header_words = [word for word in words if float(word.get("bottom", 0.0)) <= header_bottom]
                        header_text = ResumeParser._words_to_text(header_words)

                return ResumeParser._normalize_extracted_text(
                    "\n\n".join(part for part in [header_text, left_text, right_text] if part.strip())
                )

        region_text = ResumeParser._extract_region_text(page, 0.0, page_width)
        if region_text:
            return ResumeParser._normalize_extracted_text(region_text)

        if words:
            return ResumeParser._normalize_extracted_text(ResumeParser._words_to_text(words))

        # Fallbacks when word extraction is unavailable.
        try:
            layout_text = page.extract_text(layout=True)  # type: ignore[arg-type]
            if layout_text and layout_text.strip():
                return ResumeParser._normalize_extracted_text(layout_text)
        except Exception:
            pass

        plain_text = page.extract_text() or ""
        return ResumeParser._normalize_extracted_text(plain_text)

    @staticmethod
    def _chars_to_lines(chars: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not chars:
            return []

        chars_sorted = sorted(chars, key=lambda item: (float(item["top"]), float(item["x0"])))
        heights = [max(1.0, float(ch["bottom"]) - float(ch["top"])) for ch in chars_sorted]
        widths = [max(0.5, float(ch["x1"]) - float(ch["x0"])) for ch in chars_sorted]
        line_height = median(heights) if heights else 10.0
        avg_width = median(widths) if widths else 4.0
        y_tolerance = max(2.0, line_height * 0.45)
        space_threshold = max(1.1, avg_width * 0.75)

        grouped: list[dict[str, Any]] = []
        for ch in chars_sorted:
            top = float(ch["top"])
            if not grouped:
                grouped.append({"top": top, "bottom": float(ch["bottom"]), "chars": [ch]})
                continue

            current = grouped[-1]
            if abs(top - float(current["top"])) <= y_tolerance:
                current["chars"].append(ch)
                current["bottom"] = max(float(current["bottom"]), float(ch["bottom"]))
                current["top"] = (float(current["top"]) + top) / 2.0
            else:
                grouped.append({"top": top, "bottom": float(ch["bottom"]), "chars": [ch]})

        lines: list[dict[str, Any]] = []
        for row in grouped:
            row_chars = sorted(row["chars"], key=lambda item: float(item["x0"]))
            text = ResumeParser._join_chars(row_chars, space_threshold=space_threshold)
            if not text.strip():
                continue
            lines.append(
                {
                    "text": text.rstrip(),
                    "top": float(row["top"]),
                    "bottom": float(row["bottom"]),
                    "x0": min(float(ch["x0"]) for ch in row_chars),
                    "x1": max(float(ch["x1"]) for ch in row_chars),
                }
            )
        return lines

    @staticmethod
    def _lines_to_text_with_layout(
        lines: list[dict[str, Any]],
        page_width: float,
        region_state: Optional[dict[str, str]] = None
    ) -> str:
        if not lines:
            return ""

        split_x = ResumeParser._detect_line_column_split(lines, page_width)
        heights = [max(1.0, float(line["bottom"]) - float(line["top"])) for line in lines]
        line_height = median(heights) if heights else 10.0
        paragraph_gap = max(8.0, line_height * 1.35)

        if split_x is None:
            ordered_lines = ResumeParser._merge_fragmented_lines(lines)
            ordered_lines = sorted(ordered_lines, key=lambda row: (float(row["top"]), float(row["x0"])))
            return ResumeParser._render_section_aware_lines(ordered_lines, paragraph_gap)

        full_threshold = page_width * 0.72
        margin = page_width * 0.12
        full_lines = []
        left_lines = []
        right_lines = []
        for line in lines:
            x0 = float(line["x0"])
            x1 = float(line["x1"])
            width = x1 - x0
            mid = (x0 + x1) / 2.0
            if width >= full_threshold or (x0 <= (split_x - margin) and x1 >= (split_x + margin)):
                full_lines.append(line)
            elif mid < split_x:
                left_lines.append(line)
            else:
                right_lines.append(line)

        full_lines = ResumeParser._merge_fragmented_lines(full_lines)
        left_lines = ResumeParser._merge_fragmented_lines(left_lines)
        right_lines = ResumeParser._merge_fragmented_lines(right_lines)

        entries: list[dict[str, Any]] = []
        state = region_state if region_state is not None else {}

        def _add_region(lines_in_region: list[dict[str, Any]], region_name: str) -> None:
            if not lines_in_region:
                return
            preamble, sections = ResumeParser._extract_section_blocks(lines_in_region)
            if preamble:
                active_title = state.get(region_name, "").strip()
                if active_title:
                    entries.append(
                        {
                            "kind": "section",
                            "title": active_title,
                            "top": float(preamble[0]["top"]),
                            "x0": float(preamble[0]["x0"]),
                            "lines": [str(row["text"]) for row in preamble],
                            "region": region_name,
                        }
                    )
                else:
                    entries.append(
                        {
                            "kind": "preamble",
                            "top": float(preamble[0]["top"]),
                            "x0": float(preamble[0]["x0"]),
                            "lines": [str(row["text"]) for row in preamble],
                            "region": region_name
                        }
                    )
            entries.extend(sections)
            if sections:
                last_title = str(sections[-1].get("title", "")).strip()
                if last_title:
                    state[region_name] = last_title

        _add_region(full_lines, "full")
        _add_region(left_lines, "left")
        _add_region(right_lines, "right")

        if not entries:
            ordered_lines = ResumeParser._order_multicolumn_lines(lines, split_x, page_width)
            return ResumeParser._render_section_aware_lines(ordered_lines, paragraph_gap)

        entries.sort(key=lambda item: (float(item["top"]), float(item["x0"])))
        output: list[str] = []
        for entry in entries:
            if entry["kind"] == "section":
                title = str(entry.get("title", "")).strip()
                if title:
                    output.append(title)
                output.extend(entry.get("lines", []))
                output.append("")
            else:
                output.extend(entry.get("lines", []))
                output.append("")

        return "\n".join(output).strip()

    @staticmethod
    def _merge_fragmented_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(lines) <= 1:
            return list(lines)

        ordered = sorted(lines, key=lambda row: (float(row["top"]), float(row["x0"])))
        heights = [max(1.0, float(row["bottom"]) - float(row["top"])) for row in ordered]
        line_height = median(heights) if heights else 10.0
        row_tolerance = max(2.0, line_height * 0.45)

        grouped: list[list[dict[str, Any]]] = []
        for row in ordered:
            top = float(row["top"])
            if not grouped:
                grouped.append([row])
                continue

            prev_group = grouped[-1]
            prev_top = float(prev_group[0]["top"])
            if abs(top - prev_top) <= row_tolerance:
                prev_group.append(row)
            else:
                grouped.append([row])

        merged: list[dict[str, Any]] = []
        for group in grouped:
            parts = sorted(group, key=lambda row: float(row["x0"]))
            if len(parts) == 1:
                merged.append(parts[0])
                continue

            widths = [max(1.0, float(part["x1"]) - float(part["x0"])) for part in parts]
            median_width = median(widths) if widths else 30.0
            gap_limit = max(24.0, min(60.0, median_width * 0.9))

            current_chunk = [parts[0]]
            chunks: list[list[dict[str, Any]]] = []
            for part in parts[1:]:
                prev = current_chunk[-1]
                gap = float(part["x0"]) - float(prev["x1"])
                if gap <= gap_limit:
                    current_chunk.append(part)
                else:
                    chunks.append(current_chunk)
                    current_chunk = [part]
            chunks.append(current_chunk)

            for chunk in chunks:
                text_parts = [
                    str(part.get("text", "")).strip()
                    for part in chunk
                    if str(part.get("text", "")).strip()
                ]
                if not text_parts:
                    continue

                merged.append(
                    {
                        "text": " ".join(text_parts).strip(),
                        "top": min(float(part["top"]) for part in chunk),
                        "bottom": max(float(part["bottom"]) for part in chunk),
                        "x0": min(float(part["x0"]) for part in chunk),
                        "x1": max(float(part["x1"]) for part in chunk),
                    }
                )

        return merged

    @staticmethod
    def _extract_section_blocks(lines: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        ordered = sorted(lines, key=lambda row: (float(row["top"]), float(row["x0"])))
        if not ordered:
            return [], []

        preamble: list[dict[str, Any]] = []
        sections: list[dict[str, Any]] = []
        active_section: Optional[dict[str, Any]] = None

        for idx, row in enumerate(ordered):
            line = str(row.get("text", "")).strip()
            if not line:
                continue

            if ResumeParser._is_underline_line(line):
                continue

            next_line = ""
            if idx + 1 < len(ordered):
                next_line = str(ordered[idx + 1].get("text", "")).strip()

            is_heading = ResumeParser._looks_like_section_heading(
                line,
                next_line,
                in_section=(active_section is not None)
            )
            if is_heading:
                if active_section is not None:
                    sections.append(active_section)
                active_section = {
                    "kind": "section",
                    "title": ResumeParser._normalize_heading_text(line),
                    "top": float(row["top"]),
                    "x0": float(row["x0"]),
                    "lines": [],
                }
                continue

            if active_section is None:
                preamble.append(row)
            else:
                active_section["lines"].append(line)

        if active_section is not None:
            sections.append(active_section)

        return preamble, sections

    @staticmethod
    def _is_underline_line(text: str) -> bool:
        stripped = text.strip()
        if len(stripped) < 3:
            return False
        if re.fullmatch(r"[-_=~.]{3,}", stripped):
            return True
        return False

    @staticmethod
    def _normalize_heading_text(text: str) -> str:
        heading = re.sub(r"[:\-]+$", "", text.strip())
        heading = re.sub(r"\s+", " ", heading)
        return heading

    @staticmethod
    def _looks_like_section_heading(line: str, next_line: str = "", in_section: bool = False) -> bool:
        raw = line.strip()
        if not raw:
            return False

        normalized = re.sub(r"[:\-]+$", "", raw).strip()
        lower = normalized.lower()
        words = [w for w in re.split(r"\s+", normalized) if w]
        if not words or len(words) > 6:
            return False

        if "," in normalized:
            return False

        if re.search(r"@|https?://|www\.|linkedin|github", lower):
            return False
        if re.search(r"\b\d{3}[-\s)]?\d{3}[-\s]?\d{4}\b", normalized):
            return False

        if ResumeParser._is_underline_line(next_line):
            return True
        if lower in ResumeParser.COMMON_SECTION_TITLES:
            return True

        letters = [ch for ch in normalized if ch.isalpha()]
        if not letters:
            return False
        upper_ratio = sum(1 for ch in letters if ch.isupper()) / len(letters)
        title_like = sum(1 for w in words if w[:1].isupper()) / len(words)

        if upper_ratio >= 0.8 and len(words) <= 5 and len(normalized) <= 40:
            return True

        # Avoid false positives inside sections (e.g., school/company names).
        if in_section:
            return False

        return False

    @staticmethod
    def _render_section_aware_lines(lines: list[dict[str, Any]], paragraph_gap: float) -> str:
        preamble, sections = ResumeParser._extract_section_blocks(lines)
        if sections:
            output: list[str] = []
            if preamble:
                output.extend([str(row["text"]).strip() for row in preamble if str(row.get("text", "")).strip()])
                output.append("")
            for section in sections:
                title = str(section.get("title", "")).strip()
                if title:
                    output.append(title)
                output.extend([str(x).strip() for x in section.get("lines", []) if str(x).strip()])
                output.append("")
            return "\n".join(output).strip()

        output: list[str] = []
        prev_bottom: Optional[float] = None
        for row in lines:
            line_text = str(row.get("text", "")).strip()
            if not line_text:
                continue
            if prev_bottom is not None:
                gap = float(row["top"]) - prev_bottom
                if gap > paragraph_gap:
                    output.append("")
            output.append(line_text)
            prev_bottom = float(row["bottom"])
        return "\n".join(output).strip()

    @staticmethod
    def _detect_line_column_split(lines: list[dict[str, Any]], page_width: float) -> Optional[float]:
        if not lines or page_width <= 0:
            return None
        if len(lines) < 12:
            return None

        candidate_lines = [
            line for line in lines
            if (float(line["x1"]) - float(line["x0"])) <= page_width * 0.64
        ]
        if len(candidate_lines) >= 10:
            centers = sorted((float(line["x0"]) + float(line["x1"])) / 2.0 for line in candidate_lines)
            n = len(centers)
            min_side = max(4, int(n * 0.25))
            best_gap = 0.0
            best_split = None

            for idx in range(n - 1):
                left_count = idx + 1
                right_count = n - left_count
                if left_count < min_side or right_count < min_side:
                    continue
                gap = centers[idx + 1] - centers[idx]
                if gap > best_gap:
                    split = centers[idx] + (gap / 2.0)
                    if page_width * 0.22 <= split <= page_width * 0.78:
                        best_gap = gap
                        best_split = split

            if best_split is not None and best_gap >= max(20.0, page_width * 0.06):
                left = [line for line in candidate_lines if ((float(line["x0"]) + float(line["x1"])) / 2.0) < best_split]
                right = [line for line in candidate_lines if ((float(line["x0"]) + float(line["x1"])) / 2.0) >= best_split]
                if len(left) >= min_side and len(right) >= min_side:
                    left_top, left_bottom = min(float(x["top"]) for x in left), max(float(x["bottom"]) for x in left)
                    right_top, right_bottom = min(float(x["top"]) for x in right), max(float(x["bottom"]) for x in right)
                    overlap = max(0.0, min(left_bottom, right_bottom) - max(left_top, right_top))
                    left_span = max(1.0, left_bottom - left_top)
                    right_span = max(1.0, right_bottom - right_top)
                    if overlap / min(left_span, right_span) >= 0.3:
                        return best_split

        # Fallback detection: cluster by x0 starts. Useful when one column has
        # very wide lines that fail width-based filtering.
        x0s = sorted(float(line["x0"]) for line in lines)
        n_all = len(x0s)
        if n_all < 12:
            return None

        min_side = max(3, int(n_all * 0.1))
        best_gap_x = 0.0
        best_split_x = None
        for idx in range(n_all - 1):
            left_count = idx + 1
            right_count = n_all - left_count
            if left_count < min_side or right_count < min_side:
                continue
            gap = x0s[idx + 1] - x0s[idx]
            if gap > best_gap_x:
                split = x0s[idx] + (gap / 2.0)
                if page_width * 0.2 <= split <= page_width * 0.8:
                    best_gap_x = gap
                    best_split_x = split

        if best_split_x is None or best_gap_x < max(18.0, page_width * 0.12):
            return None

        left_lines = [line for line in lines if float(line["x0"]) < best_split_x]
        right_lines = [line for line in lines if float(line["x0"]) >= best_split_x]
        if len(left_lines) < min_side or len(right_lines) < min_side:
            return None

        left_top, left_bottom = min(float(x["top"]) for x in left_lines), max(float(x["bottom"]) for x in left_lines)
        right_top, right_bottom = min(float(x["top"]) for x in right_lines), max(float(x["bottom"]) for x in right_lines)
        overlap = max(0.0, min(left_bottom, right_bottom) - max(left_top, right_top))
        left_span = max(1.0, left_bottom - left_top)
        right_span = max(1.0, right_bottom - right_top)
        if overlap / min(left_span, right_span) < 0.2:
            return None

        return best_split_x

    @staticmethod
    def _order_multicolumn_lines(lines: list[dict[str, Any]], split_x: float, page_width: float) -> list[dict[str, Any]]:
        heights = [max(1.0, float(line["bottom"]) - float(line["top"])) for line in lines]
        line_height = median(heights) if heights else 10.0
        row_tolerance = max(2.5, line_height * 0.55)

        sorted_lines = sorted(lines, key=lambda row: (float(row["top"]), float(row["x0"])))
        rows: list[dict[str, Any]] = []
        for line in sorted_lines:
            top = float(line["top"])
            if not rows:
                rows.append({"top": top, "bottom": float(line["bottom"]), "items": [line]})
                continue
            current = rows[-1]
            if abs(top - float(current["top"])) <= row_tolerance:
                current["items"].append(line)
                current["bottom"] = max(float(current["bottom"]), float(line["bottom"]))
                current["top"] = (float(current["top"]) + top) / 2.0
            else:
                rows.append({"top": top, "bottom": float(line["bottom"]), "items": [line]})

        ordered: list[dict[str, Any]] = []
        full_threshold = page_width * 0.72
        margin = page_width * 0.12

        for row in rows:
            full = []
            left = []
            right = []
            for line in row["items"]:
                x0 = float(line["x0"])
                x1 = float(line["x1"])
                width = x1 - x0
                mid = (x0 + x1) / 2.0
                if width >= full_threshold or (x0 <= (split_x - margin) and x1 >= (split_x + margin)):
                    full.append(line)
                elif mid < split_x:
                    left.append(line)
                else:
                    right.append(line)

            full = sorted(full, key=lambda item: float(item["x0"]))
            left = sorted(left, key=lambda item: float(item["x0"]))
            right = sorted(right, key=lambda item: float(item["x0"]))
            ordered.extend(full + left + right)

        return ordered

    @staticmethod
    def _extract_region_text(
        page: Any,
        x0: float,
        x1: float,
        y0: Optional[float] = None,
        y1: Optional[float] = None
    ) -> str:
        """
        Extract text from a page region using char-level reconstruction to preserve
        punctuation-heavy content (e.g., dot leaders and 4/5 ratings).
        """
        region = page
        page_width = float(getattr(page, "width", 0.0) or 0.0)
        page_height = float(getattr(page, "height", 0.0) or 0.0)
        top = 0.0 if y0 is None else max(0.0, float(y0))
        bottom = page_height if y1 is None else max(0.0, float(y1))

        if (
            hasattr(page, "crop")
            and page_width > 0
            and page_height > 0
            and 0 <= x0 < x1 <= page_width
            and 0 <= top < bottom <= page_height
        ):
            try:
                region = page.crop((x0, top, x1, bottom))
            except Exception:
                region = page

        chars = ResumeParser._extract_page_chars(region)
        if chars:
            return ResumeParser._chars_to_text(chars)

        try:
            layout_text = region.extract_text(layout=True)  # type: ignore[arg-type]
            if layout_text and layout_text.strip():
                return layout_text
        except Exception:
            pass

        try:
            plain = region.extract_text() or ""
            return plain.strip()
        except Exception:
            return ""

    @staticmethod
    def _extract_page_words(page: Any) -> list[dict[str, Any]]:
        """
        Extract page words with coordinates; tolerant to pdfplumber version differences.
        """
        try:
            words = page.extract_words(  # type: ignore[attr-defined]
                keep_blank_chars=False,
                use_text_flow=False,
                x_tolerance=2,
                y_tolerance=2
            )
        except TypeError:
            try:
                words = page.extract_words()  # type: ignore[attr-defined]
            except Exception:
                return []
        except Exception:
            return []

        normalized: list[dict[str, Any]] = []
        for word in words or []:
            text = str(word.get("text", "")).strip()
            if not text:
                continue
            if not all(k in word for k in ("x0", "x1", "top", "bottom")):
                continue
            normalized.append(
                {
                    "text": text,
                    "x0": float(word["x0"]),
                    "x1": float(word["x1"]),
                    "top": float(word["top"]),
                    "bottom": float(word["bottom"]),
                }
            )
        return normalized

    @staticmethod
    def _detect_column_split(words: list[dict[str, Any]], page_width: float) -> Optional[float]:
        """
        Detect a probable two-column split point.
        Returns split x-coordinate when a strong center gutter is detected.
        """
        if not words or page_width <= 0:
            return None
        if len(words) < 30:
            return None

        centers = sorted((float(word["x0"]) + float(word["x1"])) / 2.0 for word in words)
        n = len(centers)
        min_side_words = max(8, int(n * 0.2))

        best_gap = 0.0
        best_split = None
        for idx in range(n - 1):
            left_count = idx + 1
            right_count = n - left_count
            if left_count < min_side_words or right_count < min_side_words:
                continue
            gap = centers[idx + 1] - centers[idx]
            if gap > best_gap:
                candidate = centers[idx] + (gap / 2.0)
                # Ignore extreme splits near edges.
                if page_width * 0.2 <= candidate <= page_width * 0.8:
                    best_gap = gap
                    best_split = candidate

        if best_split is None or best_gap < max(16.0, page_width * 0.04):
            return None

        left_words = [word for word in words if float(word["x0"]) < best_split]
        right_words = [word for word in words if float(word["x0"]) >= best_split]
        if len(left_words) < min_side_words or len(right_words) < min_side_words:
            return None

        # Verify vertical overlap to confirm true side-by-side columns.
        left_top, left_bottom = min(word["top"] for word in left_words), max(word["bottom"] for word in left_words)
        right_top, right_bottom = min(word["top"] for word in right_words), max(word["bottom"] for word in right_words)
        overlap = max(0.0, min(left_bottom, right_bottom) - max(left_top, right_top))
        left_span = max(1.0, left_bottom - left_top)
        right_span = max(1.0, right_bottom - right_top)
        overlap_ratio = overlap / min(left_span, right_span)
        if overlap_ratio < 0.25:
            return None

        return best_split

    @staticmethod
    def _infer_page_layout(words: list[dict[str, Any]], page_width: float, split_x: float) -> dict[str, Any]:
        """
        Decide whether page is truly two-column and detect header band that should
        remain full-width before left/right body extraction.
        """
        lines = ResumeParser._group_word_lines(words)
        if not lines:
            return {"is_two_column": False, "header_bottom": 0.0}

        gutter = max(6.0, page_width * 0.015)
        gap_threshold = max(26.0, page_width * 0.1)
        two_col_lines = 0
        left_present = 0
        right_present = 0
        center_heavy_top = 0

        annotated = []
        for idx, line in enumerate(lines):
            left = 0
            right = 0
            center = 0
            min_x = page_width
            max_x = 0.0
            left_max_x = -1.0
            right_min_x = page_width
            for word in line["words"]:
                x0 = float(word["x0"])
                x1 = float(word["x1"])
                mid = (x0 + x1) / 2.0
                min_x = min(min_x, x0)
                max_x = max(max_x, x1)
                if mid <= split_x - gutter:
                    left += 1
                    left_max_x = max(left_max_x, x1)
                elif mid >= split_x + gutter:
                    right += 1
                    right_min_x = min(right_min_x, x0)
                else:
                    center += 1

            if left > 0:
                left_present += 1
            if right > 0:
                right_present += 1
            inter_gap = (right_min_x - left_max_x) if (left_max_x >= 0 and right_min_x < page_width) else 0.0
            if left > 0 and right > 0 and center == 0 and inter_gap >= gap_threshold:
                two_col_lines += 1
            if idx < 6 and center > 0:
                center_heavy_top += 1

            annotated.append(
                {
                    "top": float(line["top"]),
                    "bottom": float(line["bottom"]),
                    "left": left,
                    "right": right,
                    "center": center,
                    "min_x": min_x,
                    "max_x": max_x,
                    "inter_gap": inter_gap,
                    "word_count": len(line["words"]),
                }
            )

        n = max(1, len(annotated))
        two_col_ratio = two_col_lines / n
        side_coverage_ok = left_present >= max(3, int(n * 0.25)) and right_present >= max(3, int(n * 0.25))
        is_two = two_col_ratio >= 0.22 and side_coverage_ok

        if not is_two:
            return {"is_two_column": False, "header_bottom": 0.0}

        # Detect transition point: top centered/full-width heading before two-column body.
        header_bottom = 0.0
        if center_heavy_top > 0 or len(annotated) > 0:
            for idx in range(min(10, len(annotated))):
                row = annotated[idx]
                is_header_like = (
                    row["center"] > 0
                    or row["inter_gap"] < gap_threshold
                    or row["word_count"] <= 4
                )
                if is_header_like:
                    header_bottom = max(header_bottom, float(row["bottom"]))
                else:
                    break

        return {"is_two_column": True, "header_bottom": header_bottom}

    @staticmethod
    def _group_word_lines(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not words:
            return []
        words_sorted = sorted(words, key=lambda word: (float(word["top"]), float(word["x0"])))
        heights = [max(1.0, float(word["bottom"]) - float(word["top"])) for word in words_sorted]
        line_height = median(heights) if heights else 10.0
        y_tolerance = max(2.5, line_height * 0.45)

        grouped: list[dict[str, Any]] = []
        for word in words_sorted:
            top = float(word["top"])
            if not grouped:
                grouped.append({"top": top, "bottom": float(word["bottom"]), "words": [word]})
                continue
            current = grouped[-1]
            if abs(top - float(current["top"])) <= y_tolerance:
                current["words"].append(word)
                current["bottom"] = max(float(current["bottom"]), float(word["bottom"]))
                current["top"] = (float(current["top"]) + top) / 2.0
            else:
                grouped.append({"top": top, "bottom": float(word["bottom"]), "words": [word]})
        return grouped

    @staticmethod
    def _extract_page_chars(page: Any) -> list[dict[str, Any]]:
        chars_raw = getattr(page, "chars", None)
        if not chars_raw:
            return []

        chars: list[dict[str, Any]] = []
        for ch in chars_raw:
            text = str(ch.get("text", ""))
            if text == "":
                continue
            if not all(k in ch for k in ("x0", "x1", "top", "bottom")):
                continue
            chars.append(
                {
                    "text": text,
                    "x0": float(ch["x0"]),
                    "x1": float(ch["x1"]),
                    "top": float(ch["top"]),
                    "bottom": float(ch["bottom"]),
                }
            )
        return chars

    @staticmethod
    def _chars_to_text(chars: list[dict[str, Any]]) -> str:
        if not chars:
            return ""
        lines = ResumeParser._chars_to_lines(chars)
        return ResumeParser._lines_to_text_with_layout(lines, page_width=0.0)

    @staticmethod
    def _join_chars(chars: list[dict[str, Any]], space_threshold: float) -> str:
        if not chars:
            return ""
        out = ""
        prev_x1 = None
        prev_char = ""
        for ch in chars:
            token = str(ch.get("text", ""))
            x0 = float(ch.get("x0", 0.0))
            x1 = float(ch.get("x1", x0))

            if prev_x1 is not None:
                gap = x0 - prev_x1
                if ResumeParser._char_gap_requires_space(prev_char, token, gap, space_threshold):
                    out += " "
            out += token
            prev_x1 = x1
            prev_char = token

        out = re.sub(r"[ \t]+", " ", out)
        return out.strip()

    @staticmethod
    def _char_gap_requires_space(prev_char: str, next_char: str, gap: float, space_threshold: float) -> bool:
        if gap <= space_threshold:
            return False

        if not prev_char or not next_char:
            return True

        if prev_char == "." and next_char == ".":
            return False
        if prev_char.isdigit() and next_char == "/":
            return False
        if prev_char == "/" and next_char.isdigit():
            return False
        if next_char in ",.;:!?%)]}/":
            return False
        if prev_char in "([{":
            return False

        return True

    @staticmethod
    def _words_to_text(words: list[dict[str, Any]]) -> str:
        """
        Convert positioned words into ordered text lines and paragraphs.
        """
        if not words:
            return ""

        words_sorted = sorted(words, key=lambda word: (float(word["top"]), float(word["x0"])))
        heights = [max(1.0, float(word["bottom"]) - float(word["top"])) for word in words_sorted]
        line_height = median(heights) if heights else 10.0
        y_tolerance = max(2.5, line_height * 0.45)
        paragraph_gap = max(7.0, line_height * 1.3)

        grouped: list[dict[str, Any]] = []
        for word in words_sorted:
            top = float(word["top"])
            if not grouped:
                grouped.append({"top": top, "bottom": float(word["bottom"]), "words": [word]})
                continue

            current = grouped[-1]
            if abs(top - float(current["top"])) <= y_tolerance:
                current["words"].append(word)
                current["bottom"] = max(float(current["bottom"]), float(word["bottom"]))
                current["top"] = (float(current["top"]) + top) / 2.0
            else:
                grouped.append({"top": top, "bottom": float(word["bottom"]), "words": [word]})

        lines: list[str] = []
        previous_bottom = None
        for line in grouped:
            line_words = sorted(line["words"], key=lambda word: float(word["x0"]))
            line_text = ResumeParser._join_words(line_words)
            if not line_text:
                continue

            if previous_bottom is not None:
                gap = float(line["top"]) - previous_bottom
                if gap > paragraph_gap:
                    lines.append("")

            lines.append(line_text)
            previous_bottom = float(line["bottom"])

        return "\n".join(lines).strip()

    @staticmethod
    def _join_words(words: list[dict[str, Any]]) -> str:
        if not words:
            return ""
        parts: list[str] = []
        for word in words:
            token = str(word.get("text", "")).strip()
            if not token:
                continue
            if parts and re.match(r"^[,.;:!?%)]$", token):
                parts[-1] = f"{parts[-1]}{token}"
            elif parts and token in {"'s", "’s"}:
                parts[-1] = f"{parts[-1]}{token}"
            else:
                parts.append(token)
        return " ".join(parts).strip()

    @staticmethod
    def _normalize_extracted_text(text: str) -> str:
        if not text:
            return ""
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"[ \t]+", " ", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    @staticmethod
    def _parse_docx(file_bytes: bytes) -> str:
        """
        Extract text from DOCX resume.
        """

        document = Document(BytesIO(file_bytes))
        paragraphs = [
            paragraph.text for paragraph in document.paragraphs
            if paragraph.text.strip()
        ]

        return "\n".join(paragraphs).strip()

    @staticmethod
    def _parse_txt(file_bytes: bytes) -> str:
        """
        Extract text from TXT resume.
        """

        return file_bytes.decode("utf-8", errors="ignore").strip()

    @staticmethod
    def _parse_doc(file_bytes: bytes) -> str:
        """
        Best-effort extraction for legacy DOC files.
        Tries antiword first; falls back to binary text extraction.
        """

        # antiword gives the best result when available in runtime.
        try:
            process = subprocess.run(
                ["antiword", "-"],
                input=file_bytes,
                capture_output=True,
                check=False
            )
            if process.returncode == 0 and process.stdout:
                parsed = process.stdout.decode("utf-8", errors="ignore").strip()
                if parsed:
                    return parsed
        except FileNotFoundError:
            pass

        # Fallback: extract printable strings from binary DOC stream.
        decoded = file_bytes.decode("latin-1", errors="ignore")
        text_chunks = re.findall(r"[A-Za-z0-9@:/,.\-+() ]{4,}", decoded)
        cleaned = " ".join(chunk.strip() for chunk in text_chunks if chunk.strip())
        return re.sub(r"\s+", " ", cleaned).strip()

    @staticmethod
    def parse_text(text: str) -> str:
        """
        Normalize raw resume text (used for tests or direct input).
        """

        return text.strip()
