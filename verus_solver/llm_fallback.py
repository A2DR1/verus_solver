import os
from typing import List

from openai import OpenAI
from openai import BadRequestError

from .models import Candidate, VerusResult


class LLMFallback:
    def __init__(self, model: str, temperature: float = 0.2, api_base: str | None = None):
        self.model = model
        self.temperature = temperature
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=api_base)

    def generate(self, code: str, result: VerusResult, max_candidates: int = 2) -> List[Candidate]:
        prompt = (
            "You are repairing Verus code. Return ONLY full Rust code.\n"
            "Target the top verifier issue while minimizing edits.\n\n"
            f"Top issues:\n{result.raw_stderr}\n\n"
            f"Code:\n{code}"
        )
        req = {
            "model": self.model,
            "n": max_candidates,
            "messages": [
                {"role": "system", "content": "You are an expert Verus proof engineer."},
                {"role": "user", "content": prompt},
            ],
        }
        # Some latest reasoning models only support default temperature.
        if not self.model.startswith("gpt-5"):
            req["temperature"] = self.temperature
        try:
            rsp = self.client.chat.completions.create(**req)
        except BadRequestError:
            # Retry with minimal compatible parameters.
            req.pop("temperature", None)
            req["n"] = 1
            rsp = self.client.chat.completions.create(**req)
        out: List[Candidate] = []
        for i, choice in enumerate(rsp.choices):
            text = (choice.message.content or "").strip()
            if text:
                out.append(Candidate(name=f"llm-fallback-{i}", code=text, strategy="llm_fallback"))
        return out

