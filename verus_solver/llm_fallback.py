from __future__ import annotations

import os
from typing import TYPE_CHECKING, List, Optional

from .models import Candidate, VerusResult

if TYPE_CHECKING:
    from .verus_runner import VerusRunner

# ---------------------------------------------------------------------------
# Verus syntax reference injected into every prompt.
# ---------------------------------------------------------------------------
_VERUS_SYNTAX_GUIDE = """
== Verus proof syntax reference (read carefully before writing code) ==

1. Nonlinear arithmetic assertions:
   CORRECT:   assert(x * y <= z) by (nonlinear_arith);
   WRONG:     assert(x * y <= z) by { requires ...; }

2. Proof blocks in exec functions:
   CORRECT:   proof { lemma_foo(x, y); assert(expr); }
   WRONG:     proof { requires ...; }

3. Quantifiers always use closure-style binders:
   CORRECT:   forall|k: int| 0 <= k < n ==> a@[k] >= 0
   WRONG:     forall k: int, 0 <= k ...

4. Loop invariants go between the loop header and the opening brace:
   CORRECT:
       while lo < hi
           invariant 0 <= lo, lo <= hi + 1,
           decreases hi - lo,
       {
   WRONG:     while lo < hi { invariant ...; }

5. Spec/proof functions cannot have executable code; exec functions cannot
   contain bare spec expressions outside proof {} blocks.

6. assert...by with a lemma call:
   CORRECT:   assert(p) by { lemma_foo(args); }
   CORRECT:   assert(p) by (nonlinear_arith);

7. Seq indexing in proof context uses a@[i as int], NOT a[i].

8. Return-type annotation uses (result: T) pattern:
   pub fn foo(...) -> (result: u32)  ensures result == ...

Only return complete, compilable Rust+Verus code. No markdown fences.
"""

_SYSTEM_PROMPT = (
    "You are an expert Verus proof engineer. "
    "You write correct, minimal Verus annotations and never use invalid Verus syntax. "
    "When given the run_verus tool, use it to iteratively test your changes "
    "and fix any remaining issues before returning your final answer."
)

# Anthropic tool definition for run_verus.
_RUN_VERUS_TOOL_ANTHROPIC = {
    "name": "run_verus",
    "description": (
        "Run the Verus verifier on a complete Rust source file and return "
        "the verification result. Use this to test your changes iteratively. "
        "Call it after each edit to see which functions verified and which failed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Complete Rust+Verus source code to verify.",
            }
        },
        "required": ["code"],
    },
}

# Max Verus calls the agent can make per invocation.
_MAX_VERUS_CALLS = 10


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_issues(result: VerusResult) -> str:
    if result.compile_error:
        lines = result.raw_stderr.splitlines()
        error_lines = [l for l in lines if l.startswith("error")][:6]
        return "COMPILE ERROR:\n" + "\n".join(error_lines)
    if not result.issues:
        return (
            f"Verification: {result.verified} verified, {result.errors} errors "
            "(no structured issues parsed)"
        )
    parts = [f"{result.verified} verified, {result.errors} errors. Top issues:"]
    for issue in result.issues[:5]:
        loc = f" (line {issue.line})" if issue.line else ""
        parts.append(f"  [{issue.kind}]{loc}: {issue.message}")
    return "\n".join(parts)


def _format_verus_result(result: VerusResult) -> str:
    """Format a VerusResult as a tool-response string the model can read."""
    if result.success:
        return f"SUCCESS: {result.verified} verified, 0 errors."

    parts = [_format_issues(result)]

    if result.compile_error and result.raw_stderr:
        truncated = result.raw_stderr[:3000]
        if len(result.raw_stderr) > 3000:
            truncated += "\n... (truncated)"
        parts.append("\n== Raw compiler output ==\n" + truncated)
    elif result.raw_stderr:
        stderr_lines = result.raw_stderr.splitlines()
        relevant = [
            l for l in stderr_lines if "error" in l.lower() or "note" in l.lower()
        ][:20]
        if relevant:
            parts.append("\n== Relevant output ==\n" + "\n".join(relevant))

    return "\n".join(parts)


def _format_prev_note(prev_code: Optional[str], prev_result: Optional[VerusResult]) -> str:
    if prev_code is None or prev_result is None:
        return ""
    if prev_result.compile_error:
        lines = prev_result.raw_stderr.splitlines()
        error_lines = [l for l in lines if l.startswith("error")][:3]
        return (
            "\n== Previous attempt note ==\n"
            "Your last generated code had a COMPILE ERROR. Do not repeat that structure.\n"
            + "\n".join(error_lines)
            + "\n"
        )
    if prev_result.errors >= 1:
        return (
            "\n== Previous attempt note ==\n"
            f"Your last attempt reached {prev_result.verified} verified / "
            f"{prev_result.errors} errors but did not fully verify. "
            "Try a different approach for the remaining issues.\n"
        )
    return ""


