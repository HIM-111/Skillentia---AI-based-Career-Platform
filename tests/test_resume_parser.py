from app.services.resume_parser import ResumeParser
import re


def test_resume_parser_text_input():
    sample_text = "Experienced Python developer with FastAPI and Docker."
    parser = ResumeParser()

    result = parser.parse_text(sample_text)

    assert isinstance(result, str)
    assert "Python" in result


def test_resume_parser_doc_fallback_extracts_text():
    fake_doc_bytes = b"\x00\x01Candidate Resume Jane Doe Python FastAPI Docker SQL\x00\x02"
    parsed = ResumeParser.parse(fake_doc_bytes, "doc")

    assert isinstance(parsed, str)
    assert "Python" in parsed or "FastAPI" in parsed


def test_pdf_column_aware_page_extraction_orders_left_before_right():
    class FakePage:
        width = 600

        def extract_words(self, **_kwargs):
            return [
                {"text": "SUMMARY", "x0": 40, "x1": 120, "top": 40, "bottom": 50},
                {"text": "Backend", "x0": 40, "x1": 100, "top": 58, "bottom": 68},
                {"text": "Engineer", "x0": 108, "x1": 180, "top": 58, "bottom": 68},
                {"text": "EXPERIENCE", "x0": 40, "x1": 150, "top": 95, "bottom": 105},
                {"text": "Built", "x0": 40, "x1": 70, "top": 113, "bottom": 123},
                {"text": "FastAPI", "x0": 78, "x1": 130, "top": 113, "bottom": 123},
                {"text": "SKILLS", "x0": 330, "x1": 390, "top": 42, "bottom": 52},
                {"text": "Python", "x0": 330, "x1": 380, "top": 60, "bottom": 70},
                {"text": "SQL", "x0": 388, "x1": 420, "top": 60, "bottom": 70},
                {"text": "Docker", "x0": 330, "x1": 385, "top": 78, "bottom": 88},
                {"text": "AWS", "x0": 392, "x1": 430, "top": 78, "bottom": 88},
            ]

        def extract_text(self, *args, **kwargs):
            _ = (args, kwargs)
            return ""

    extracted = ResumeParser._extract_pdf_page_text(FakePage())

    assert "SUMMARY" in extracted
    assert "SKILLS" in extracted
    assert extracted.index("SUMMARY") < extracted.index("SKILLS")
    assert "Built FastAPI" in extracted
    assert "Python SQL" in extracted


def test_pdf_detect_column_split_returns_none_for_single_column():
    words = [
        {"text": "John", "x0": 40, "x1": 80, "top": 10, "bottom": 20},
        {"text": "Doe", "x0": 90, "x1": 120, "top": 10, "bottom": 20},
    ]
    # Repeat enough words to satisfy min token checks while staying single-column.
    words = words * 20

    split = ResumeParser._detect_column_split(words, page_width=600)
    assert split is None


def test_pdf_layout_inference_detects_two_column_with_top_header():
    words = []
    # Centered heading line.
    words.extend(
        [
            {"text": "JANE", "x0": 250, "x1": 285, "top": 20, "bottom": 30},
            {"text": "DOE", "x0": 292, "x1": 325, "top": 20, "bottom": 30},
            {"text": "ENGINEER", "x0": 332, "x1": 392, "top": 20, "bottom": 30},
        ]
    )
    # Two-column body.
    for i in range(18):
        y = 60 + (i * 14)
        words.append({"text": f"L{i}", "x0": 40, "x1": 62, "top": y, "bottom": y + 10})
        words.append({"text": f"LX{i}", "x0": 72, "x1": 102, "top": y, "bottom": y + 10})
        words.append({"text": f"R{i}", "x0": 340, "x1": 362, "top": y, "bottom": y + 10})
        words.append({"text": f"RX{i}", "x0": 372, "x1": 402, "top": y, "bottom": y + 10})

    split = ResumeParser._detect_column_split(words, page_width=600)
    assert split is not None
    layout = ResumeParser._infer_page_layout(words, page_width=600, split_x=split)
    assert layout["is_two_column"] is True
    assert layout["header_bottom"] > 0


def test_pdf_layout_inference_detects_single_column_vertical_resume():
    words = []
    for i in range(40):
        y = 20 + (i * 12)
        words.append({"text": f"Item{i}", "x0": 40, "x1": 90, "top": y, "bottom": y + 10})
        words.append({"text": "describes", "x0": 98, "x1": 152, "top": y, "bottom": y + 10})
        words.append({"text": "experience", "x0": 160, "x1": 228, "top": y, "bottom": y + 10})
        words.append({"text": "details", "x0": 236, "x1": 286, "top": y, "bottom": y + 10})

    split = ResumeParser._detect_column_split(words, page_width=600)
    if split is not None:
        layout = ResumeParser._infer_page_layout(words, page_width=600, split_x=split)
        assert layout["is_two_column"] is False


def test_lines_layout_orders_rowwise_for_two_column_resume_sections():
    lines = [
        {"text": "Jane Doe", "top": 15, "bottom": 24, "x0": 250, "x1": 340},
        {"text": "Education", "top": 55, "bottom": 64, "x0": 40, "x1": 120},
        {"text": "Profile", "top": 55, "bottom": 64, "x0": 340, "x1": 400},
        {"text": "Skills", "top": 95, "bottom": 104, "x0": 40, "x1": 90},
        {"text": "Projects", "top": 95, "bottom": 104, "x0": 340, "x1": 410},
        {"text": "Soft Skills", "top": 135, "bottom": 144, "x0": 40, "x1": 120},
        {"text": "References", "top": 135, "bottom": 144, "x0": 340, "x1": 420},
    ]
    text = ResumeParser._lines_to_text_with_layout(lines, page_width=600)

    assert text.index("Education") < text.index("Profile")
    assert text.index("Profile") < text.index("Skills")
    assert text.index("Skills") < text.index("Projects")


