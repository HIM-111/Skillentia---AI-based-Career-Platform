import requests
from app.core.config import settings


class LocalLLMClient:
    @staticmethod
    def generate(prompt: str, timeout: int = 120) -> str:
        response = requests.post(
            f"{settings.OLLAMA_URL}/api/generate",
            json={
                "model": settings.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0,
                    "top_p": 0.9,
                    "seed": 42
                }
            },
            timeout=timeout
        )

        response.raise_for_status()
        return response.json()["response"].strip()
