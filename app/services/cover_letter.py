from app.llm.client import LocalLLMClient
from app.llm.prompts import cover_letter_prompt

class CoverLetterGenerator:
    @staticmethod
    def generate(resume_text: str, job_description: str) -> str:
        prompt = cover_letter_prompt(resume_text, job_description)
        output = LocalLLMClient.generate(prompt)
        return CoverLetterGenerator._clean_output(output)

    @staticmethod
    def _clean_output(text: str) -> str:
        raw = (text or "").replace("\r\n", "\n").strip()
        if not raw:
            return ""

        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw.rsplit("\n", 1)[0]

        lines = [line.strip() for line in raw.split("\n")]
        intro_prefixes = (
            "cover letter",
            "generated cover letter",
            "professional cover letter",
            "here is",
            "here's",
            "below is",
            "certainly",
            "of course",
            "sure",
        )
        trailing_prefixes = (
            "let me know",
            "feel free",
            "if you'd like",
            "if you want",
            "i can",
            "note:",
            "tips:",
        )

        start = 0
        end = len(lines) - 1

        while start <= end:
            line = lines[start].lstrip("#* ").strip().lower()
            if not line or any(line.startswith(prefix) for prefix in intro_prefixes):
                start += 1
                continue
            break

        while end >= start:
            line = lines[end].strip().lower()
            if not line or any(line.startswith(prefix) for prefix in trailing_prefixes):
                end -= 1
                continue
            break

        return "\n".join(lines[start:end + 1]).strip()