def test_pdf_char_reconstruction_preserves_dot_leaders_and_rating():
    class FakeCrop:
        def __init__(self, chars):
            self.chars = chars

        def extract_text(self, *args, **kwargs):
            _ = (args, kwargs)
            return ""

    class FakePage:
        width = 600
        height = 800

        def __init__(self):
            self._chars = []
            self._words = []
            self._seed_data()

        @property
        def chars(self):
            return self._chars

        def _emit_chars(self, text, x_start, y, step=5.0):
            x = x_start
            for ch in text:
                if ch == " ":
                    x += step * 0.9
                    continue
                self._chars.append({"text": ch, "x0": x, "x1": x + 3.5, "top": y, "bottom": y + 9})
                x += step

        def _seed_data(self):
            # Left column
            self._emit_chars("SUMMARY", 40, 40)
            self._emit_chars("Backend Engineer", 40, 58)
            self._emit_chars("EXPERIENCE", 40, 90)
            self._emit_chars("Built APIs", 40, 108)
            # Right column with dot leaders + 4/5 rating
            self._emit_chars("SKILLS", 330, 40)
            self._emit_chars("Python ..... 4/5", 330, 58)
            self._emit_chars("SQL ....... 5/5", 330, 76)

            self._words = [
                {"text": "SUMMARY", "x0": 40, "x1": 120, "top": 40, "bottom": 50},
                {"text": "Backend", "x0": 40, "x1": 100, "top": 58, "bottom": 68},
                {"text": "Engineer", "x0": 108, "x1": 180, "top": 58, "bottom": 68},
                {"text": "EXPERIENCE", "x0": 40, "x1": 150, "top": 90, "bottom": 100},
                {"text": "Built", "x0": 40, "x1": 70, "top": 108, "bottom": 118},
                {"text": "APIs", "x0": 78, "x1": 108, "top": 108, "bottom": 118},
                {"text": "SKILLS", "x0": 330, "x1": 390, "top": 40, "bottom": 50},
                {"text": "Python", "x0": 330, "x1": 380, "top": 58, "bottom": 68},
                {"text": "4/5", "x0": 430, "x1": 455, "top": 58, "bottom": 68},
                {"text": "SQL", "x0": 330, "x1": 360, "top": 76, "bottom": 86},
                {"text": "5/5", "x0": 430, "x1": 455, "top": 76, "bottom": 86},
            ]

        def extract_words(self, **_kwargs):
            return list(self._words)

        def crop(self, bbox):
            x0, _top, x1, _bottom = bbox
            filtered = [
                ch for ch in self._chars
                if float(ch["x0"]) >= float(x0) and float(ch["x1"]) <= float(x1)
            ]
            return FakeCrop(filtered)

        def extract_text(self, *args, **kwargs):
            _ = (args, kwargs)
            return ""

    extracted = ResumeParser._extract_pdf_page_text(FakePage())
    assert extracted.index("SUMMARY") < extracted.index("SKILLS")
    assert "4/5" in extracted
    assert re.search(r"Python\s*\.{3,}\s*4/5", extracted)


def test_lines_layout_state_carries_section_across_pages_when_heading_missing():
    state = {}
    page_one = []
    for idx in range(9):
        y = 60 + (idx * 16)
        page_one.append({"text": f"Edu {idx}", "top": y, "bottom": y + 10, "x0": 40, "x1": 120})
    page_one.extend(
        [
            {"text": "Projects", "top": 60, "bottom": 70, "x0": 330, "x1": 410},
            {"text": "Project Alpha", "top": 76, "bottom": 86, "x0": 330, "x1": 450},
            {"text": "Project Alpha detail", "top": 92, "bottom": 102, "x0": 330, "x1": 500},
        ]
    )

    page_two = []
    for idx in range(9):
        y = 40 + (idx * 16)
        page_two.append({"text": f"Lang {idx}", "top": y, "bottom": y + 10, "x0": 40, "x1": 110})
    page_two.extend(
        [
            {"text": "Project Beta", "top": 40, "bottom": 50, "x0": 330, "x1": 430},
            {"text": "Project Beta detail", "top": 56, "bottom": 66, "x0": 330, "x1": 495},
            {"text": "References", "top": 96, "bottom": 106, "x0": 330, "x1": 410},
        ]
    )

    first = ResumeParser._lines_to_text_with_layout(page_one, page_width=600, region_state=state)
    second = ResumeParser._lines_to_text_with_layout(page_two, page_width=600, region_state=state)

    assert "Projects" in first
    assert "Projects" in second
    assert second.index("Projects") < second.index("Project Beta")
    assert "Lang 0" in second
    assert second.index("Project Beta") < second.index("References")


def test_merge_fragmented_lines_joins_same_row_text_segments():
    lines = [
        {"text": "seeking opportunities", "top": 100.0, "bottom": 110.0, "x0": 300.0, "x1": 420.0},
        {"text": "to apply and expand", "top": 100.4, "bottom": 110.2, "x0": 430.0, "x1": 540.0},
        {"text": "next line", "top": 120.0, "bottom": 130.0, "x0": 300.0, "x1": 350.0},
    ]
    merged = ResumeParser._merge_fragmented_lines(lines)
    assert len(merged) == 2
    assert merged[0]["text"] == "seeking opportunities to apply and expand"