def _strip_markdown(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(l for l in lines if not l.startswith("```")).strip()
    return text


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class LLMFallback:
    def __init__(
        self,
        model: str,
        temperature: float = 0.2,
        api_base: str | None = None,
        runner: Optional["VerusRunner"] = None,
    ):
        self.model = model
        self.temperature = temperature
        self.api_base = api_base
        self.runner = runner
        self._last_code: Optional[str] = None
        self._last_result: Optional[VerusResult] = None
        # Lazy-initialised clients.
        self._openai_client = None
        self._anthropic_client = None

    # ------------------------------------------------------------------
    # Client accessors (lazy)
    # ------------------------------------------------------------------

    def _get_openai(self):
        if self._openai_client is None:
            from openai import OpenAI
            self._openai_client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY"), base_url=self.api_base
            )
        return self._openai_client

    def _get_anthropic(self):
        if self._anthropic_client is None:
            import anthropic
            self._anthropic_client = anthropic.Anthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )
        return self._anthropic_client

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate(
        self,
        code: str,
        result: VerusResult,
        max_candidates: int = 2,
    ) -> List[Candidate]:
        if self.runner is not None:
            if self.model.startswith("claude"):
                return self._generate_claude_agentic(code, result)
            return self._generate_openai_agentic(code, result)
        return self._generate_openai_oneshot(code, result, max_candidates)

    def update_last_result(self, result: VerusResult) -> None:
        """Call after evaluating the LLM candidate so the next round gets accurate feedback."""
        self._last_result = result

    # ------------------------------------------------------------------
    # Anthropic agentic loop (Claude tool use)
    # ------------------------------------------------------------------

    def _generate_claude_agentic(
        self,
        code: str,
        result: VerusResult,
    ) -> List[Candidate]:
        """
        Give Claude a run_verus tool and let it iterate until verification
        succeeds or the call budget is exhausted.
        """
        client = self._get_anthropic()
        prev_note = _format_prev_note(self._last_code, self._last_result)
        issues_summary = _format_issues(result)

        user_message = (
            f"{_VERUS_SYNTAX_GUIDE}\n"
            f"{prev_note}\n"
            "== Task ==\n"
            "Repair the Verus code below so it fully verifies.\n"
            "Use the run_verus tool to test your changes. Keep iterating until "
            "the tool reports SUCCESS or you run out of attempts.\n"
            "After your final iteration output ONLY the complete repaired Rust "
            "source — no markdown fences, no explanation.\n\n"
            f"== Current verifier feedback ==\n{issues_summary}\n\n"
            f"== Current code ==\n{code}"
        )

        messages: list[dict] = [{"role": "user", "content": user_message}]
        best_code: Optional[str] = None
        best_result: Optional[VerusResult] = None
        verus_calls = 0

        while verus_calls < _MAX_VERUS_CALLS:
            try:
                response = client.messages.create(
                    model=self.model,
                    max_tokens=8192,
                    system=_SYSTEM_PROMPT,
                    tools=[_RUN_VERUS_TOOL_ANTHROPIC],
                    messages=messages,
                )
            except Exception as exc:
                print(f"[llm_fallback] Anthropic API error: {exc}")
                break

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        candidate_code = _strip_markdown(block.text)
                        if candidate_code:
                            best_code = candidate_code
                break

            if response.stop_reason != "tool_use":
                break

            tool_results: list[dict] = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                if block.name != "run_verus":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Unknown tool: {block.name}",
                    })
                    continue

                agent_code = block.input.get("code", "")
                verus_calls += 1
                print(f"[llm_fallback] Claude tool call #{verus_calls}: run_verus()")

                try:
                    vr = self.runner.run_code(agent_code)
                except Exception as exc:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Runner error: {exc}",
                    })
                    continue

                if best_result is None or (
                    not vr.compile_error
                    and (vr.errors < best_result.errors
                         or (vr.errors == best_result.errors
                             and vr.verified > best_result.verified))
                ):
                    best_result = vr
                    best_code = agent_code

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": _format_verus_result(vr),
                })

                if vr.success:
                    break

            messages.append({"role": "user", "content": tool_results})

            if best_result is not None and best_result.success:
                break

        if not best_code:
            return []

        self._last_code = best_code
        self._last_result = best_result or result
        return [Candidate(name="llm-claude-agent-0", code=best_code, strategy="llm_fallback")]

    # ------------------------------------------------------------------
    # OpenAI agentic loop (function calling)
    # ------------------------------------------------------------------

    def _generate_openai_agentic(
        self,
        code: str,
        result: VerusResult,
    ) -> List[Candidate]:
        import json
        from openai import BadRequestError

        client = self._get_openai()
        prev_note = _format_prev_note(self._last_code, self._last_result)
        issues_summary = _format_issues(result)

        user_content = (
            f"{_VERUS_SYNTAX_GUIDE}\n"
            f"{prev_note}\n"
            "== Task ==\n"
            "Repair the Verus code below so it fully verifies.\n"
            "Use the run_verus tool to test each version. Keep iterating until "
            "the tool reports SUCCESS or you run out of attempts.\n"
            "After your final iteration output ONLY the complete repaired Rust "
            "source — no markdown fences, no explanation.\n\n"
            f"== Current verifier feedback ==\n{issues_summary}\n\n"
            f"== Current code ==\n{code}"
        )

        tool_def = {
            "type": "function",
            "function": {
                "name": "run_verus",
                "description": (
                    "Run the Verus verifier on a complete Rust source file. "
                    "Use this to test your changes iteratively."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Complete Rust+Verus source."}
                    },
                    "required": ["code"],
                },
            },
        }

        messages: list[dict] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        best_code: Optional[str] = None
        best_result: Optional[VerusResult] = None
        verus_calls = 0

        while verus_calls < _MAX_VERUS_CALLS:
            req: dict = {
                "model": self.model,
                "messages": messages,
                "tools": [tool_def],
                "tool_choice": "auto",
            }
            if not self.model.startswith("gpt-5") and not self.model.startswith("o"):
                req["temperature"] = self.temperature

            try:
                rsp = client.chat.completions.create(**req)
            except BadRequestError:
                req.pop("temperature", None)
                rsp = client.chat.completions.create(**req)
            except Exception as exc:
                print(f"[llm_fallback] OpenAI API error: {exc}")
                break

            msg = rsp.choices[0].message
            messages.append(msg)

            if rsp.choices[0].finish_reason == "stop" or not msg.tool_calls:
                text = _strip_markdown(msg.content or "")
                if text:
                    best_code = text
                break

            for tc in msg.tool_calls:
                if tc.function.name != "run_verus":
                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": f"Unknown function: {tc.function.name}"})
                    continue
                try:
                    agent_code = json.loads(tc.function.arguments).get("code", "")
                except Exception:
                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": "Error: could not parse arguments."})
                    continue

                verus_calls += 1
                print(f"[llm_fallback] OpenAI tool call #{verus_calls}: run_verus()")
                try:
                    vr = self.runner.run_code(agent_code)
                except Exception as exc:
                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": f"Runner error: {exc}"})
                    continue

                if best_result is None or (
                    not vr.compile_error
                    and (vr.errors < best_result.errors
                         or (vr.errors == best_result.errors
                             and vr.verified > best_result.verified))
                ):
                    best_result = vr
                    best_code = agent_code

                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": _format_verus_result(vr)})

            if best_result is not None and best_result.success:
                break

        if not best_code:
            return []

        self._last_code = best_code
        self._last_result = best_result or result
        return [Candidate(name="llm-openai-agent-0", code=best_code, strategy="llm_fallback")]

    # ------------------------------------------------------------------
    # OpenAI one-shot (no runner available)
    # ------------------------------------------------------------------

    def _generate_openai_oneshot(
        self,
        code: str,
        result: VerusResult,
        max_candidates: int,
    ) -> List[Candidate]:
        from openai import BadRequestError

        client = self._get_openai()
        issues_summary = _format_issues(result)
        prev_note = _format_prev_note(self._last_code, self._last_result)

        prompt = (
            f"{_VERUS_SYNTAX_GUIDE}\n"
            f"{prev_note}\n"
            "== Task ==\n"
            "Repair the Verus code below so it fully verifies.\n"
            "Return ONLY the complete Rust source — no markdown, no explanation.\n\n"
            f"== Verifier feedback ==\n{issues_summary}\n\n"
            f"== Current code ==\n{code}"
        )

        req: dict = {
            "model": self.model,
            "n": max_candidates,
            "messages": [
                {"role": "system", "content": (
                    "You are an expert Verus proof engineer. "
                    "You write correct, minimal Verus annotations. "
                    "You never use syntax that is invalid in Verus."
                )},
                {"role": "user", "content": prompt},
            ],
        }
        if not self.model.startswith("gpt-5") and not self.model.startswith("o"):
            req["temperature"] = self.temperature

        try:
            rsp = client.chat.completions.create(**req)
        except BadRequestError:
            req.pop("temperature", None)
            req["n"] = 1
            rsp = client.chat.completions.create(**req)

        out: List[Candidate] = []
        for i, choice in enumerate(rsp.choices):
            text = _strip_markdown(choice.message.content or "")
            if text:
                out.append(Candidate(name=f"llm-fallback-{i}", code=text, strategy="llm_fallback"))

        if out:
            self._last_code = out[0].code
            self._last_result = result

        return out
