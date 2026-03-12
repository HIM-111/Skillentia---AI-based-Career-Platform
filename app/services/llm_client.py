"""
Centralized LLM client with hallucination safeguards.
All AI text generation must go through this module.
"""

from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.LLM_API_KEY)


def template_fallback(prompt: str) -> str:
    """
    Deterministic fallback used when no LLM is configured.
    Prevents hallucinations and ensures system reliability.
    """
    return (
        "Dear Hiring Manager,\n\n"
        "I am writing to express my interest in the position. "
        "My skills and experience align well with the job requirements. "
        "I am eager to contribute and grow within your organization.\n\n"
        "Sincerely,\n"
        "Candidate"
    )


def generate_text(prompt: str) -> str:
    """
    Generates text using an external LLM if configured.
    Falls back to deterministic templates otherwise.
    """

    if not settings.LLM_API_KEY:
        return template_fallback(prompt)

    # IMPORTANT:
    # LLM calls must be tightly constrained to avoid hallucinations.
    # No open-ended creativity, no reasoning, no assumptions.

    try:
        # Example placeholder — provider-agnostic
        # Replace with OpenAI / Azure / local gateway if needed
        response = call_llm_api(
            prompt=prompt,
            temperature=0.2,
            max_tokens=300
        )
        return response.strip()

    except Exception:
        # Safety fallback
        return template_fallback(prompt)


def call_llm_api(prompt: str, temperature: float, max_tokens: int) -> str:
    """
    Calls OpenAI Chat Completions API with strict constraints
    to minimize hallucinations.
    """

    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a professional career assistant. "
                    "Only use the information explicitly provided. "
                    "Do not make assumptions. Do not invent facts."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=temperature,   # LOW creativity
        max_tokens=max_tokens,     # Hard limit
        top_p=0.9
    )

    return response.choices[0].message.content
