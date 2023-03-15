from __future__ import annotations

from typing import Dict

try:
    from guardrails import Guard
except ImportError:
    Guard = None


from langchain.output_parsers.base import BaseOutputParser


class GuardrailOutputParser(BaseOutputParser):
    guard = Guard

    @property
    def _type(self) -> str:
        return "guardrail"

    @classmethod
    def from_rail(cls, rail_file: str, num_reasks: int = 1) -> GuardrailOutputParser:
        if Guard is None:
            raise ImportError(
                "guardrails-ai package not installed. "
                "Install it by running `pip install guardrails-ai`."
            )
        return cls(guard=Guard.from_rail(rail_file, num_reasks=num_reasks))

    @classmethod
    def from_rail_string(
        cls, rail_str: str, num_reasks: int = 1
    ) -> GuardrailOutputParser:
        if Guard is None:
            raise ImportError(
                "guardrails-ai package not installed. "
                "Install it by running `pip install guardrails-ai`."
            )
        return cls(guard=Guard.from_rail_string(rail_str, num_reasks=num_reasks))

    def get_format_instructions(self) -> str:
        return self.guard.raw_prompt.format_instructions

    def parse(self, text: str) -> Dict:
        return self.guard.parse(text)
